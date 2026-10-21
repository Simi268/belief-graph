from time import perf_counter

from .agent import AgentRuntime
from .replanner import Replanner
from .events import RevisionEvent
from .models import NodeStatus, NodeType, ActionExecutionStatus
from .semantic_recomputation import SemanticRecomputer

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
        recompute_node=None,
    ):
        """Revise a failed belief, plan recovery, and optionally execute it.

        ``recompute_node`` is an optional callback passed to
        AgentRuntime.execute_selective_recovery. It must accept a graph node
        and return the recomputed result. The callback is intentionally
        required for arbitrary plan/conclusion recomputation; the engine does
        not pretend that changing a node's status recomputes its semantics.
        """
        recovery_started_at = perf_counter()

        evidence_result = self.agent.create_evidence_from_action_result(
            evidence_id=evidence_id,
            action_result=action_result,
        )
        if evidence_result is None:
            return {
                "status": "no_recovery_needed",
                "recovery_metrics": {
                    "replacement_planned": False,
                    "replacement_executed": False,
                    "replacement_succeeded": None,
                    "recomputed_node_count": 0,
                    "recovery_duration_ms": round(
                        (perf_counter() - recovery_started_at) * 1000, 3
                    ),
                },
            }

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
        selective_recovery = None

        # Keep the existing replacement-action behavior intact.
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

        # Run generic selective recovery only when a domain-specific callback
        # is supplied. The newly-created replacement action is handled by the
        # existing execution path above, so don't recompute it a second time.
        if recompute_node is not None:
            plan_for_execution = dict(recovery_plan)
            selected_node_ids = [
                node_id
                for node_id in recovery_plan.get("replan_nodes", [])
                if new_action is None or node_id != old_action_id
            ]

            # The legacy planner selects PLAN/ACTION nodes. When the explicit
            # SemanticRecomputer is supplied, also include affected CONCLUSION
            # nodes so their values are refreshed before dependent plans.
            # Generic callbacks retain the original selection contract.
            if isinstance(recompute_node, SemanticRecomputer):
                recomputable_conclusion_statuses = {
                    NodeStatus.INVALID,
                    NodeStatus.REQUIRES_REEVALUATION,
                    NodeStatus.UNCERTAIN,
                }
                affected_conclusion_ids = []
                for node_id, details in impact.items():
                    if (
                        not isinstance(details, dict)
                        or details.get("impact") not in recomputable_conclusion_statuses
                        or node_id not in self.agent.graph.graph
                    ):
                        continue
                    node = self.agent.graph.get_node(node_id)
                    if node.node_type == NodeType.CONCLUSION:
                        affected_conclusion_ids.append(node_id)

                selected_node_ids = affected_conclusion_ids + selected_node_ids

            plan_for_execution["replan_nodes"] = list(
                dict.fromkeys(selected_node_ids)
            )
            selective_recovery = self.agent.execute_selective_recovery(
                recovery_plan=plan_for_execution,
                recompute_node=recompute_node,
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

        # Legacy status contract: "recovered" means replacement planning
        # completed; execution outcomes are reported separately.
        status = "recovered" if new_action is not None else "revised"

        selective_metrics = (
            selective_recovery.get("metrics", {})
            if selective_recovery is not None else {}
        )
        selective_recovery_reason = (
            None
            if selective_recovery is not None
            else "No semantic evaluators were registered for this graph."
        )
        recovery_metrics = {
            "affected_node_count": len(set(affected_nodes)),
            "invalidated_node_count": len(set(invalidated_nodes)),
            "reevaluation_node_count": len(set(reevaluation_nodes)),
            "uncertain_node_count": len(set(uncertain_nodes)),
            "replacement_planned": new_action is not None,
            "replacement_executed": execution is not None,
            "replacement_succeeded": (
                execution.get("success") if execution is not None else None
            ),
            "selective_recovery_executed": selective_recovery is not None,
            "selective_recovery_skip_reason": selective_recovery_reason,
            "recomputed_node_count": selective_metrics.get(
                "recomputed_node_count", 0
            ),
            "successful_recomputations": selective_metrics.get(
                "successful_recomputations", 0
            ),
            "failed_recomputations": selective_metrics.get(
                "failed_recomputations", 0
            ),
            "selective_recovery_duration_ms": selective_metrics.get(
                "recovery_duration_ms"
            ),
            "recovery_duration_ms": round(
                (perf_counter() - recovery_started_at) * 1000, 3
            ),
        }

        return {
            "status": status,
            "revision": revision,
            "recovery_plan": recovery_plan,
            "selective_recovery": selective_recovery,
            "new_action": new_action,
            "execution": execution,
            "event": event,
            "commitment_impact": commitment_report,
            "commitment_dependency_report": dependency_report,
            "commitment_recommendations": recommendations,
            "recovery_metrics": recovery_metrics,
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
            raise ValueError(
                f"Cannot execute using inactive belief '{belief_id}'."
            )
        if self.agent.graph.graph.get_edge_data(belief_id, action_id) is None:
            raise ValueError(
                f"Action '{action_id}' does not depend on belief '{belief_id}'."
            )

        action.execution_status = ActionExecutionStatus.RUNNING
        action.execution_result = None
        try:
            result = self.agent.execute_api_action(
                environment=environment,
                belief_id=belief_id,
                action_id=action_id,
            )
            env_result = result.get("environment_result", {})
            success = bool(env_result.get("success", False))
            action.execution_status = (
                ActionExecutionStatus.SUCCEEDED
                if success else ActionExecutionStatus.FAILED
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
                "success": False,
                "action_id": action_id,
                "error": str(exc),
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
