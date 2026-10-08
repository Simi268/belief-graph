from app.agent import AgentRuntime
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)


def test_multi_belief_impact_merges_shared_dependencies():

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
    # COMBINED IMPACT
    # ==================================================

    impact = agent.graph.analyze_multi_belief_impact(
        changed_nodes=["B1", "B2"]
    )

    # ==================================================
    # C1 — SHARED DEPENDENCY
    # ==================================================

    assert "C1" in impact

    assert impact["C1"]["impact"] == (
        NodeStatus.INVALID
    )

    assert set(
        impact["C1"]["affected_by"]
    ) == {"B1", "B2"}

    assert impact["C1"]["depth"] == 1

    # ==================================================
    # P1 — DOWNSTREAM SHARED DEPENDENCY
    # ==================================================

    assert "P1" in impact

    assert impact["P1"]["impact"] == (
        NodeStatus.INVALID
    )

    assert set(
        impact["P1"]["affected_by"]
    ) == {"B1", "B2"}

    assert impact["P1"]["depth"] == 2

    # ==================================================
    # VERIFY DEPENDENCY INFORMATION
    # ==================================================

    assert (
        DependencyType.REQUIRES
        in impact["C1"]["dependency_types"]
    )

    assert (
        DependencyType.REQUIRES
        in impact["P1"]["dependency_types"]
    )