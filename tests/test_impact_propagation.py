from app.agent import AgentRuntime
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)


def test_belief_invalidation_propagates_to_dependents():
    agent = AgentRuntime()

    # Main reasoning chain
    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90
    )

    agent.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="v1 endpoint can be used"
    )

    agent.create_node(
        node_id="P1",
        node_type=NodeType.PLAN,
        content="Fetch customer data"
    )

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1"
    )

    # Unrelated branch
    agent.create_belief(
        belief_id="B2",
        content="Customer region is India",
        value="India",
        confidence=0.90
    )

    agent.create_node(
        node_id="C2",
        node_type=NodeType.CONCLUSION,
        content="Use INR"
    )

    # Dependencies
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

    agent.add_dependency(
        "P1",
        "A1",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "B2",
        "C2",
        DependencyType.REQUIRES
    )

    # Invalidate B1
    affected = agent.graph.invalidate("B1")

    # Main branch should be affected
    assert "B1" in affected
    assert "C1" in affected
    assert "P1" in affected
    assert "A1" in affected

    # Unrelated branch must NOT be affected
    assert "B2" not in affected
    assert "C2" not in affected

    # Verify statuses
    assert (
        agent.graph.get_node("B1").status
        == NodeStatus.INVALID
    )

    assert (
        agent.graph.get_node("C1").status
        == NodeStatus.INVALID
    )

    assert (
        agent.graph.get_node("P1").status
        == NodeStatus.INVALID
    )

    assert (
        agent.graph.get_node("A1").status
        == NodeStatus.INVALID
    )

    assert (
        agent.graph.get_node("B2").status
        == NodeStatus.ACTIVE
    )

    assert (
        agent.graph.get_node("C2").status
        == NodeStatus.ACTIVE
    )