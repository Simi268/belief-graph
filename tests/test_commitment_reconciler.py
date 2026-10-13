import pytest

from app.commitments import (
    CommitmentRegistry,
    CommitmentStatus,
    Reversibility,
)
from app.commitment_reconciler import CommitmentReconciler


@pytest.fixture
def setup_reconciler():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="shipment-001",
        action_id="action-001",
        originating_belief_ids={"belief-stock"},
        description="Shipment reservation",
        reversibility=Reversibility.COMPENSABLE,
    )

    registry.mark_inconsistent(
        "shipment-001",
        "Inventory belief changed.",
    )

    return registry, CommitmentReconciler(registry)


def test_recommendation_does_not_execute_compensation(setup_reconciler):
    _, reconciler = setup_reconciler
    called = False

    def compensation(_commitment):
        nonlocal called
        called = True
        return {"success": True, "verification_evidence": "verified"}

    recommendation = reconciler.recommend("shipment-001")

    assert recommendation["recommendation"] == "compensate"
    assert recommendation["requires_approval"] is True
    assert called is False


def test_compensation_requires_explicit_approval(setup_reconciler):
    _, reconciler = setup_reconciler

    result = reconciler.reconcile(
        "shipment-001",
        lambda _: {
            "success": True,
            "verification_evidence": "Reservation cancelled.",
        },
    )

    assert result.status == "approval_required"


def test_successful_compensation_reconciles_commitment(setup_reconciler):
    registry, reconciler = setup_reconciler

    result = reconciler.reconcile(
        "shipment-001",
        lambda _: {
            "success": True,
            "verification_evidence": "Reservation cancellation verified.",
        },
        approved=True,
    )

    assert result.status == "reconciled"
    assert (
        registry.get("shipment-001").status
        == CommitmentStatus.RECONCILED
    )


def test_failed_compensation_does_not_reconcile_commitment(setup_reconciler):
    registry, reconciler = setup_reconciler

    result = reconciler.reconcile(
        "shipment-001",
        lambda _: {"success": False},
        approved=True,
    )

    assert result.status == "compensation_failed"
    assert (
        registry.get("shipment-001").status
        == CommitmentStatus.INCONSISTENT
    )


def test_missing_verification_does_not_reconcile_commitment(
    setup_reconciler,
):
    registry, reconciler = setup_reconciler

    result = reconciler.reconcile(
        "shipment-001",
        lambda _: {"success": True},
        approved=True,
    )

    assert result.status == "verification_required"
    assert (
        registry.get("shipment-001").status
        == CommitmentStatus.INCONSISTENT
    )


def test_irreversible_commitment_cannot_be_compensated():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="payment-001",
        action_id="action-payment",
        originating_belief_ids={"belief-payment"},
        description="Payment submitted",
        reversibility=Reversibility.IRREVERSIBLE,
    )
    registry.mark_inconsistent("payment-001", "Payment conflict.")

    reconciler = CommitmentReconciler(registry)

    result = reconciler.reconcile(
        "payment-001",
        lambda _: {
            "success": True,
            "verification_evidence": "Should not execute.",
        },
        approved=True,
    )

    assert result.status == "blocked"
    assert (
        registry.get("payment-001").status
        == CommitmentStatus.INCONSISTENT
    )


def test_compensation_exception_does_not_reconcile(setup_reconciler):
    registry, reconciler = setup_reconciler

    def failing_compensation(_):
        raise RuntimeError("External service failed")

    result = reconciler.reconcile(
        "shipment-001",
        failing_compensation,
        approved=True,
    )

    assert result.status == "compensation_failed"
    assert (
        registry.get("shipment-001").status
        == CommitmentStatus.INCONSISTENT
    )


def test_already_reconciled_commitment_is_not_compensated():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="shipment-002",
        action_id="action-002",
        originating_belief_ids={"belief-stock"},
        description="Previously reconciled shipment",
        reversibility=Reversibility.COMPENSABLE,
    )
    registry.mark_reconciled(
        "shipment-002",
        "External state verified.",
    )

    reconciler = CommitmentReconciler(registry)

    result = reconciler.reconcile(
        "shipment-002",
        lambda _: pytest.fail("Should not execute compensation"),
        approved=True,
    )

    assert result.status == "blocked"
    assert (
        registry.get("shipment-002").status
        == CommitmentStatus.RECONCILED
    )