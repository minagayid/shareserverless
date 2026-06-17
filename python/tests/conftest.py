"""Shared pytest fixtures for ShareServerless tests."""
from __future__ import annotations

import hashlib
import structlog
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.schemas import (
    AvailabilityProfile,
    NodeHeartbeat,
    NodeRegistrationRequest,
    ResourceProfiles,
)

logger = structlog.get_logger(__name__)

# Shared test constants
SAMPLE_PUBLIC_KEY = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzF7u0BBFUwMZ8aZ1NFxl\n"
    "loQvIIKJQ6TFBnDQdfF1QsNhOtbC6DqnDcbxkhBtUkcBFlWclqscSPLTQASzGcbXmC\n"
    "3RFAjQn3zF5M0SHTb8XPZ0k9lBbRtN+rFJOIat4Or7W6LW/xYdCW5ZfqIYhK0GLIM\n"
    "zJ8T5wN6SSPQPyMNmFxzGbOJAZZfRfHJCXuIygH3oHTnMFvg8R8ZF5fxZtNZPBSIb\n"
    "nWcwgaBjFOEjDPbTzkp4W9FqvLO5BNqsi5mQd9LgHsY8kCCln2Kuk0Xb0qxJwDlFY\n"
    "T8zpM7UQnH7xn1y3NNyBNZ2KucqgUCYbMdJmRAWExC5djA0P+4RJEEDwQIDAQAB\n"
    "-----END PUBLIC KEY-----\n"
)


def _fingerprint(public_key_pem: str) -> str:
    """Derive a deterministic fingerprint from an RSA public key PEM."""
    raw = public_key_pem.replace("\n", "").encode()
    return hashlib.sha256(raw).hexdigest()[:16]


SAMPLE_NODE_ID: str = _fingerprint(SAMPLE_PUBLIC_KEY)


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine (sync) for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an in-memory async SQLite session (async) for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncSessionLocal() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def sample_node_req() -> NodeRegistrationRequest:
    return NodeRegistrationRequest(
        public_key_pem=SAMPLE_PUBLIC_KEY,
        resource_profile=ResourceProfiles(
            cpu_vcpu=4,
            cpu_model="x86_64",
            ram_mb=8192,
            disk_gb=256,
            bandwidth_mbps=500.0,
        ),
        availability=AvailabilityProfile(
            avg_uptime_percent=99.2,
            latency_ms_to_home=45.0,
            region="us-east-1",
            country_alpha2="US",
            timezone="America/New_York",
        ),
    )


@pytest.fixture
def sample_node_req_gpu() -> NodeRegistrationRequest:
    """A high-end GPU-capable node registration request."""
    return NodeRegistrationRequest(
        public_key_pem=SAMPLE_PUBLIC_KEY + "X",  # unique fingerprint
        resource_profile=ResourceProfiles(
            cpu_vcpu=16,
            cpu_model="x86_64",
            ram_mb=32768,
            disk_gb=1024,
            bandwidth_mbps=2000.0,
            gpu_available=True,
            gpu_model="RTX 4090",
            gpu_vram_mb=24576,
        ),
        availability=AvailabilityProfile(
            avg_uptime_percent=99.9,
            latency_ms_to_home=8.0,
            region="us-west-2",
            country_alpha2="US",
            timezone="America/Los_Angeles",
        ),
    )


@pytest.fixture
def heartbeat_for_node() -> NodeHeartbeat:
    return NodeHeartbeat(
        node_id=SAMPLE_NODE_ID,
        timestamp=datetime.now(timezone.utc).isoformat(),
        cpu_usage_percent=30.0,
        ram_usage_percent=55.0,
        disk_usage_percent=10.0,
        active_tasks=1,
        is_healthy=True,
    )
