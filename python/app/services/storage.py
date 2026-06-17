from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Node, NodeTier


logger = structlog.get_logger(__name__)


class StorageError(Exception):
    pass


class StorageCoordinator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def locate_chunks(self, content_cid: str, min_replicas: int = 3) -> list[dict]:
        """
        Find minimum N nodes that claim availability of the given content CID.
        Real implementation would RPC into each node's ContentStore RPC.
        """
        result = await self.db.execute(
            select(Node).where(Node.is_online == True, Node.disk_gb >= 10)
        )
        nodes = result.scalars().all()
        # In production, additionally filter by actual CID presence.
        return [{"node_id": n.node_id, "region": n.region, "tier": n.tier.value} for n in nodes[:min_replicas]]

    async def schedule_rebalance(self, overloaded_node_ids: Sequence[str]) -> None:
        for nid in overloaded_node_ids:
            result = await self.db.execute(select(Node).where(Node.node_id == nid))
            node = result.scalar_one_or_none()
            if node:
                logger.info("rebalance_triggered", node_id=nid, disk_pct=node.disk_gb)
                # In production: move cold chunks off node, update DHT, etc.

    async def get_health_snapshot(self) -> dict:
        result = await self.db.execute(
            select(
                Node.tier,
                func.count().label("count"),
                func.avg(Node.reputation_score).label("avg_reputation"),
                sum(Node.disk_gb).label("total_disk"),
            ).group_by(Node.tier)
        )
        rows = result.all()
        return {
            "tiers": [
                {
                    "tier": r.tier,
                    "count": r.count,
                    "avg_reputation": float(r.avg_reputation or 0),
                    "total_disk_gb": float(r.total_disk or 0),
                }
                for r in rows
            ]
        }
