from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NodeTier(str, Enum):
    TIER_1 = "1"
    TIER_2 = "2"
    TIER_3 = "3"
    TIER_4 = "4"
    TIER_5 = "5"

    @classmethod
    def classify(cls, vcpu: int, ram_gb: int, has_gpu: bool) -> "NodeTier":
        if has_gpu and vcpu >= 16 and ram_gb >= 32:
            return cls.TIER_5
        if vcpu >= 8 and ram_gb >= 16:
            return cls.TIER_4
        if vcpu >= 4 and ram_gb >= 8:
            return cls.TIER_3
        if vcpu >= 2 and ram_gb >= 4:
            return cls.TIER_2
        return cls.TIER_1


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    tier: Mapped[NodeTier] = mapped_column(String(1), nullable=False, default=NodeTier.TIER_2)

    # Resource snapshot (latest)
    cpu_vcpu: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_available: Mapped[bool] = mapped_column(Boolean, default=False)
    gpu_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gpu_vram_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bandwidth_mbps: Mapped[float] = mapped_column(Float, nullable=False)
    has_ipv6: Mapped[bool] = mapped_column(Boolean, default=False)
    has_static_ip: Mapped[bool] = mapped_column(Boolean, default=False)

    # Region
    region: Mapped[str] = mapped_column(String(64), index=True)
    country_alpha2: Mapped[str] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(64))

    # Availability / health
    avg_uptime_percent: Mapped[float] = mapped_column(Float, nullable=False, default=99.0)
    latency_p95_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Reputation
    reputation_score: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    tasks_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    malicious_reports_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Storage
    supported_capabilities: Mapped[dict] = mapped_column(JSONB, default=dict)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    heartbeats: Mapped[list[NodeHeartbeatRecord]] = relationship(back_populates="node", cascade="all, delete-orphan")
    tasks: Mapped[list[Task]] = relationship(back_populates="assigned_node")


class NodeHeartbeatRecord(Base):
    __tablename__ = "node_heartbeats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    cpu_usage_percent: Mapped[float] = mapped_column(Float, nullable=False)
    ram_usage_percent: Mapped[float] = mapped_column(Float, nullable=False)
    disk_usage_percent: Mapped[float] = mapped_column(Float, nullable=False)
    active_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True)

    node: Mapped[Node] = relationship(back_populates="heartbeats")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Submitter / identity
    submitter_node_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    app_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    workload_type: Mapped[str] = mapped_column(String(16), nullable=False, default="cpu")
    estimated_duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    compute_requirements: Mapped[dict] = mapped_column(JSONB, default=dict)
    data_inputs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    code_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Scheduling results
    required_tier: Mapped[NodeTier | None] = mapped_column(String(1), nullable=True)
    assigned_node_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=True)
    assigned_node: Mapped[Node | None] = relationship(back_populates="tasks")

    allowed_regions: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    preferred_price: Mapped[float] = mapped_column(Float, nullable=False)

    payment_offer: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Execution lifecycle
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    result_cid: Mapped[str | None] = mapped_column(String(256), nullable=True)
    output_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Verification
    verification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    verifying_nodes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    consensus_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    score_delta: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
