from app.agent import AgentRuntime
from app.models import NodeType, DependencyType, NodeStatus


def test_multiple_beliefs_share_downstream_reasoning():

    agent = AgentRuntime()

    # ==================================================
    # BELIEF 1
    # ==================================================

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="api-service"
    )

    # ==================================================
    # BELIEF 2
    # ==================================================

    agent.create_belief(
        belief_id="B2",
        content="Customer endpoint is available",
        value=True,
        confidence=0.90,
        source="service-discovery"
    )

    # ==================================================
    # SHARED CONCLUSION
    # ==================================================

    agent.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content=(
            "Customer data can be retrieved "
            "through the available API"
        )
    )

    # Both beliefs are required for C1.
    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "B2",
        "C1",
        DependencyType.REQUIRES
    )

    # ==================================================
    # SHARED PLAN
    # ==================================================

    agent.create_node(
        node_id="P1",
        node_type=NodeType.PLAN,
        content="Retrieve customer data"
    )

    agent.add_dependency(
        "C1",
        "P1",
        DependencyType.REQUIRES
    )

    # ==================================================
    # VERIFY INITIAL STATE
    # ==================================================

    assert agent.get_belief_status(
        "B1"
    ) == NodeStatus.ACTIVE

    assert agent.get_belief_status(
        "B2"
    ) == NodeStatus.ACTIVE

    assert agent.graph.get_node(
        "C1"
    ).status == NodeStatus.ACTIVE

    assert agent.graph.get_node(
        "P1"
    ).status == NodeStatus.ACTIVE

    # ==================================================
    # CHANGE BELIEF 1
    # ==================================================

    impact_b1 = agent.graph.propagate_state_impact(
        "B1",
        initial_status=NodeStatus.INVALID
    )

    # B1 requires C1, so C1 becomes invalid.
    assert impact_b1["C1"]["impact"] == (
        NodeStatus.INVALID
    )

    # C1 requires P1, so P1 becomes invalid too.
    assert impact_b1["P1"]["impact"] == (
        NodeStatus.INVALID
    )

    # ==================================================
    # CHANGE BELIEF 2
    # ==================================================

    impact_b2 = agent.graph.propagate_state_impact(
        "B2",
        initial_status=NodeStatus.INVALID
    )

    # The second belief independently reaches
    # the same shared reasoning chain.
    assert impact_b2["C1"]["impact"] == (
        NodeStatus.INVALID
    )

    assert impact_b2["P1"]["impact"] == (
        NodeStatus.INVALID
    )
