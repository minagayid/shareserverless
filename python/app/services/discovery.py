from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Node, NodeHeartbeatRecord, NodeTier, ReputationEvent
from app.models.schemas import (
    AvailabilityProfile,
    NodeHeartbeat,
    NodeRegistrationRequest,
    NodeReport,
    ReputationUpdateRequest,
    ResourceProfiles,
)


logger = structlog.get_logger(__name__)


class NodeDiscoveryError(Exception):
    pass


class NodeRegistry:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_node(self, req: NodeRegistrationRequest) -> Node:
        fingerprint = _fingerprint(req.public_key_pem)
        existing = await self.db.execute(select(Node).where(Node.fingerprint == fingerprint))
        if existing.scalar_one_or_none():
            raise NodeDiscoveryError(f"Node already registered: {fingerprint}")

        tier = NodeTier.classify(
            vcpu=req.resource_profile.cpu_vcpu,
            ram_gb=req.resource_profile.ram_mb // 1024,
            has_gpu=req.resource_profile.gpu_available,
        )

        node = Node(
            node_id=fingerprint,
            public_key_pem=req.public_key_pem,
            fingerprint=fingerprint,
            tier=tier,
            cpu_vcpu=req.resource_profile.cpu_vcpu,
            ram_mb=req.resource_profile.ram_mb,
            disk_gb=req.resource_profile.disk_gb,
            gpu_available=req.resource_profile.gpu_available,
            gpu_model=req.resource_profile.gpu_model,
            gpu_vram_mb=req.resource_profile.gpu_vram_mb,
            bandwidth_mbps=req.resource_profile.bandwidth_mbps,
            has_ipv6=req.resource_profile.has_ipv6,
            has_static_ip=req.resource_profile.has_static_ip,
            region=req.availability.region,
            country_alpha2=req.availability.country_alpha2,
            timezone=req.availability.timezone,
            avg_uptime_percent=req.availability.avg_uptime_percent,
            latency_p95_ms=req.availability.latency_ms_to_home,
            supported_capabilities=req.supported_capabilities,
            metadata=req.metadata,
            is_online=True,
            last_heartbeat=datetime.now(timezone.utc),
        )

        self.db.add(node)
        await self.db.commit()
        await self.db.refresh(node)
        logger.info("node_registered", node_id=node.node_id, tier=tier.value)
        return node

    async def process_heartbeat(self, heartbeat: NodeHeartbeat) -> Node | None:
        result = await self.db.execute(select(Node).where(Node.node_id == heartbeat.node_id))
        node = result.scalar_one_or_none()
        if not node:
            logger.warning("heartbeat_unknown_node", node_id=heartbeat.node_id)
            return None

        record = NodeHeartbeatRecord(
            node_id=node.id,
            cpu_usage_percent=heartbeat.cpu_usage_percent,
            ram_usage_percent=heartbeat.ram_usage_percent,
            disk_usage_percent=heartbeat.disk_usage_percent,
            active_tasks=heartbeat.active_tasks,
            is_healthy=heartbeat.is_healthy,
        )
        self.db.add(record)

        node.last_heartbeat = datetime.now(timezone.utc)
        node.is_online = heartbeat.is_healthy
        await self.db.commit()
        await self.db.refresh(node)
        logger.debug("heartbeat_processed", node_id=node.node_id)
        return node

    async def get_online_nodes(self, tier: NodeTier | None = None) -> Sequence[Node]:
        q = select(Node).where(Node.is_online == True)
        if tier:
            q = q.where(Node.tier == tier)
        result = await self.db.execute(q)
        return result.scalars().all()

    async def get_node_report(self, node_id: str) -> NodeReport | None:
        result = await self.db.execute(select(Node).where(Node.node_id == node_id))
        node = result.scalar_one_or_none()
        if not node:
            return None

        rep_result = await self.db.execute(
            select(func.avg(ReputationEvent.score_delta)).where(ReputationEvent.node_id == node.id)
        )
        avg_delta = rep_result.scalar() or 0.0

        return NodeReport(
            node_id=node.node_id,
            tier=int(node.tier.value),
            cpu_vcpu=node.cpu_vcpu,
            ram_mb=node.ram_mb,
            disk_gb=node.disk_gb,
            gpu_available=node.gpu_available,
            bandwidth_mbps=node.bandwidth_mbps,
            region=node.region,
            availability=node.avg_uptime_percent,
            latency_p95_ms=node.latency_p95_ms or 0.0,
            reputation=node.reputation_score + avg_delta,
            tasks_completed=node.tasks_completed,
            tasks_failed=node.tasks_failed,
            is_online=node.is_online,
            last_heartbeat=node.last_heartbeat.isoformat() if node.last_heartbeat else None,
        )


class ReputationEngine:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def apply_event(self, event: ReputationUpdateRequest) -> float:
        result = await self.db.execute(select(Node).where(Node.node_id == event.node_id))
        node = result.scalar_one_or_none()
        if not node:
            raise ValueError(f"Unknown node: {event.node_id}")

        delta = event.score_delta
        node.reputation_score = max(0.0, min(100.0, node.reputation_score + delta))

        if event.event_type == "task_completed":
            node.tasks_completed += 1
        elif event.event_type == "task_failed":
            node.tasks_failed += 1
        elif event.event_type == "malicious_report":
            node.malicious_reports_received += 1

        evt = ReputationEvent(
            node_id=node.id,
            event_type=event.event_type,
            score_delta=event.score_delta,
            evidence_uri=event.evidence_uri,
        )
        self.db.add(evt)
        await self.db.commit()
        logger.info("reputation_event", node_id=node.node_id, event=event.event_type, delta=delta)
        return node.reputation_score

    async def get_reputation(self, node_id: str) -> float:
        result = await self.db.execute(select(Node).where(Node.node_id == node_id))
        node = result.scalar_one_or_none()
        return node.reputation_score if node else 0.0


def _fingerprint(public_key_pem: str) -> str:
    import hashlib, base64
    raw = public_key_pem.replace("\n", "").encode()
    return hashlib.sha256(raw).hexdigest()[:16]
