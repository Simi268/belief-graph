from app.agent import AgentRuntime
from app.models import (
    DependencyType,
    NodeStatus,
    NodeType
)


def test_invalidation_does_not_cross_soft_boundary():
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
        "Plan supported by conclusion"
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

    impact = agent.graph.propagate_state_impact(
        "B1"
    )

    applied = agent.graph.apply_state_impact(
        impact
    )

    assert applied["C1"] == NodeStatus.INVALID

    assert applied["P1"] == (
        NodeStatus.REQUIRES_REEVALUATION
    )

    # A1 must remain untouched because P1
    # is only awaiting reevaluation.
    assert "A1" not in applied

    assert agent.graph.get_node(
        "A1"
    ).status == NodeStatus.ACTIVE