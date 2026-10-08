from app.agent import AgentRuntime
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)


def test_multi_belief_impact_uses_strongest_state():

    agent = AgentRuntime()

    # ================================================
    # TWO BELIEFS
    # ================================================

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="api-service"
    )

    agent.create_belief(
        belief_id="B2",
        content="Customer endpoint is available",
        value=True,
        confidence=0.90,
        source="service-discovery"
    )

    # ================================================
    # SHARED CONCLUSION
    # ================================================

    agent.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="Customer data can be retrieved"
    )

    # B1 is REQUIRED for C1.
    # If B1 becomes invalid, C1 becomes INVALID.

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.REQUIRES
    )

    # B2 only SUPPORTS C1.
    # If B2 becomes invalid, C1 only needs reevaluation.

    agent.add_dependency(
        "B2",
        "C1",
        DependencyType.SUPPORTS
    )

    # ================================================
    # DOWNSTREAM PLAN
    # ================================================

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

    # ================================================
    # COMBINED IMPACT
    # ================================================

    impact = agent.graph.analyze_multi_belief_impact(
        changed_nodes=["B1", "B2"]
    )

    # ================================================
    # C1
    # ================================================

    assert "C1" in impact

    # B1 -> C1 gives INVALID
    # B2 -> C1 gives REQUIRES_REEVALUATION
    #
    # INVALID is stronger, so INVALID must win.

    assert impact["C1"]["impact"] == NodeStatus.INVALID

    assert set(
        impact["C1"]["affected_by"]
    ) == {"B1", "B2"}

    assert impact["C1"]["depth"] == 1

    # ================================================
    # P1
    # ================================================

    assert "P1" in impact

    # Because C1 reaches P1 with INVALID impact,
    # the hard invalidation continues downstream.

    assert impact["P1"]["impact"] == NodeStatus.INVALID

    assert set(
        impact["P1"]["affected_by"]
    ) == {"B1", "B2"}

    assert impact["P1"]["depth"] == 2