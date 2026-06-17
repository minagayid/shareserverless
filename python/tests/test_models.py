from __future__ import annotations

import structlog

from app.models.database import NodeTier


logger = structlog.get_logger(__name__)


def test_node_tier_classification() -> None:
    assert NodeTier.classify(vcpu=1, ram_gb=2, has_gpu=False) == NodeTier.TIER_1
    assert NodeTier.classify(vcpu=2, ram_gb=4, has_gpu=False) == NodeTier.TIER_2
    assert NodeTier.classify(vcpu=4, ram_gb=8, has_gpu=False) == NodeTier.TIER_3
    assert NodeTier.classify(vcpu=8, ram_gb=16, has_gpu=False) == NodeTier.TIER_4
    assert NodeTier.classify(vcpu=16, ram_gb=64, has_gpu=True) == NodeTier.TIER_5


def test_max_tier_boundaries() -> None:
    assert NodeTier.classify(vcpu=64, ram_gb=256, has_gpu=True) == NodeTier.TIER_5
