"""Analyze external commitments affected by belief changes."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.commitments import (
    CommitmentRegistry,
    CommitmentStatus,
    Reversibility,
)


@dataclass
class CommitmentImpactReport:
    changed_belief_ids: set[str]
    affected_commitment_ids: list[str] = field(default_factory=list)
    inconsistent_commitment_ids: list[str] = field(default_factory=list)
    review_required_ids: list[str] = field(default_factory=list)
    unaffected_commitment_ids: list[str] = field(default_factory=list)


class CommitmentImpactAnalyzer:
    """Identify commitments affected by changes to their originating beliefs."""

    def __init__(self, registry: CommitmentRegistry):
        self.registry = registry

    def analyze(
        self,
        changed_belief_ids: set[str],
        reason: str = "An originating belief has changed.",
    ) -> CommitmentImpactReport:
        if not changed_belief_ids:
            raise ValueError("At least one changed belief ID is required.")

        report = CommitmentImpactReport(
            changed_belief_ids=set(changed_belief_ids)
        )

        for commitment in self.registry.all():
            # Ignore commitments that have already been reconciled.
            if commitment.status == CommitmentStatus.RECONCILED:
                report.unaffected_commitment_ids.append(
                    commitment.commitment_id
                )
                continue

            affected_beliefs = (
                commitment.originating_belief_ids & changed_belief_ids
            )

            if not affected_beliefs:
                report.unaffected_commitment_ids.append(
                    commitment.commitment_id
                )
                continue

            report.affected_commitment_ids.append(
                commitment.commitment_id
            )

            # Irreversible or unknown external effects must not be
            # automatically treated as safe to compensate.
            if commitment.reversibility in {
                Reversibility.IRREVERSIBLE,
                Reversibility.UNKNOWN,
            }:
                self.registry.mark_for_review(
                    commitment.commitment_id,
                    (
                        f"{reason} Affected beliefs: "
                        f"{', '.join(sorted(affected_beliefs))}"
                    ),
                )

                report.review_required_ids.append(
                    commitment.commitment_id
                )
            else:
                self.registry.mark_inconsistent(
                    commitment.commitment_id,
                    (
                        f"{reason} Affected beliefs: "
                        f"{', '.join(sorted(affected_beliefs))}"
                    ),
                )

                report.inconsistent_commitment_ids.append(
                    commitment.commitment_id
                )

        return report