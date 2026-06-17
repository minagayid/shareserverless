from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Node, NodeTier, Task, ReputationEvent
from app.models.schemas import TaskVerificationResult
from app.services.discovery import NodeRegistry, NodeDiscoveryError


logger = structlog.get_logger(__name__)


class VerificationService:
    def __init__(self, db: AsyncSession, registry: NodeRegistry) -> None:
        self.db = db
        self.registry = registry

    async def enqueue(self, task: Task) -> list[str]:
        tier = NodeTier(task.required_tier) if task.required_tier else NodeTier.TIER_3
        nodes = await self.registry.get_online_nodes(tier=tier)

        # Avoid verified node if it's the executed node
        candidate_nodes = [n for n in nodes if n.node_id != task.assigned_node_id][:4]
        verifiers = candidate_nodes[:2]
        verifier_ids = [n.node_id for n in verifiers]

        task.verifying_nodes = verifier_ids
        task.status = "verifying"
        await self.db.commit()
        logger.info("verification_enqueued", task_id=task.task_id, verifiers=verifier_ids)
        return verifier_ids

    async def record_consensus(self, task: Task, outputs: list[dict], verifier_ids: list[str]) -> TaskVerificationResult:
        if len(outputs) < 2:
            return TaskVerificationResult(
                task_id=task.task_id,
                verified=False,
                consensus_percent=0.0,
                verifying_nodes=verifier_ids,
                output_cid=None,
                error="Insufficient verifier responses",
            )

        # Hash-based consensus
        hashes = [o.get("result_hash") for o in outputs]
        from collections import Counter
        counts = Counter(hashes)
        most_common_hash, most_common_count = counts.most_common(1)[0]
        consensus_pct = most_common_count / len(hashes) * 100

        verified = consensus_pct >= 80.0
        task.status = "completed" if verified else "failed"
        task.consensus_result = {"consensus_pct": consensus_pct, "authoritative_hash": most_common_hash}
        task.verified_at = datetime.now(timezone.utc)
        task.result_cid = outputs[0].get("output_cid")
        await self.db.commit()

        return TaskVerificationResult(
            task_id=task.task_id,
            verified=verified,
            consensus_percent=consensus_pct,
            verifying_nodes=verifier_ids,
            output_cid=task.result_cid,
            error=None,
        )
