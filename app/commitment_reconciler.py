"""Safely reconcile inconsistent external commitments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.commitments import (
    Commitment,
    CommitmentRegistry,
    CommitmentStatus,
    Reversibility,
)


@dataclass
class ReconciliationResult:
    commitment_id: str
    status: str
    message: str
    verification_evidence: str | None = None


class CommitmentReconciler:
    """Coordinate safe compensation and verification."""

    def __init__(self, registry: CommitmentRegistry):
        self.registry = registry

    def recommend(self, commitment_id: str) -> dict:
        """Recommend a next step without executing external actions."""

        commitment = self.registry.get(commitment_id)

        if commitment.status == CommitmentStatus.RECONCILED:
            return {
                "commitment_id": commitment_id,
                "recommendation": "none",
                "requires_approval": False,
                "reason": "Commitment is already reconciled.",
            }

        if commitment.status == CommitmentStatus.REQUIRES_REVIEW:
            return {
                "commitment_id": commitment_id,
                "recommendation": "human_review",
                "requires_approval": True,
                "reason": "Commitment requires human review.",
            }

        if commitment.status != CommitmentStatus.INCONSISTENT:
            return {
                "commitment_id": commitment_id,
                "recommendation": "investigate",
                "requires_approval": True,
                "reason": "Commitment is not marked inconsistent.",
            }

        if commitment.reversibility == Reversibility.REVERSIBLE:
            recommendation = "compensate"
            reason = "The commitment is marked reversible."
        elif commitment.reversibility == Reversibility.COMPENSABLE:
            recommendation = "compensate"
            reason = "A compensating action may be possible."
        else:
            recommendation = "human_review"
            reason = "Reversibility is not established."

        return {
            "commitment_id": commitment_id,
            "recommendation": recommendation,
            "requires_approval": True,
            "reason": reason,
        }

    def reconcile(
        self,
        commitment_id: str,
        compensation: Callable[[Commitment], dict],
        *,
        approved: bool = False,
    ) -> ReconciliationResult:
        """Execute approved compensation and verify its reported outcome.

        The callback must return:
            {
                "success": True,
                "verification_evidence": "..."
            }

        A successful callback response is treated as the executor's
        verification report. Production integrations should independently
        verify the external system's actual state.
        """

        commitment = self.registry.get(commitment_id)
        recommendation = self.recommend(commitment_id)

        if recommendation["recommendation"] != "compensate":
            return ReconciliationResult(
                commitment_id=commitment_id,
                status="blocked",
                message=recommendation["reason"],
            )

        if not approved:
            return ReconciliationResult(
                commitment_id=commitment_id,
                status="approval_required",
                message="Explicit approval is required.",
            )

        if commitment.reversibility not in {
            Reversibility.REVERSIBLE,
            Reversibility.COMPENSABLE,
        }:
            return ReconciliationResult(
                commitment_id=commitment_id,
                status="blocked",
                message="Unsafe or unknown reversibility.",
            )

        try:
            outcome = compensation(commitment)
        except Exception as exc:
            return ReconciliationResult(
                commitment_id=commitment_id,
                status="compensation_failed",
                message=f"Compensation raised {type(exc).__name__}.",
            )

        if not isinstance(outcome, dict) or not outcome.get("success"):
            return ReconciliationResult(
                commitment_id=commitment_id,
                status="compensation_failed",
                message="Compensation did not report success.",
            )

        evidence = outcome.get("verification_evidence")

        if not isinstance(evidence, str) or not evidence.strip():
            return ReconciliationResult(
                commitment_id=commitment_id,
                status="verification_required",
                message=(
                    "Compensation reported success, but verification "
                    "evidence is missing. The commitment remains unresolved."
                ),
            )

        self.registry.mark_reconciled(
            commitment_id=commitment_id,
            verification_evidence=evidence,
        )

        return ReconciliationResult(
            commitment_id=commitment_id,
            status="reconciled",
            message="Compensation and verification were reported successful.",
            verification_evidence=evidence,
        )