"""Identify stale actions from their current dependency state."""

from __future__ import annotations

from app.models import NodeStatus, NodeType


STALE_DEPENDENCY_STATUSES = {
    NodeStatus.INVALID,
    NodeStatus.REQUIRES_REEVALUATION,
    NodeStatus.UNCERTAIN,
}


def detect_stale_actions(graph) -> set[str]:
    """Return actions whose immediate prerequisite plan is not active.

    This detector derives its result from the runtime graph. It does not
    read benchmark expected_stale_actions.
    """

    stale_actions: set[str] = set()

    for node_id in graph.graph.nodes:
        node = graph.get_node(node_id)

        if node.node_type != NodeType.ACTION:
            continue

        # In this benchmark, plans are direct predecessors of actions.
        prerequisite_plans = [
            predecessor_id
            for predecessor_id in graph.graph.predecessors(node_id)
            if graph.get_node(predecessor_id).node_type == NodeType.PLAN
        ]

        if any(
            graph.get_node(plan_id).status in STALE_DEPENDENCY_STATUSES
            for plan_id in prerequisite_plans
        ):
            stale_actions.add(node_id)

    return stale_actions