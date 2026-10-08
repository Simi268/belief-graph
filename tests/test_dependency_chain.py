from app.agent import AgentRuntime
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)


def test_belief_to_action_dependency_chain():
    agent = AgentRuntime()

    # -------------------------
    # Create reasoning nodes
    # -------------------------

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

    # -------------------------
    # Create dependencies
    # -------------------------

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

    # -------------------------
    # Verify dependency chain
    # -------------------------

    assert (
        agent.graph.get_dependency_type(
            "B1",
            "C1"
        )
        == DependencyType.REQUIRES
    )

    assert (
        agent.graph.get_dependency_type(
            "C1",
            "P1"
        )
        == DependencyType.REQUIRES
    )

    assert (
        agent.graph.get_dependency_type(
            "P1",
            "A1"
        )
        == DependencyType.REQUIRES
    )

    # -------------------------
    # All nodes start active
    # -------------------------

    assert (
        agent.get_belief_status("B1")
        == NodeStatus.ACTIVE
    )

    assert (
        agent.graph.get_node("C1").status
        == NodeStatus.ACTIVE
    )

    assert (
        agent.graph.get_node("P1").status
        == NodeStatus.ACTIVE
    )

    assert (
        agent.graph.get_node("A1").status
        == NodeStatus.ACTIVE
    )