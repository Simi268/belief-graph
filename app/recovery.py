from .agent import AgentRuntime
from .replanner import Replanner
from .events import RevisionEvent
from .models import NodeStatus, NodeType, ActionExecutionStatus

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
        self.commitment_registry = (
            commitment_registry if commitment_registry is not None
            else CommitmentRegistry()
        )
        self.commitment_analyzer = CommitmentImpactAnalyzer(
            self.commitment_registry
        )
        self.commitment_reconciler = CommitmentReconciler(
            self.commitment_registry
        )
        self.commitment_dependency_resolver = CommitmentDependencyResolver(
            agent.graph, self.commitment_registry
        )

    def recover_from_action_failure(
        self,
        action_result: dict,
        evidence_id: str,
        new_belief_id: str,
        new_action_id: str,
        *,
        environment=None,
    ):
        evidence_result = self.agent.create_evidence_from_action_result(
            evidence_id=evidence_id,
            action_result=action_result,
        )
        if evidence_result is None:
            return {"status": "no_recovery_needed"}

        conflict = evidence_result["conflict"]
        revision = self.agent.revise_from_action_failure(
            conflict_id=conflict.id,
            new_belief_id=new_belief_id,
        )
        old_belief_id = revision["old_belief"]

        dependency_report = self.commitment_dependency_resolver.resolve(
            changed_node_ids={old_belief_id}
        )
        commitment_report = self.commitment_analyzer.analyze(
            changed_belief_ids=dependency_report.affected_node_ids,
            reason=f"Belief '{old_belief_id}' changed after an action failure.",
        )
        recommendations = [
            self.commitment_reconciler.recommend(commitment_id)
            for commitment_id in commitment_report.affected_commitment_ids
        ]

        impact = revision.get("impact", {})
        affected_nodes, invalidated_nodes = [], []
        reevaluation_nodes, uncertain_nodes = [], []
        for node_id, details in impact.items():
            if not isinstance(details, dict) or "impact" not in details:
                continue
            status = details["impact"]
            affected_nodes.append(node_id)
            if status == NodeStatus.INVALID:
                invalidated_nodes.append(node_id)
            elif status == NodeStatus.REQUIRES_REEVALUATION:
                reevaluation_nodes.append(node_id)
            elif status == NodeStatus.UNCERTAIN:
                uncertain_nodes.append(node_id)

        if old_belief_id not in invalidated_nodes:
            invalidated_nodes.append(old_belief_id)
        if old_belief_id not in affected_nodes:
            affected_nodes.append(old_belief_id)
        if new_belief_id not in affected_nodes:
            affected_nodes.append(new_belief_id)

        recovery_plan = self.agent.create_recovery_plan(
            impact=impact, changed_nodes=[old_belief_id]
        )
        old_action_id = action_result.get("action_id")
        new_action, execution = None, None

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
            if environment is not None:
                execution = self.execute_replacement_action(
                    action_id=new_action.id,
                    belief_id=new_belief_id,
                    environment=environment,
                )

        event = RevisionEvent(
            event_id=f"REV-{conflict.id}",
            conflict_id=conflict.id,
            old_belief_id=old_belief_id,
            new_belief_id=new_belief_id,
            old_action_id=old_action_id,
            new_action_id=new_action.id if new_action is not None else None,
            affected_nodes=affected_nodes,
            invalidated_nodes=invalidated_nodes,
            reevaluation_nodes=reevaluation_nodes,
            uncertain_nodes=uncertain_nodes,
            reason=(
                f"New evidence contradicts belief {old_belief_id}. "
                f"The belief was revised to {new_belief_id}."
            ),
        )

        # Keep historical status semantics for callers that only plan recovery.
        # When execution is requested, report its verified result.
        # Preserve the legacy RecoveryEngine contract: "recovered" means
        # belief revision + replacement planning completed. The actual retry
        # outcome is represented separately by `execution`.
        if new_action is not None:
            status = "recovered"
        else:
            status = "revised"

        return {
            "status": status,
            "revision": revision,
            "recovery_plan": recovery_plan,
            "new_action": new_action,
            "execution": execution,
            "event": event,
            "commitment_impact": commitment_report,
            "commitment_dependency_report": dependency_report,
            "commitment_recommendations": recommendations,
        }

    def execute_replacement_action(
        self, *, action_id: str, belief_id: str, environment
    ) -> dict:
        action = self.agent.graph.get_node(action_id)
        belief = self.agent.graph.get_node(belief_id)

        if action.node_type != NodeType.ACTION:
            raise ValueError(f"Node '{action_id}' is not an action.")
        if belief.node_type != NodeType.BELIEF:
            raise ValueError(f"Node '{belief_id}' is not a belief.")
        if belief.status != NodeStatus.ACTIVE:
            raise ValueError(f"Cannot execute using inactive belief '{belief_id}'.")
        if self.agent.graph.graph.get_edge_data(belief_id, action_id) is None:
            raise ValueError(
                f"Action '{action_id}' does not depend on belief '{belief_id}'."
            )

        action.execution_status = ActionExecutionStatus.RUNNING
        action.execution_result = None
        try:
            result = self.agent.execute_api_action(
                environment=environment, belief_id=belief_id, action_id=action_id
            )
            env_result = result.get("environment_result", {})
            success = bool(env_result.get("success", False))
            action.execution_status = (
                ActionExecutionStatus.SUCCEEDED if success
                else ActionExecutionStatus.FAILED
            )
            action.execution_result = {
                "success": success,
                "belief_id": belief_id,
                "action_id": action_id,
                "assumed_version": result.get("assumed_version"),
                "environment_result": env_result,
            }
            return action.execution_result.copy()
        except Exception as exc:
            action.execution_status = ActionExecutionStatus.FAILED
            action.execution_result = {
                "success": False, "action_id": action_id, "error": str(exc)
            }
            raise

    def reconcile_commitment(
        self, commitment_id, compensation, *, approved=False
    ):
        return self.commitment_reconciler.reconcile(
            commitment_id=commitment_id,
            compensation=compensation,
            approved=approved,
        )
