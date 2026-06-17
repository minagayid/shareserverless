from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


EyeTier = Literal[1, 2, 3, 4, 5]
TIER_LABELS: dict[int, str] = {
    1: "Phone / IoT",
    2: "Low-End PC",
    3: "Mid-Range PC",
    4: "High-End PC / Workstation",
    5: "Server / Enterprise",
}


class ResourceProfiles(BaseModel):
    cpu_vcpu: int = Field(ge=1, description="Available virtual CPUs")
    cpu_model: str = Field(default="")
    ram_mb: int = Field(ge=0)
    disk_gb: int = Field(ge=0)
    gpu_available: bool = False
    gpu_model: str = Field(default="")
    gpu_vram_mb: int = Field(ge=0, default=0)
    bandwidth_mbps: float = Field(ge=0)
    has_ipv6: bool = False
    has_static_ip: bool = False


class AvailabilityProfile(BaseModel):
    avg_uptime_percent: float = Field(ge=0, le=100)
    latency_ms_to_home: float = Field(ge=0)
    region: str
    country_alpha2: str = Field(min_length=2, max_length=2)
    timezone: str


class NodeRegistrationRequest(BaseModel):
    public_key_pem: str
    resource_profile: ResourceProfiles
    availability: AvailabilityProfile
    supported_capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("public_key_pem")
    @classmethod
    def valid_rsa_key(cls, value: str) -> str:
        import base64
        try:
            raw = value.replace("\n", "").replace("-----BEGIN PUBLIC KEY-----", "").replace("-----END PUBLIC KEY-----", "")
            base64.b64decode(raw)
        except Exception:
            raise ValueError("Invalid RSA public key PEM")
        return value


class NodeReport(BaseModel):
    node_id: str
    tier: EyeTier
    cpu_vcpu: int
    ram_mb: int
    disk_gb: int
    gpu_available: bool
    bandwidth_mbps: float
    region: str
    availability: float = Field(ge=0, le=100)
    latency_p95_ms: float
    reputation: float = Field(ge=0, le=100)
    tasks_completed: int = 0
    tasks_failed: int = 0
    is_online: bool = False
    last_heartbeat: str | None = None


class TaskSubmission(BaseModel):
    app_type: Literal["static", "api", "ai_inference"] = Field(...)
    workload_type: Literal["cpu", "gpu", "cpu+gpu"] = "cpu"
    estimated_duration_s: int = Field(ge=1)
    compute_requirements: dict[str, int | float] = Field(default_factory=dict)
    data_inputs: list[str] = Field(default_factory=list, description="CIDs or URLs for inputs")
    code_uri: str | None = None
    payment_offer: float = Field(ge=0)
    required_tier: EyeTier | None = None
    preferred_regions: list[str] = Field(default_factory=list)
    verification_enabled: bool = True
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class TaskAllocation(BaseModel):
    task_id: str
    node_id: str
    node_tier: EyeTier
    node_region: str
    estimated_start: str
    estimated_completion: str
    price: float
    status: Literal["queued", "running", "completed", "failed", "verifying"]


class TaskVerificationResult(BaseModel):
    task_id: str
    verified: bool
    consensus_percent: float
    verifying_nodes: list[str]
    output_cid: str | None
    error: str | None


class NodeHeartbeat(BaseModel):
    node_id: str
    timestamp: str
    cpu_usage_percent: float = Field(ge=0, le=100)
    ram_usage_percent: float = Field(ge=0, le=100)
    disk_usage_percent: float = Field(ge=0, le=100)
    active_tasks: int
    is_healthy: bool = True


class ReputationUpdateRequest(BaseModel):
    node_id: str
    event_type: Literal["task_completed", "task_failed", "malicious_report", "verified", "heartbeat_missed"]
    score_delta: float
    evidence_uri: str | None = None


class GovernanceProposal(BaseModel):
    proposal_id: str
    proposer: str
    title: str
    description: str
    category: Literal["parameter_change", "maintainer_addition", "policy_update", "emergency"]
    changes: dict[str, str | int | float | bool]
    voting_starts_at: str
    voting_ends_at: str
    required_threshold: float = Field(ge=0, le=100, default=66.0)


class VoteCast(BaseModel):
    proposal_id: str
    voter: str
    choice: Literal["for", "against", "abstain"]
    signature: str
