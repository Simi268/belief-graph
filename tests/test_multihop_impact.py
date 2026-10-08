from app.agent import AgentRuntime
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)


def test_multi_hop_impact_preserves_dependency_semantics():

    agent = AgentRuntime()

    agent.create_belief(
        "B1",
        "API version is v1"
    )

    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "v1 endpoint can be used"
    )

    agent.create_node(
        "P1",
        NodeType.PLAN,
        "Fetch customer data"
    )

    agent.create_node(
        "A1",
        NodeType.ACTION,
        "Call customer API"
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

    impact = agent.graph.propagate_impact("B1")

    assert impact["C1"]["impact"] == (
        NodeStatus.INVALID
    )

    assert impact["P1"]["impact"] == (
        NodeStatus.REQUIRES_REEVALUATION
    )

    assert impact["A1"]["impact"] == (
        NodeStatus.INVALID
    )