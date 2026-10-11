from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.environment import DynamicAPIEnvironment
from app.langgraph_adapter import LangGraphAdapter
from app.models import DependencyType, NodeStatus, NodeType


def test_api_action_recovers_automatically_and_preserves_unrelated_nodes():
    environment = DynamicAPIEnvironment()
    adapter = LangGraphAdapter()

    # Original reasoning chain.
    adapter.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        value="v1",
    )

    adapter.register_node(
        langgraph_node="reason",
        belief_node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="Customer data can be retrieved",
    )

    adapter.register_node(
        langgraph_node="plan",
        belief_node_id="P1",
        node_type=NodeType.PLAN,
        content="Retrieve customer data",
    )

    adapter.register_node(
        langgraph_node="act",
        belief_node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1",
        value="v1",
    )

    adapter.add_dependencies(
        [
            ("retrieve", "reason", DependencyType.REQUIRES),
            ("reason", "plan", DependencyType.REQUIRES),
            ("plan", "act", DependencyType.REQUIRES),
        ]
    )

    # Independent branch.
    adapter.register_node(
        langgraph_node="report",
        belief_node_id="B3",
        node_type=NodeType.BELIEF,
        content="Reporting database is available",
        value=True,
    )

    adapter.register_node(
        langgraph_node="report_reason",
        belief_node_id="C3",
        node_type=NodeType.CONCLUSION,
        content="Reporting data can be generated",
    )

    adapter.add_dependencies(
        [
            ("report", "report_reason", DependencyType.REQUIRES),
        ]
    )

    # The environment changes after the original belief is created.
    environment.set_api_version("v2")

    result = adapter.execute_api_action_with_recovery(
        environment=environment,
        belief_id="B1",
        action_id="A1",
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
    )

    # Recovery and replacement execution both succeed.
    assert result["status"] == "recovered"
    assert result["recovery"]["status"] == "recovered"
    assert result["retry_result"]["environment_result"]["success"] is True

    # The old reasoning chain is invalidated.
    assert adapter.status(node_id="B1") == NodeStatus.INVALID
    assert adapter.status(node_id="C1") == NodeStatus.INVALID
    assert adapter.status(node_id="P1") == NodeStatus.INVALID
    assert adapter.status(node_id="A1") == NodeStatus.INVALID

    # The replacement belief and action are active.
    assert adapter.status(node_id="B2") == NodeStatus.ACTIVE
    assert adapter.status(node_id="A2") == NodeStatus.ACTIVE

    # The independent branch is preserved.
    assert adapter.status(node_id="B3") == NodeStatus.ACTIVE
    assert adapter.status(node_id="C3") == NodeStatus.ACTIVE

    # The recovery event records the revision.
    event = result["recovery"]["event"]
    assert "B1" in event.invalidated_nodes
    assert "A1" in event.invalidated_nodes
    assert "B2" in event.affected_nodes


class RecoveryWorkflowState(TypedDict):
    task: str
    recovery_status: str
    retry_succeeded: bool
    recovery_event: Any


def test_real_langgraph_workflow_executes_automatic_recovery():
    environment = DynamicAPIEnvironment()
    adapter = LangGraphAdapter()

    adapter.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        value="v1",
    )

    adapter.register_node(
        langgraph_node="act",
        belief_node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1",
        value="v1",
    )

    adapter.add_dependency(
        "retrieve",
        "act",
        DependencyType.REQUIRES,
    )

    # The environment changes after the original belief is created.
    environment.set_api_version("v2")

    def retrieve(state: RecoveryWorkflowState):
        return {}

    def act(state: RecoveryWorkflowState):
        outcome = adapter.execute_api_action_with_recovery(
            environment=environment,
            belief_id="B1",
            action_id="A1",
            evidence_id="E1",
            new_belief_id="B2",
            new_action_id="A2",
        )

        retry_result = outcome.get("retry_result") or {}
        environment_result = retry_result.get("environment_result") or {}
        recovery = outcome.get("recovery") or {}

        return {
            "recovery_status": outcome["status"],
            "retry_succeeded": (
                environment_result.get("success") is True
            ),
            "recovery_event": recovery.get("event"),
        }

    builder = StateGraph(RecoveryWorkflowState)

    builder.add_node("retrieve", retrieve)
    builder.add_node("act", act)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "act")
    builder.add_edge("act", END)

    workflow = builder.compile()

    result = workflow.invoke(
        {
            "task": "retrieve customer data",
            "recovery_status": "not_started",
            "retry_succeeded": False,
            "recovery_event": None,
        }
    )

    assert result["recovery_status"] == "recovered"
    assert result["retry_succeeded"] is True

    # Recovery details are visible in the final workflow state.
    event = result["recovery_event"]
    assert event is not None
    assert event.old_belief_id == "B1"
    assert event.new_belief_id == "B2"
    assert "B1" in event.invalidated_nodes
    assert "A1" in event.invalidated_nodes

    # Confirm that the workflow's action triggered belief revision.
    assert adapter.status(node_id="B1") == NodeStatus.INVALID
    assert adapter.status(node_id="B2") == NodeStatus.ACTIVE
    assert adapter.status(node_id="A1") == NodeStatus.INVALID
    assert adapter.status(node_id="A2") == NodeStatus.ACTIVE


def test_retry_failure_is_reported_without_another_retry():
    class ChangingAPIEnvironment(DynamicAPIEnvironment):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def call_api(self, version: str):
            self.calls += 1

            result = super().call_api(version)

            # Change the environment after the first API attempt.
            if self.calls == 1:
                self.set_api_version("v3")

            return result

    environment = ChangingAPIEnvironment()
    adapter = LangGraphAdapter()

    adapter.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        value="v1",
    )

    adapter.register_node(
        langgraph_node="act",
        belief_node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1",
        value="v1",
    )

    adapter.add_dependency(
        "retrieve",
        "act",
        DependencyType.REQUIRES,
    )

    # The original belief is stale: the environment uses v2.
    environment.set_api_version("v2")

    result = adapter.execute_api_action_with_recovery(
        environment=environment,
        belief_id="B1",
        action_id="A1",
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
    )

    # The replacement targets v2, but the environment has moved to v3.
    assert result["status"] == "retry_failed"
    assert (
        result["retry_result"]["environment_result"]["success"]
        is False
    )

    # Exactly two attempts: original action + one replacement action.
    assert environment.calls == 2

    # The outdated reasoning chain is invalidated.
    assert adapter.status(node_id="B1") == NodeStatus.INVALID
    assert adapter.status(node_id="A1") == NodeStatus.INVALID

    # Belief revision and replanning happened, but execution failed.
    assert adapter.status(node_id="B2") == NodeStatus.ACTIVE
    assert adapter.status(node_id="A2") == NodeStatus.ACTIVE

    # The adapter must not report a failed retry as successful recovery.
    assert result["status"] != "recovered"