from app.environment import DynamicAPIEnvironment
from app.langgraph_adapter import LangGraphAdapter
from app.models import DependencyType, NodeStatus, NodeType


def test_api_action_recovers_automatically_and_preserves_unrelated_nodes():
    environment = DynamicAPIEnvironment()
    adapter = LangGraphAdapter()
    runtime = adapter.belief_graph.runtime

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

    # Environment changes after the original belief was created.
    environment.set_api_version("v2")

    result = adapter.execute_api_action_with_recovery(
        environment=environment,
        belief_id="B1",
        action_id="A1",
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
    )

    # Recovery and the replacement execution both succeed.
    assert result["status"] == "recovered"
    assert result["recovery"]["status"] == "recovered"
    assert result["retry_result"]["environment_result"]["success"] is True

    # The old reasoning chain is invalidated.
    assert adapter.status(node_id="B1") == NodeStatus.INVALID
    assert adapter.status(node_id="C1") == NodeStatus.INVALID
    assert adapter.status(node_id="P1") == NodeStatus.INVALID
    assert adapter.status(node_id="A1") == NodeStatus.INVALID

    # The replacement belief and action are valid.
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

