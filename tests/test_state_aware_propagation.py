from app.agent import AgentRuntime
from app.models import (
    DependencyType,
    NodeStatus,
    NodeType
)


def test_invalid_state_continues_through_required_dependencies():
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
        DependencyType.REQUIRES
    )

    result = agent.graph.propagate_state_impact(
        "B1"
    )

    assert result["C1"]["impact"] == (
        NodeStatus.INVALID
    )

    assert result["P1"]["impact"] == (
        NodeStatus.INVALID
    )

    assert result["P1"]["depth"] == 2


def test_reevaluation_is_a_soft_boundary():
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

    agent.create_node(
        "A1",
        NodeType.ACTION,
        "Execute action"
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

    agent.add_dependency(
        "P1",
        "A1",
        DependencyType.REQUIRES
    )

    result = agent.graph.propagate_state_impact(
        "B1"
    )

    assert result["C1"]["impact"] == (
        NodeStatus.INVALID
    )

    assert result["P1"]["impact"] == (
        NodeStatus.REQUIRES_REEVALUATION
    )

    assert "A1" not in result


def test_unrelated_branch_is_not_affected():
    agent = AgentRuntime()

    agent.create_belief(
        "B1",
        "Changed belief"
    )

    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "Affected conclusion"
    )

    agent.create_node(
        "P1",
        NodeType.PLAN,
        "Affected plan"
    )

    agent.create_node(
        "C2",
        NodeType.CONCLUSION,
        "Unrelated conclusion"
    )

    agent.create_node(
        "P2",
        NodeType.PLAN,
        "Unrelated plan"
    )

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "C1",
        "P1",
        DependencyType.REQUIRES
    )

    result = agent.graph.propagate_state_impact(
        "B1"
    )

    assert "C1" in result
    assert "P1" in result

    assert "C2" not in result
    assert "P2" not in result

    assert agent.graph.get_node(
        "C2"
    ).status == NodeStatus.ACTIVE

    assert agent.graph.get_node(
        "P2"
    ).status == NodeStatus.ACTIVE