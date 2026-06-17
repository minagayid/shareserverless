import pytest

from app.models.schemas import (
    NodeRegistrationRequest,
    ResourceProfiles,
    AvailabilityProfile,
    NodeHeartbeat,
    ReputationUpdateRequest,
    TaskSubmission,
)


def test_resource_profile_defaults() -> None:
    rp = ResourceProfiles(cpu_vcpu=2, ram_mb=4096, disk_gb=64, bandwidth_mbps=100.0)
    assert rp.cpu_vcpu == 2
    assert rp.gpu_available is False
    assert rp.gpu_vram_mb == 0


def test_resource_profile_gpu() -> None:
    rp = ResourceProfiles(
        cpu_vcpu=16, cpu_model="x86_64", ram_mb=32768, disk_gb=1024,
        bandwidth_mbps=2000.0, gpu_available=True, gpu_model="RTX 4090", gpu_vram_mb=24576,
    )
    assert rp.gpu_available is True
    assert rp.gpu_vram_mb == 24576


def test_node_registration_request_construction() -> None:
    req = NodeRegistrationRequest(
        public_key_pem=_pem(),
        resource_profile=ResourceProfiles(
            cpu_vcpu=4, ram_mb=8192, disk_gb=256, bandwidth_mbps=500.0
        ),
        availability=AvailabilityProfile(
            avg_uptime_percent=99.2,
            latency_ms_to_home=45.0,
            region="us-east-1",
            country_alpha2="US",
            timezone="America/New_York",
        ),
    )
    assert req.availability.region == "us-east-1"


def test_node_heartbeat_construction() -> None:
    hb = NodeHeartbeat(
        node_id="node-abc",
        timestamp="2025-01-01T00:00:00Z",
        cpu_usage_percent=55.0,
        ram_usage_percent=60.0,
        disk_usage_percent=30.0,
        active_tasks=2,
    )
    assert hb.cpu_usage_percent == 55.0
    assert hb.is_healthy is True


def test_heartbeat_usage_out_of_range() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        NodeHeartbeat(
            node_id="node-abc",
            timestamp="2025-01-01T00:00:00Z",
            cpu_usage_percent=150.0,
            ram_usage_percent=0.0,
            disk_usage_percent=0.0,
            active_tasks=0,
        )


def test_reputation_update_request_validation() -> None:
    evt = ReputationUpdateRequest(node_id="node-1", event_type="task_completed", score_delta=5.0)
    assert evt.event_type == "task_completed"


def test_task_submission_defaults() -> None:
    task = TaskSubmission(app_type="static", workload_type="cpu", estimated_duration_s=10)
    assert task.app_type == "static"
    assert task.payment_offer == 0.0


def _pem() -> str:
    return (
        "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzF7u0BBFUwMZ8aZ1NFxl\n"
        "loQvIIKJQ6TFBnDQdfF1QsNhOtbC6DqnDcbxkhBtUkcBFlWclqscSPLTQASzGcbXmC\n"
        "3RFAjQn3zF5M0SHTb8XPZ0k9lBbRtN+rFJOIat4Or7W6LW/xYdCW5ZfqIYhK0GLIM\n"
        "zJ8T5wN6SSPQPyMNmFxzGbOJAZZfRfHJCXuIygH3oHTnMFvg8R8ZF5fxZtNZPBSIb\n"
        "nWcwgaBjFOEjDPbTzkp4W9FqvLO5BNqsi5mQd9LgHsY8kCCln2Kuk0Xb0qxJwDlFY\n"
        "T8zpM7UQnH7xn1y3NNyBNZ2KucqgUCYbMdJmRAWExC5djA0P+4RJEEDwQIDAQAB\n"
        "-----END PUBLIC KEY-----\n"
    )
