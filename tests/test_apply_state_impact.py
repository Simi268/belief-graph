from app.agent import AgentRuntime
from app.models import (
    DependencyType,
    NodeStatus,
    NodeType
)


def test_apply_state_impact_changes_node_states():
    agent = AgentRuntime()

    agent.create_belief(
        "B1",
        "Initial belief"
    )

    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "Derived conclusion"
    )

    agent.create_node(
        "P1",
        NodeType.PLAN,
        "Execution plan"
    )

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "C1",
        "P1",
        DependencyType.SUPPORTS
    )

    impact = agent.graph.propagate_state_impact(
        "B1"
    )

    applied = agent.graph.apply_state_impact(
        impact
    )

    assert applied["C1"] == (
        NodeStatus.INVALID
    )

    assert applied["P1"] == (
        NodeStatus.REQUIRES_REEVALUATION
    )

    assert agent.graph.get_node(
        "C1"
    ).status == NodeStatus.INVALID

    assert agent.graph.get_node(
        "P1"
    ).status == (
        NodeStatus.REQUIRES_REEVALUATION
    )