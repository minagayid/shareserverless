from __future__ import annotations

import hashlib
import structlog
from typing import Any

import httpx
from fastapi import Request

from app.core.config import settings


logger = structlog.get_logger(__name__)


class GovernanceError(Exception):
    pass


class GovernanceService:
    def __init__(self) -> None:
        self.proposals: dict[str, dict[str, Any]] = {}
        self.votes: dict[str, list[dict[str, Any]]] = {}

    async def submit_proposal(self, proposal: dict[str, Any]) -> str:
        proposal_id = _hash(f"{proposal['proposer']}:{proposal['title']}:{_now()}")
        self.proposals[proposal_id] = proposal
        self.votes[proposal_id] = []
        logger.info("proposal_submitted", proposal_id=proposal_id, proposer=proposal["proposer"])
        return proposal_id

    async def cast_vote(self, proposal_id: str, voter: str, choice: str, signature: str = "") -> None:
        if proposal_id not in self.proposals:
            raise GovernanceError(f"Unknown proposal: {proposal_id}")
        self.votes[proposal_id].append({"voter": voter, "choice": choice, "signature": signature})
        logger.info("vote_cast", proposal_id=proposal_id, voter=voter, choice=choice)

    async def get_tally(self, proposal_id: str) -> dict[str, int]:
        votes = self.votes.get(proposal_id, [])
        from collections import Counter
        counts = Counter(v["choice"] for v in votes)
        return dict(counts)

    async def list_active_proposals(self) -> list[dict[str, Any]]:
        now = _now()
        return [
            {**p, "proposal_id": pid}
            for pid, p in self.proposals.items()
            if p.get("voting_ends_at", now) > now
        ]


class Telemetry:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append({
            "ts": _now(),
            "type": event_type,
            "payload": payload,
        })

    async def export_to_observability(self, endpoint: str, bearer: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                endpoint,
                json=self.events[-1000:],  # tail
                headers={"Authorization": f"Bearer {bearer}"},
                timeout=5,
            )


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:24]


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
