from __future__ import annotations

from dataclasses import dataclass
import structlog
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Node, NodeTier
from app.models.schemas import TaskSubmission
from app.services.discovery import NodeRegistry
from app.core.metrics import record_task


@dataclass
class Candidate:
    node_id: str
    tier: int
    reputation: float
    bandwidth_mbps: float
    distance_score: float
    affinity_score: float
    total_score: float
    ram_mb: int
    gpu_available: bool
    region: str


class SchedulingError(Exception):
    pass


class IntelligentScheduler:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def select(self, task: TaskSubmission) -> Candidate | None:
        candidates_query = select(Node).where(Node.is_online == True)
        if task.required_tier:
            candidates_query = candidates_query.where(Node.tier >= NodeTier(task.required_tier))

        if task.workload_type == "gpu":
            candidates_query = candidates_query.where(Node.gpu_available == True)

        if task.preferred_regions:
            candidates_query = candidates_query.where(Node.region.in_(task.preferred_regions))

        result = await self.db.execute(candidates_query)
        nodes: Sequence[Node] = result.scalars().all()

        if not nodes:
            return None

        ranked: list[Candidate] = []
        for node in nodes:
            # Skip nodes with reputation below minimum
            if node.reputation_score < 0:
                continue

            # Weighted scoring
            rep_score = node.reputation_score / 100.0 * 0.4
            latency_score = self._latency_to_score(node.latency_p95_ms or 5000) * 0.3
            res_score = self._resource_affinity(node, task) * 0.2
            price_score = 0.5 * 0.1  # simplified

            total = rep_score + latency_score + res_score + price_score
            ranked.append(
                Candidate(
                    node_id=node.node_id,
                    tier=int(node.tier.value),
                    reputation=node.reputation_score,
                    bandwidth_mbps=node.bandwidth_mbps,
                    distance_score=latency_score,
                    affinity_score=res_score,
                    total_score=total,
                    ram_mb=node.ram_mb,
                    gpu_available=node.gpu_available,
                    region=node.region,
                )
            )

        ranked.sort(key=lambda c: c.total_score, reverse=True)
        return ranked[0]

    @staticmethod
    def _latency_to_score(latency_ms: float) -> float:
        return max(0.0, 1.0 - (latency_ms / 5000.0))

    @staticmethod
    def _resource_affinity(node: Node, task: TaskSubmission) -> float:
        req = task.compute_requirements
        cpu_score = min(1.0, node.cpu_vcpu / max(1, req.get("cpu_vcpu", 1)))
        mem_score = min(1.0, node.ram_mb / max(1, req.get("ram_mb", 512)))
        disk_score = min(1.0, node.disk_gb / max(1, req.get("disk_gb", 1)))
        return (cpu_score + mem_score + disk_score) / 3.0


class Orchestrator:
    def __init__(self, db: AsyncSession, registry: NodeRegistry) -> None:
        self.db = db
        self.registry = registry
        self.scheduler = IntelligentScheduler(db)

    async def submit_task(self, task: TaskSubmission) -> str:
        candidate = await self.scheduler.select(task)
        if candidate is None:
            raise SchedulingError("No suitable online node available")

        task_id = f"task-{task.app_type[:4]}-{_short_uuid()}"
        await record_task(app_type=task.app_type, tier=candidate.tier, status="queued")
        logger.info("task_submitted", task_id=task_id, node=candidate.node_id, app=task.app_type)
        return task_id
