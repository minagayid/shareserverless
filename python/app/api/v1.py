from __future__ import annotations

import structlog
from datetime import datetime, timezone
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.database import Node, Task
from app.models.schemas import (
    GovernanceProposal,
    NodeHeartbeat,
    NodeRegistrationRequest,
    NodeReport,
    ReputationUpdateRequest,
    TaskAllocation,
    TaskSubmission,
    TaskVerificationResult,
    VoteCast,
)
from app.services.discovery import NodeRegistry, NodeDiscoveryError, ReputationEngine
from app.services.governance import GovernanceService, Telemetry
from app.services.scheduler import IntelligentScheduler, SchedulingError, Orchestrator
from app.services.storage import StorageCoordinator
from app.services.verification import VerificationService

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Nodes ──────────────────────────────────────────────────────────────────────


@router.post("/nodes/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_node(
    req: NodeRegistrationRequest,
    session: AsyncSession = Depends(get_session),
):
    registry = NodeRegistry(session)
    try:
        node = await registry.register_node(req)
    except NodeDiscoveryError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"node_id": node.node_id, "tier": node.tier.value, "fingerprint": node.fingerprint}


@router.get("/nodes", response_model=list[dict])
async def list_nodes(
    tier: int | None = None,
    region: str | None = None,
    online_only: bool = False,
    session: AsyncSession = Depends(get_session),
):
    registry = NodeRegistry(session)
    q = select(Node)
    if tier:
        q = q.where(Node.tier == str(tier))
    if region:
        q = q.where(Node.region == region)
    if online_only:
        q = q.where(Node.is_online == True)
    result = await session.execute(q)
    nodes = result.scalars().all()
    return [
        {
            "node_id": n.node_id,
            "tier": n.tier.value,
            "region": n.region,
            "reputation": n.reputation_score,
            "is_online": n.is_online,
            "cpu_vcpu": n.cpu_vcpu,
            "ram_mb": n.ram_mb,
            "gpu_available": n.gpu_available,
        }
        for n in nodes
    ]


@router.get("/nodes/{node_id}", response_model=NodeReport)
async def get_node(node_id: str, session: AsyncSession = Depends(get_session)):
    registry = NodeRegistry(session)
    report = await registry.get_node_report(node_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return report


@router.post(
    "/nodes/heartbeat",
    status_code=status.HTTP_202_ACCEPTED,
)
async def heartbeat(
    hb: NodeHeartbeat,
    session: AsyncSession = Depends(get_session),
):
    registry = NodeRegistry(session)
    node = await registry.process_heartbeat(hb)
    if not node:
        raise HTTPException(status_code=404, detail="Node unknown")
    return {"status": "accepted", "node_id": node.node_id, "is_online": node.is_online}


# ── Tasks ──────────────────────────────────────────────────────────────────────


@router.post("/tasks", response_model=TaskAllocation, status_code=status.HTTP_201_CREATED)
async def submit_task(
    task: TaskSubmission,
    session: AsyncSession = Depends(get_session),
):
    registry = NodeRegistry(session)
    orch = Orchestrator(session, registry)
    try:
        task_id = await orch.submit_task(task)
    except SchedulingError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    result = await session.execute(select(Task).where(Task.task_id == task_id))
    created = result.scalar_one_or_none()
    if not created:
        raise HTTPException(status_code=500, detail="Task record not persisted")

    return TaskAllocation(
        task_id=created.task_id,
        node_id=created.assigned_node.node_id if created.assigned_node else "",
        node_tier=int(created.assigned_node.tier.value) if created.assigned_node else 3,
        node_region=created.assigned_node.region if created.assigned_node else "",
        estimated_start=created.created_at.isoformat(),
        estimated_completion="",
        price=task.payment_offer,
        status=created.status,
    )


@router.get("/tasks/{task_id}", response_model=dict)
async def task_status(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Task).where(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "result_cid": task.result_cid,
        "assigned_node_id": task.assigned_node_id,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat(),
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


@router.post("/tasks/{task_id}/verify", response_model=TaskVerificationResult)
async def verify_task(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Task).where(Task.task_id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.verification_enabled:
        raise HTTPException(status_code=400, detail="Verification not enabled for this task")

    registry = NodeRegistry(session)
    service = VerificationService(session, registry)
    if not task.verifying_nodes:
        await service.enqueue(task)

    # Simulated consensus: in production, verifier nodes return signed result hashes.
    fake_outputs = [
        {"result_hash": "sha256:abc123", "output_cid": f"cid-{task.task_id}"},
        {"result_hash": "sha256:abc123", "output_cid": f"cid-{task.task_id}"},
    ]
    return await service.record_consensus(
        task=task,
        outputs=fake_outputs,
        verifier_ids=task.verifying_nodes or [],
    )


# ── Reputation ─────────────────────────────────────────────────────────────────


@router.post("/reputation/event")
async def reputation_event(
    evt: ReputationUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    engine = ReputationEngine(session)
    try:
        new_score = await engine.apply_event(evt)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"node_id": evt.node_id, "new_score": new_score}


@router.get("/reputation/{node_id}")
async def reputation(node_id: str, session: AsyncSession = Depends(get_session)):
    engine = ReputationEngine(session)
    score = await engine.get_reputation(node_id)
    return {"node_id": node_id, "reputation": score}


# ── Storage ────────────────────────────────────────────────────────────────────


@router.get("/storage/chunks/{cid}/replicas")
async def locate_chunks(cid: str, min_replicas: int = 3, session: AsyncSession = Depends(get_session)):
    coordinator = StorageCoordinator(session)
    return await coordinator.locate_chunks(content_cid=cid, min_replicas=min_replicas)


@router.get("/storage/health")
async def storage_health(session: AsyncSession = Depends(get_session)):
    coordinator = StorageCoordinator(session)
    return await coordinator.get_health_snapshot()


# ── Governance ─────────────────────────────────────────────────────────────────


@router.post("/governance/proposals", status_code=status.HTTP_201_CREATED)
async def submit_proposal(proposal: GovernanceProposal):
    svc = GovernanceService()
    pid = await svc.submit_proposal(proposal.model_dump())
    return {"proposal_id": pid}


@router.post("/governance/proposals/{proposal_id}/vote")
async def cast_vote(proposal_id: str, vote: VoteCast):
    svc = GovernanceService()
    await svc.cast_vote(proposal_id, vote.voter, vote.choice, vote.signature)
    return {"status": "recorded", "proposal_id": proposal_id}


@router.get("/governance/proposals/active")
async def active_proposals():
    svc = GovernanceService()
    return await svc.list_active_proposals()
