from app.agent import AgentRuntime
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)


def test_causal_recovery_identifies_only_affected_branch():

    agent = AgentRuntime()

    # ==================================================
    # CHANGED BELIEF
    # ==================================================

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="api-service"
    )

    # ==================================================
    # AFFECTED BRANCH
    # ==================================================

    agent.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="Customer data can be retrieved"
    )

    agent.create_node(
        node_id="P1",
        node_type=NodeType.PLAN,
        content="Retrieve customer data"
    )

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1"
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

    agent.add_dependency(
        "P1",
        "A1",
        DependencyType.REQUIRES
    )

    # ==================================================
    # UNRELATED BRANCH
    # ==================================================

    agent.create_belief(
        belief_id="B3",
        content="Reporting database is available",
        value=True,
        confidence=0.90,
        source="database"
    )

    agent.create_node(
        node_id="C3",
        node_type=NodeType.CONCLUSION,
        content="Reporting data can be generated"
    )

    agent.create_node(
        node_id="P3",
        node_type=NodeType.PLAN,
        content="Generate reporting data"
    )

    agent.add_dependency(
        "B3",
        "C3",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "C3",
        "P3",
        DependencyType.REQUIRES
    )

    # ==================================================
    # ANALYZE IMPACT
    # ==================================================

    impact = agent.graph.analyze_multi_belief_impact(
        changed_nodes=["B1"]
    )

    # ==================================================
    # AFFECTED NODES
    # ==================================================

    assert set(impact.keys()) == {
        "C1",
        "P1",
        "A1"
    }

    # ==================================================
    # VERIFY IMPACT STATES
    # ==================================================

    assert impact["C1"]["impact"] == NodeStatus.INVALID
    assert impact["P1"]["impact"] == NodeStatus.INVALID
    assert impact["A1"]["impact"] == NodeStatus.INVALID

    # ==================================================
    # VERIFY CAUSAL ANCESTRY
    # ==================================================

    assert set(
        impact["C1"]["affected_by"]
    ) == {"B1"}

    assert set(
        impact["P1"]["affected_by"]
    ) == {"B1"}

    assert set(
        impact["A1"]["affected_by"]
    ) == {"B1"}

    # ==================================================
    # UNRELATED BRANCH MUST NOT APPEAR
    # ==================================================

    assert "B3" not in impact
    assert "C3" not in impact
    assert "P3" not in impact


def test_causal_recovery_plan_separates_replanning_from_preservation():

    agent = AgentRuntime()

    # ==================================================
    # PRIMARY BRANCH
    # ==================================================

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="api-service"
    )

    agent.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="Customer data can be retrieved"
    )

    agent.create_node(
        node_id="P1",
        node_type=NodeType.PLAN,
        content="Retrieve customer data"
    )

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1"
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

    agent.add_dependency(
        "P1",
        "A1",
        DependencyType.REQUIRES
    )

    # ==================================================
    # PRESERVED BRANCH
    # ==================================================

    agent.create_belief(
        belief_id="B3",
        content="Reporting database is available",
        value=True,
        confidence=0.90,
        source="database"
    )

    agent.create_node(
        node_id="C3",
        node_type=NodeType.CONCLUSION,
        content="Reporting data can be generated"
    )

    agent.create_node(
        node_id="P3",
        node_type=NodeType.PLAN,
        content="Generate reporting data"
    )

    agent.add_dependency(
        "B3",
        "C3",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "C3",
        "P3",
        DependencyType.REQUIRES
    )

    # ==================================================
    # EXPECTED RECOVERY PLAN
    # ==================================================

    impact = agent.graph.analyze_multi_belief_impact(
        changed_nodes=["B1"]
    )

    # This is the interface we want to implement next.
    recovery_plan = agent.create_recovery_plan(
    impact=impact,
    changed_nodes=["B1"]
)

    # ==================================================
    # AFFECTED
    # ==================================================

    assert set(
        recovery_plan["affected_nodes"]
    ) == {
        "C1",
        "P1",
        "A1"
    }

    # ==================================================
    # REPLANNING
    # ==================================================

    assert set(
        recovery_plan["replan_nodes"]
    ) == {
        "P1",
        "A1"
    }

    # ==================================================
    # PRESERVED
    # ==================================================

    assert set(
        recovery_plan["preserved_nodes"]
    ) == {
        "B3",
        "C3",
        "P3"
    }

    # ==================================================
    # CAUSAL TRACE
    # ==================================================

    assert recovery_plan["causes"]["C1"] == ["B1"]
    assert recovery_plan["causes"]["P1"] == ["B1"]
    assert recovery_plan["causes"]["A1"] == ["B1"]