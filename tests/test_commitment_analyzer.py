import pytest

from app.commitments import (
    CommitmentRegistry,
    CommitmentStatus,
    Reversibility,
)
from app.commitment_analyzer import CommitmentImpactAnalyzer


@pytest.fixture
def setup_analyzer():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="shipping-001",
        action_id="action-001",
        originating_belief_ids={"belief-in-stock"},
        description="Shipping label created",
        reversibility=Reversibility.COMPENSABLE,
    )

    registry.register(
        commitment_id="payment-001",
        action_id="action-002",
        originating_belief_ids={"belief-payment"},
        description="Payment submitted",
        reversibility=Reversibility.IRREVERSIBLE,
    )

    registry.register(
        commitment_id="email-001",
        action_id="action-003",
        originating_belief_ids={"belief-customer"},
        description="Customer notification sent",
        reversibility=Reversibility.UNKNOWN,
    )

    registry.register(
        commitment_id="shipping-002",
        action_id="action-004",
        originating_belief_ids={"unrelated-belief"},
        description="Unrelated shipment",
        reversibility=Reversibility.REVERSIBLE,
    )

    return registry, CommitmentImpactAnalyzer(registry)


def test_detects_commitments_affected_by_changed_belief(setup_analyzer):
    _, analyzer = setup_analyzer

    report = analyzer.analyze({"belief-in-stock"})

    assert report.affected_commitment_ids == ["shipping-001"]
    assert report.inconsistent_commitment_ids == ["shipping-001"]


def test_irreversible_commitment_requires_review(setup_analyzer):
    registry, analyzer = setup_analyzer

    report = analyzer.analyze({"belief-payment"})

    assert report.review_required_ids == ["payment-001"]
    assert (
        registry.get("payment-001").status
        == CommitmentStatus.REQUIRES_REVIEW
    )


def test_unknown_reversibility_requires_review(setup_analyzer):
    registry, analyzer = setup_analyzer

    report = analyzer.analyze({"belief-customer"})

    assert report.review_required_ids == ["email-001"]
    assert (
        registry.get("email-001").status
        == CommitmentStatus.REQUIRES_REVIEW
    )


def test_unrelated_commitment_remains_unaffected(setup_analyzer):
    registry, analyzer = setup_analyzer

    report = analyzer.analyze({"belief-in-stock"})

    assert "shipping-002" in report.unaffected_commitment_ids
    assert (
        registry.get("shipping-002").status
        == CommitmentStatus.ACTIVE
    )


def test_multiple_belief_changes_are_supported(setup_analyzer):
    _, analyzer = setup_analyzer

    report = analyzer.analyze(
        {"belief-in-stock", "belief-payment"}
    )

    assert set(report.affected_commitment_ids) == {
        "shipping-001",
        "payment-001",
    }


def test_empty_belief_changes_are_rejected(setup_analyzer):
    _, analyzer = setup_analyzer

    with pytest.raises(ValueError):
        analyzer.analyze(set())