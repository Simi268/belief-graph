from unittest.mock import Mock

from app.commitments import (
    CommitmentRegistry,
    CommitmentStatus,
    Reversibility,
)
from app.commitment_analyzer import CommitmentImpactAnalyzer


def test_recovery_engine_uses_shared_commitment_registry():
    """RecoveryEngine should retain the registry supplied by its caller."""
    from app.recovery import RecoveryEngine

    agent = Mock()
    agent.graph = Mock()

    registry = CommitmentRegistry()
    engine = RecoveryEngine(
        agent,
        commitment_registry=registry,
    )

    assert engine.commitment_registry is registry
    assert isinstance(
        engine.commitment_analyzer,
        CommitmentImpactAnalyzer,
    )


def test_commitment_analysis_updates_registry_status():
    """Changed beliefs should update associated commitment statuses."""
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="shipment-001",
        action_id="action-001",
        originating_belief_ids={"belief-stock"},
        description="Shipment reservation",
        reversibility=Reversibility.COMPENSABLE,
    )

    analyzer = CommitmentImpactAnalyzer(registry)
    report = analyzer.analyze({"belief-stock"})

    assert report.affected_commitment_ids == ["shipment-001"]
    assert (
        registry.get("shipment-001").status
        == CommitmentStatus.INCONSISTENT
    )


def test_irreversible_commitment_is_flagged_for_review():
    """Irreversible external effects must require human review."""
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="payment-001",
        action_id="action-payment",
        originating_belief_ids={"belief-payment"},
        description="Payment submitted",
        reversibility=Reversibility.IRREVERSIBLE,
    )

    report = CommitmentImpactAnalyzer(registry).analyze(
        {"belief-payment"}
    )

    assert report.review_required_ids == ["payment-001"]
    assert (
        registry.get("payment-001").status
        == CommitmentStatus.REQUIRES_REVIEW
    )