from .agent import AgentRuntime
from .replanner import Replanner
from .events import RevisionEvent
from .models import NodeStatus

from .commitments import CommitmentRegistry
from .commitment_analyzer import CommitmentImpactAnalyzer
from .commitment_reconciler import CommitmentReconciler
from .commitment_dependency_resolver import CommitmentDependencyResolver


class RecoveryEngine:

    def __init__(
        self,
        agent: AgentRuntime,
        commitment_registry: CommitmentRegistry | None = None,
    ):
        self.agent = agent
        self.replanner = Replanner(agent.graph)

        # Shared commitment registry
        self.commitment_registry = (
            commitment_registry
            if commitment_registry is not None
            else CommitmentRegistry()
        )

        # Commitment impact classification
        self.commitment_analyzer = CommitmentImpactAnalyzer(
            self.commitment_registry
        )

        # Explicitly approved commitment reconciliation
        self.commitment_reconciler = CommitmentReconciler(
            self.commitment_registry
        )

        # Dependency-aware commitment discovery
        self.commitment_dependency_resolver = (
            CommitmentDependencyResolver(
                agent.graph,
                self.commitment_registry,
            )
        )

    def recover_from_action_failure(
        self,
        action_result: dict,
        evidence_id: str,
        new_belief_id: str,
        new_action_id: str,
    ):
        # ==================================================
        # STEP 1 — Convert failure into evidence
        # ==================================================

        evidence_result = self.agent.create_evidence_from_action_result(
            evidence_id=evidence_id,
            action_result=action_result,
        )

        if evidence_result is None:
            return {
                "status": "no_recovery_needed",
            }

        conflict = evidence_result["conflict"]

        # ==================================================
        # STEP 2 — Revise the belief
        # ==================================================

        revision = self.agent.revise_from_action_failure(
            conflict_id=conflict.id,
            new_belief_id=new_belief_id,
        )

        old_belief_id = revision["old_belief"]

        # ==================================================
        # STEP 3 — Resolve affected commitments
        # ==================================================

        dependency_report = (
            self.commitment_dependency_resolver.resolve(
                changed_node_ids={old_belief_id},
            )
        )

        commitment_report = self.commitment_analyzer.analyze(
            changed_belief_ids=dependency_report.affected_node_ids,
            reason=(
                f"Belief '{old_belief_id}' changed "
                "after an action failure."
            ),
        )

        commitment_recommendations = [
            self.commitment_reconciler.recommend(commitment_id)
            for commitment_id in (
                commitment_report.affected_commitment_ids
            )
        ]

        # ==================================================
        # STEP 4 — Extract state-aware graph impact
        # ==================================================

        impact = revision.get("impact", {})

        affected_nodes = []
        invalidated_nodes = []
        reevaluation_nodes = []
        uncertain_nodes = []

        for node_id, details in impact.items():

            if not isinstance(details, dict):
                continue

            if "impact" not in details:
                continue

            status = details["impact"]

            affected_nodes.append(node_id)

            if status == NodeStatus.INVALID:
                invalidated_nodes.append(node_id)

            elif status == NodeStatus.REQUIRES_REEVALUATION:
                reevaluation_nodes.append(node_id)

            elif status == NodeStatus.UNCERTAIN:
                uncertain_nodes.append(node_id)

        # The original belief is the changed root.
        if old_belief_id not in invalidated_nodes:
            invalidated_nodes.append(old_belief_id)

        if old_belief_id not in affected_nodes:
            affected_nodes.append(old_belief_id)

        # The revised belief is active and should not be treated
        # as an invalidated node.
        if new_belief_id not in affected_nodes:
            affected_nodes.append(new_belief_id)

        # ==================================================
        # STEP 5 — Build selective recovery plan
        # ==================================================

        recovery_plan = self.agent.create_recovery_plan(
            impact=impact,
            changed_nodes=[old_belief_id],
        )

        # ==================================================
        # STEP 6 — Replan only if the failed action belongs
        #          to the recovery region
        # ==================================================

        old_action_id = action_result.get("action_id")
        new_action = None

        if (
            old_action_id is not None
            and old_action_id in recovery_plan["replan_nodes"]
        ):
            new_action = self.replanner.replan_api_action(
                old_belief_id=old_belief_id,
                new_belief_id=new_belief_id,
                old_action_id=old_action_id,
                new_action_id=new_action_id,
            )


        # ==================================================
        # STEP 7 — Record revision provenance
        # ==================================================

        event = RevisionEvent(
            event_id=f"REV-{conflict.id}",
            conflict_id=conflict.id,
            old_belief_id=old_belief_id,
            new_belief_id=new_belief_id,
            old_action_id=old_action_id,
            new_action_id=(
                new_action.id if new_action is not None else None
            ),
            affected_nodes=affected_nodes,
            invalidated_nodes=invalidated_nodes,
            reevaluation_nodes=reevaluation_nodes,
            uncertain_nodes=uncertain_nodes,
            reason=(
                f"New evidence contradicts belief {old_belief_id}. "
                f"The belief was revised to {new_belief_id}."
            ),
        )

        # ==================================================
        # STEP 8 — Return recovery result
        # ==================================================

        return {
            "status": "recovered" if new_action else "revised",
            "revision": revision,
            "recovery_plan": recovery_plan,
            "new_action": new_action,
            "event": event,
            "commitment_impact": commitment_report,
            "commitment_dependency_report": dependency_report,
            "commitment_recommendations": commitment_recommendations,
        }

    # ======================================================
    # EXPLICIT COMMITMENT RECONCILIATION
    # ======================================================

    def reconcile_commitment(
        self,
        commitment_id,
        compensation,
        *,
        approved=False,
    ):
        """
        Reconcile an affected commitment.

        Compensation requires explicit approval and successful
        verification evidence from the compensation callback.
        """

        return self.commitment_reconciler.reconcile(
            commitment_id=commitment_id,
            compensation=compensation,
            approved=approved,
        )