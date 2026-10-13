import pytest

from app.commitments import (
    CommitmentRegistry,
    CommitmentStatus,
    Reversibility,
)


def test_register_commitment():
    registry = CommitmentRegistry()

    commitment = registry.register(
        commitment_id="SHIPMENT_001",
        action_id="A_SHIP",
        originating_belief_ids={"B_INVENTORY"},
        description="Create shipment",
        reversibility=Reversibility.COMPENSABLE,
    )

    assert commitment.commitment_id == "SHIPMENT_001"
    assert commitment.status == CommitmentStatus.ACTIVE


def test_find_commitments_by_belief():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="C1",
        action_id="A1",
        originating_belief_ids={"B1"},
        description="Reserve inventory",
    )

    registry.register(
        commitment_id="C2",
        action_id="A2",
        originating_belief_ids={"B2"},
        description="Prepare report",
    )

    results = registry.find_by_belief("B1")

    assert [item.commitment_id for item in results] == ["C1"]


def test_mark_commitment_inconsistent():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="C1",
        action_id="A1",
        originating_belief_ids={"B1"},
        description="Reserve inventory",
    )

    commitment = registry.mark_inconsistent(
        "C1",
        "Product is no longer available",
    )

    assert commitment.status == CommitmentStatus.INCONSISTENT


def test_reconciliation_requires_verification():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="C1",
        action_id="A1",
        originating_belief_ids={"B1"},
        description="Reserve inventory",
    )

    with pytest.raises(ValueError):
        registry.mark_reconciled("C1", "")


def test_successful_reconciliation_records_evidence():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="C1",
        action_id="A1",
        originating_belief_ids={"B1"},
        description="Reserve inventory",
    )

    commitment = registry.mark_reconciled(
        "C1",
        "Inventory service confirmed reservation released",
    )

    assert commitment.status == CommitmentStatus.RECONCILED

    assert (
        commitment.metadata["verification_evidence"]
        == "Inventory service confirmed reservation released"
    )


def test_duplicate_commitment_is_rejected():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="C1",
        action_id="A1",
        originating_belief_ids={"B1"},
        description="Reserve inventory",
    )

    with pytest.raises(ValueError):
        registry.register(
            commitment_id="C1",
            action_id="A2",
            originating_belief_ids={"B2"},
            description="Create shipment",
        )