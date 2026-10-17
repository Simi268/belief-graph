from dataclasses import dataclass, field
from typing import Any, Mapping

from app.models import NodeStatus, ActionExecutionStatus


@dataclass
class RecoveryVerification:
    verified: bool
    graph_correct: bool
    execution_successful: bool

    stale_nodes: list[str] = field(default_factory=list)
    unnecessarily_invalidated_nodes: list[str] = field(
        default_factory=list
    )
    status_mismatches: dict[str, dict[str, str]] = field(
        default_factory=dict
    )
    missing_nodes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "graph_correct": self.graph_correct,
            "execution_successful": self.execution_successful,
            "stale_nodes": self.stale_nodes,
            "unnecessarily_invalidated_nodes": (
                self.unnecessarily_invalidated_nodes
            ),
            "status_mismatches": self.status_mismatches,
            "missing_nodes": self.missing_nodes,
        }


def _status_value(status: NodeStatus | str) -> str:
    if isinstance(status, NodeStatus):
        return status.value
    return str(status)


def _execution_succeeded(
    execution_result: Mapping[str, Any] | None,
) -> bool:
    if not execution_result:
        return False

    # Support the environment's boolean result.
    if execution_result.get("success") is True:
        return True

    # Also support an action execution lifecycle result.
    status = execution_result.get("execution_status")

    if isinstance(status, ActionExecutionStatus):
        status = status.value

    return status == ActionExecutionStatus.SUCCEEDED.value


def verify_recovery(
    actual_statuses: Mapping[str, NodeStatus | str],
    expected_statuses: Mapping[str, NodeStatus | str],
    execution_result: Mapping[str, Any] | None,
) -> RecoveryVerification:
    """
    Independently verify graph recovery and action execution.

    actual_statuses:
        Statuses read from the actual graph after recovery.

    expected_statuses:
        Expected status for each node, defined by the scenario.

    execution_result:
        Actual result from executing the replacement action.
    """

    mismatches: dict[str, dict[str, str]] = {}
    missing_nodes: list[str] = []
    stale_nodes: list[str] = []
    unnecessarily_invalidated: list[str] = []

    for node_id, expected_status in expected_statuses.items():
        expected = _status_value(expected_status)

        if node_id not in actual_statuses:
            missing_nodes.append(node_id)
            continue

        actual = _status_value(actual_statuses[node_id])

        if actual != expected:
            mismatches[node_id] = {
                "expected": expected,
                "actual": actual,
            }

        # An affected node should not remain active when its
        # expected post-recovery status is non-active.
        if (
            expected != NodeStatus.ACTIVE.value
            and actual == NodeStatus.ACTIVE.value
        ):
            stale_nodes.append(node_id)

        # A node expected to remain valid should not be invalidated.
        if (
            expected == NodeStatus.ACTIVE.value
            and actual == NodeStatus.INVALID.value
        ):
            unnecessarily_invalidated.append(node_id)

    graph_correct = not mismatches and not missing_nodes
    execution_successful = _execution_succeeded(execution_result)

    return RecoveryVerification(
        verified=graph_correct and execution_successful,
        graph_correct=graph_correct,
        execution_successful=execution_successful,
        stale_nodes=sorted(stale_nodes),
        unnecessarily_invalidated_nodes=sorted(
            unnecessarily_invalidated
        ),
        status_mismatches=mismatches,
        missing_nodes=sorted(missing_nodes),
    )

def verify_graph_recovery(
    graph,
    expected_statuses: Mapping[str, NodeStatus | str],
    execution_result: Mapping[str, Any] | None,
) -> RecoveryVerification:
    """
    Verify recovery using actual graph node states.

    Unlike the impact prediction output, this reads each
    node's status directly from the graph after recovery.
    """
    actual_statuses = {}

    missing_nodes = []

    for node_id in expected_statuses:
        try:
            node = graph.get_node(node_id)
            actual_statuses[node_id] = node.status
        except (KeyError, ValueError):
            missing_nodes.append(node_id)

    result = verify_recovery(
        actual_statuses=actual_statuses,
        expected_statuses=expected_statuses,
        execution_result=execution_result,
    )

    # Include nodes absent from the actual graph.
    result.missing_nodes = sorted(
        set(result.missing_nodes) | set(missing_nodes)
    )

    result.graph_correct = (
        result.graph_correct and not result.missing_nodes
    )

    result.verified = (
        result.graph_correct and result.execution_successful
    )

    return result

def verify_recovery_run(
    *,
    agent,
    recovery_result,
    expected_statuses,
):
    """
    Verify a completed recovery using the actual graph state
    and the replacement action's execution result.

    expected_statuses should come from scenario ground truth,
    not from the recovery engine's predicted impact.
    """
    execution = recovery_result.get("execution")
    new_action = recovery_result.get("new_action")

    # Prefer the result stored on the actual replacement action.
    if new_action is not None:
        try:
            action = agent.graph.get_node(new_action.id)

            if action.execution_result is not None:
                execution = action.execution_result
        except (KeyError, ValueError):
            pass

    # A planned recovery without execution is not verified.
    if execution is None:
        execution = {"success": False}

    verification = verify_graph_recovery(
        graph=agent.graph,
        expected_statuses=expected_statuses,
        execution_result=execution,
    )

    report = verification.to_dict()
    report["recovery_status"] = recovery_result.get("status")
    report["replacement_action_id"] = (
        new_action.id if new_action is not None else None
    )

    return report