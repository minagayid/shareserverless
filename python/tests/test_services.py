"""Tests for the service layer."""
from __future__ import annotations

import structlog

import pytest

from app.models.schemas import (
    AvailabilityProfile,
    NodeRegistrationRequest,
    NodeHeartbeat,
    ReputationUpdateRequest,
    ResourceProfiles,
    TaskSubmission,
)
from app.services.discovery import NodeRegistry, ReputationEngine, NodeDiscoveryError
from app.services.scheduler import IntelligentScheduler

logger = structlog.get_logger(__name__)


# NOTE: fixtures (db_session, sample_node_req, heartbeat_for_node, SAMPLE_NODE_ID)
# are provided by tests/conftest.py and injected by pytest.

@pytest.mark.asyncio
async def test_register_and_list_nodes(db_session, sample_node_req) -> None:
    registry = NodeRegistry(db_session)
    node = await registry.register_node(sample_node_req)
    assert node.node_id  # non-empty string assigned as fingerprint
    online = await registry.get_online_nodes()
    assert any(n.node_id == node.node_id for n in online)


@pytest.mark.asyncio
async def test_duplicate_registration_rejected(db_session, sample_node_req) -> None:
    registry = NodeRegistry(db_session)
    req = NodeRegistrationRequest(
        # Different PEM so fingerprint differs.
        public_key_pem=_alt_pem(),
        resource_profile=ResourceProfiles(
            cpu_vcpu=4, cpu_model="x86_64", ram_mb=8192, disk_gb=256, bandwidth_mbps=100.0,
        ),
        availability=AvailabilityProfile(
            avg_uptime_percent=99.0, latency_ms_to_home=30.0,
            region="eu-west-1", country_alpha2="DE", timezone="Europe/Berlin",
        ),
    )
    await registry.register_node(req)
    with pytest.raises(NodeDiscoveryError):
        await registry.register_node(req)


@pytest.mark.asyncio
async def test_heartbeat_updates_node(db_session, sample_node_req, heartbeat_for_node) -> None:
    registry = NodeRegistry(db_session)
    node = await registry.register_node(sample_node_req)
    # Ensure the heartbeat refers to the registered node id.
    hb = NodeHeartbeat(
        node_id=node.node_id,
        timestamp=_now(),
        cpu_usage_percent=20.0,
        ram_usage_percent=40.0,
        disk_usage_percent=12.0,
        active_tasks=1,
        is_healthy=True,
    )
    updated = await registry.process_heartbeat(hb)
    assert updated is not None
    assert updated.is_online is True
    assert updated.last_heartbeat is not None


@pytest.mark.asyncio
async def test_heartbeat_unknown_node_returns_none(db_session, heartbeat_for_node) -> None:
    registry = NodeRegistry(db_session)
    result = await registry.process_heartbeat(heartbeat_for_node)
    assert result is None


@pytest.mark.asyncio
async def test_reputation_engine(db_session, sample_node_req) -> None:
    registry = NodeRegistry(db_session)
    node = await registry.register_node(sample_node_req)
    engine = ReputationEngine(db_session)
    new_score = await engine.apply_event(
        ReputationUpdateRequest(node_id=node.node_id, event_type="task_completed", score_delta=10.0),
    )
    assert new_score == pytest.approx(60.0)


@pytest.mark.asyncio
async def test_scheduler_selects_node(db_session, sample_node_req) -> None:
    registry = NodeRegistry(db_session)
    for _ in range(3):
        await registry.register_node(sample_node_req)
    scheduler = IntelligentScheduler(db_session)
    task = TaskSubmission(
        app_type="static",
        workload_type="cpu",
        estimated_duration_s=10,
        compute_requirements={"cpu_vcpu": 1, "ram_mb": 512},
    )
    candidate = await scheduler.select(task)
    assert candidate is not None
    assert candidate.total_score > 0


@pytest.mark.asyncio
async def test_scheduler_rejects_gpu_task_when_no_gpu_nodes(db_session, sample_node_req) -> None:
    """Nodes in fixture have no GPU, so a GPU task should yield no candidate."""
    registry = NodeRegistry(db_session)
    await registry.register_node(sample_node_req)
    scheduler = IntelligentScheduler(db_session)
    task = TaskSubmission(
        app_type="ai_inference",
        workload_type="gpu",
        estimated_duration_s=60,
        compute_requirements={"gpu_vram_mb": 2048},
    )
    result = await scheduler.select(task)
    # No GPU node registered -> no candidate
    assert result is None


@pytest.mark.asyncio
async def test_scheduler_gpu_task_with_gpu_node(db_session, sample_node_req_gpu, sample_node_req) -> None:
    """If a GPU node is registered, a GPU task should match it."""
    registry = NodeRegistry(db_session)
    await registry.register_node(sample_node_req)
    await registry.register_node(sample_node_req_gpu)
    scheduler = IntelligentScheduler(db_session)
    task = TaskSubmission(
        app_type="ai_inference",
        workload_type="gpu",
        estimated_duration_s=60,
        compute_requirements={"gpu_vram_mb": 2048},
    )
    result = await scheduler.select(task)
    assert result is not None


def _alt_pem() -> str:
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1a2CCzKNZWn/Q3rKCEQB\n"
        "aqFvzPvSZe5CchMd7adsuUn06TfzRDaG5SIBz/qP4bNm3O1rV0/8zTlTJAfv1XAZ\n"
        "-----END PUBLIC KEY-----\n"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
