from .agent import AgentRuntime
from .replanner import Replanner
from .events import RevisionEvent
from .models import NodeStatus


class RecoveryEngine:

    def __init__(self, agent: AgentRuntime):
        self.agent = agent
        self.replanner = Replanner(agent.graph)

    def recover_from_action_failure(
        self,
        action_result: dict,
        evidence_id: str,
        new_belief_id: str,
        new_action_id: str
    ):
        # ==================================================
        # STEP 1 — Convert failure into evidence
        # ==================================================

        evidence_result = self.agent.create_evidence_from_action_result(
            evidence_id=evidence_id,
            action_result=action_result
        )

        if evidence_result is None:
            return {
                "status": "no_recovery_needed"
            }

        conflict = evidence_result["conflict"]

        # ==================================================
        # STEP 2 — Revise the belief
        # ==================================================

        revision = self.agent.revise_from_action_failure(
            conflict_id=conflict.id,
            new_belief_id=new_belief_id
        )

        old_belief_id = revision["old_belief"]

        # ==================================================
        # STEP 3 — Extract state-aware impact
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

        # The revised belief is a new active state introduced by this
        # recovery event. It is not invalidated, but it is part of the
        # event's affected/provenance surface.
        if new_belief_id not in affected_nodes:
            affected_nodes.append(new_belief_id)

        # ==================================================
        # STEP 4 — Build the selective recovery plan
        # ==================================================

        recovery_plan = self.agent.create_recovery_plan(
            impact=impact,
            changed_nodes=[old_belief_id]
        )

        # ==================================================
        # STEP 5 — Replan only if the failed action is
        #          actually inside the recovery region.
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
                new_action_id=new_action_id
            )

        # ==================================================
        # STEP 6 — Record revision provenance
        # ==================================================

        event = RevisionEvent(
            event_id=f"REV-{conflict.id}",
            conflict_id=conflict.id,
            old_belief_id=old_belief_id,
            new_belief_id=new_belief_id,
            old_action_id=old_action_id,
            new_action_id=(
                new_action.id
                if new_action is not None
                else None
            ),
            affected_nodes=affected_nodes,
            invalidated_nodes=invalidated_nodes,
            reevaluation_nodes=reevaluation_nodes,
            uncertain_nodes=uncertain_nodes,
            reason=conflict.reason
        )

        # ==================================================
        # STEP 7 — Return the complete recovery result
        # ==================================================

        return {
            "status": (
                "recovered"
                if new_action is not None
                else "revised"
            ),
            "revision": revision,
            "recovery_plan": recovery_plan,
            "new_action": new_action,
            "event": event
        }
