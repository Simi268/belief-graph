from __future__ import annotations

from time import perf_counter
from typing import Any

from .models import (
    BeliefNode,
    NodeType,
    NodeStatus,
    DependencyType,
    ActionExecutionStatus,
)


class Replanner:
    """Create replacement actions and describe selective-recovery work.

    ``plan_selective_recovery`` creates a recovery-work plan only; it does not
    execute actions or claim that nodes have been recomputed.
    """

    def __init__(self, graph):
        self.graph = graph

    def replan_api_action(
        self,
        old_belief_id: str,
        new_belief_id: str,
        old_action_id: str,
        new_action_id: str,
    ):
        old_belief = self.graph.get_node(old_belief_id)
        new_belief = self.graph.get_node(new_belief_id)
        old_action = self.graph.get_node(old_action_id)

        if old_belief.status != NodeStatus.INVALID:
            raise ValueError("Old belief must be invalid before replanning.")
        if new_belief.status != NodeStatus.ACTIVE:
            raise ValueError("New belief must be active before replanning.")
        if old_action.status != NodeStatus.INVALID:
            raise ValueError("Old action must be invalid before replanning.")
        if new_action_id in self.graph.graph:
            raise ValueError(
                f"Node '{new_action_id}' already exists; refusing to overwrite it."
            )

        new_action = BeliefNode(
            id=new_action_id,
            node_type=NodeType.ACTION,
            content=f"Call customer API using {new_belief.value}",
            value=new_belief.value,
            confidence=new_belief.confidence,
            source="replanner",
            execution_status=ActionExecutionStatus.PLANNED,
            execution_result=None,
        )
        self.graph.add_node(new_action)
        self.graph.add_dependency(
            new_belief_id, new_action_id, DependencyType.REQUIRES
        )
        return new_action

    def plan_selective_recovery(
        self,
        *,
        impact: dict[str, Any],
        changed_node_ids: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict[str, Any]:
        """Build a deterministic plan from an existing impact classification.

        The returned counts describe nodes selected for recovery, not actual
        recomputation. Actual recomputation must be performed and measured by
        the recovery executor.
        """
        started_at = perf_counter()
        changed_nodes = set(changed_node_ids or ())
        affected_nodes: set[str] = set()
        recovery_nodes: set[str] = set()
        invalidated_nodes: set[str] = set()
        reevaluation_nodes: set[str] = set()
        uncertain_nodes: set[str] = set()
        causes: dict[str, list[str]] = {}

        for node_id, details in impact.items():
            if not isinstance(details, dict) or "impact" not in details:
                continue

            affected_nodes.add(node_id)
            status = details["impact"]
            if status == NodeStatus.INVALID:
                invalidated_nodes.add(node_id)
            elif status == NodeStatus.REQUIRES_REEVALUATION:
                reevaluation_nodes.add(node_id)
            elif status == NodeStatus.UNCERTAIN:
                uncertain_nodes.add(node_id)

            affected_by = details.get("affected_by")
            if affected_by is not None:
                causes[node_id] = sorted(set(affected_by))
            elif details.get("source") is not None:
                causes[node_id] = [details["source"]]
            else:
                causes[node_id] = []

            if node_id not in self.graph.graph:
                continue

            node = self.graph.get_node(node_id)
            if node.node_type in {NodeType.PLAN, NodeType.ACTION} and status in {
                NodeStatus.INVALID,
                NodeStatus.REQUIRES_REEVALUATION,
                NodeStatus.UNCERTAIN,
            }:
                recovery_nodes.add(node_id)

        excluded = affected_nodes | changed_nodes
        reasoning_types = {
            NodeType.BELIEF,
            NodeType.CONCLUSION,
            NodeType.PLAN,
            NodeType.ACTION,
        }

        # Exclude revised beliefs pointed to by a superseded node.
        for node_id in self.graph.graph.nodes:
            node = self.graph.graph.nodes[node_id].get("data")
            if node is not None and getattr(node, "superseded_by", None):
                excluded.add(node.superseded_by)

        preserved_nodes = set()
        for node_id in self.graph.graph.nodes:
            if node_id in excluded:
                continue
            node = self.graph.graph.nodes[node_id].get("data")
            if node is not None and node.node_type in reasoning_types:
                preserved_nodes.add(node_id)

        elapsed_ms = round((perf_counter() - started_at) * 1000, 3)
        return {
            "changed_nodes": sorted(changed_nodes),
            "affected_nodes": sorted(affected_nodes),
            "invalidated_nodes": sorted(invalidated_nodes),
            "reevaluation_nodes": sorted(reevaluation_nodes),
            "uncertain_nodes": sorted(uncertain_nodes),
            "recovery_nodes": sorted(recovery_nodes),
            "preserved_nodes": sorted(preserved_nodes),
            "causes": causes,
            "metrics": {
                "affected_node_count": len(affected_nodes),
                "recovery_candidate_count": len(recovery_nodes),
                "preserved_node_count": len(preserved_nodes),
                "planning_duration_ms": elapsed_ms,
                "recomputed_node_count": 0,
                "execution_performed": False,
            },
        }
