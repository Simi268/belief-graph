"""Track external commitments created by AI agent actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CommitmentStatus(str, Enum):
    ACTIVE = "active"
    INCONSISTENT = "inconsistent"
    REQUIRES_REVIEW = "requires_review"
    RECONCILED = "reconciled"


class Reversibility(str, Enum):
    REVERSIBLE = "reversible"
    COMPENSABLE = "compensable"
    IRREVERSIBLE = "irreversible"
    UNKNOWN = "unknown"


@dataclass
class Commitment:
    commitment_id: str
    action_id: str
    originating_belief_ids: set[str]

    description: str

    reversibility: Reversibility = Reversibility.UNKNOWN

    status: CommitmentStatus = CommitmentStatus.ACTIVE

    metadata: dict = field(default_factory=dict)


class CommitmentRegistry:
    """Maintain commitments created by executed agent actions."""

    def __init__(self):
        self._commitments: dict[str, Commitment] = {}

    def register(
        self,
        commitment_id: str,
        action_id: str,
        originating_belief_ids: set[str],
        description: str,
        reversibility: Reversibility = Reversibility.UNKNOWN,
        metadata: Optional[dict] = None,
    ) -> Commitment:
        """Register an external commitment."""

        if commitment_id in self._commitments:
            raise ValueError(
                f"Commitment already exists: {commitment_id}"
            )

        if not originating_belief_ids:
            raise ValueError(
                "At least one originating belief is required."
            )

        commitment = Commitment(
            commitment_id=commitment_id,
            action_id=action_id,
            originating_belief_ids=set(originating_belief_ids),
            description=description,
            reversibility=reversibility,
            metadata=dict(metadata or {}),
        )

        self._commitments[commitment_id] = commitment

        return commitment

    def get(self, commitment_id: str) -> Commitment:
        """Retrieve a commitment by ID."""

        try:
            return self._commitments[commitment_id]
        except KeyError as exc:
            raise KeyError(
                f"Unknown commitment: {commitment_id}"
            ) from exc

    def all(self) -> list[Commitment]:
        """Return all registered commitments."""

        return list(self._commitments.values())

    def find_by_belief(
        self,
        belief_id: str,
    ) -> list[Commitment]:
        """Find commitments directly justified by a belief."""

        return [
            commitment
            for commitment in self._commitments.values()
            if belief_id in commitment.originating_belief_ids
        ]

    def mark_inconsistent(
        self,
        commitment_id: str,
        reason: str,
    ) -> Commitment:
        """Record that a commitment conflicts with updated evidence."""

        commitment = self.get(commitment_id)

        commitment.status = CommitmentStatus.INCONSISTENT

        commitment.metadata["inconsistency_reason"] = reason

        return commitment

    def mark_for_review(
        self,
        commitment_id: str,
        reason: str,
    ) -> Commitment:
        """Flag a commitment whose validity needs further checking."""

        commitment = self.get(commitment_id)

        commitment.status = CommitmentStatus.REQUIRES_REVIEW

        commitment.metadata["review_reason"] = reason

        return commitment

    def mark_reconciled(
        self,
        commitment_id: str,
        verification_evidence: str,
    ) -> Commitment:
        """Record reconciliation after verification."""

        if not verification_evidence.strip():
            raise ValueError(
                "Verification evidence is required."
            )

        commitment = self.get(commitment_id)

        commitment.status = CommitmentStatus.RECONCILED

        commitment.metadata["verification_evidence"] = (
            verification_evidence
        )

        return commitment