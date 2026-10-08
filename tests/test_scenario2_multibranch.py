import pytest

from app.agent import AgentRuntime
from app.models import (
    DependencyType,
    NodeStatus,
    NodeType,
)


def build_multi_branch_graph():
    """
    Scenario #2:

                    B1
                    |
                   C1
          +---------+---------+
          |         |         |
       REQUIRES   SUPPORTS   CONTEXT
          |         |         |
         P1        P2        P3
          |         |         |
         A1        A2        A3

                    B4
                    |
                   C4
                    |
                   P4
                    |
                   A4

    B1 is the changed belief.
    B4 is an unrelated branch.
    """

    agent = AgentRuntime()

    # ------------------------------------------------------
    # SHARED BELIEF
    # ------------------------------------------------------

    agent.create_belief(
        belief_id="B1",
        content="API supports version v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge",
    )

    agent.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="The customer API can be used",
    )

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.REQUIRES,
    )

    # ------------------------------------------------------
    # BRANCH 1 — REQUIRES
    # ------------------------------------------------------

    agent.create_node(
        node_id="P1",
        node_type=NodeType.PLAN,
        content="Retrieve customer data",
    )

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API",
    )

    agent.add_dependency(
        "C1",
        "P1",
        DependencyType.REQUIRES,
    )

    agent.add_dependency(
        "P1",
        "A1",
        DependencyType.REQUIRES,
    )

    # ------------------------------------------------------
    # BRANCH 2 — SUPPORTS
    # ------------------------------------------------------

    agent.create_node(
        node_id="P2",
        node_type=NodeType.PLAN,
        content="Use API-backed customer workflow",
    )

    agent.create_node(
        node_id="A2",
        node_type=NodeType.ACTION,
        content="Process customer workflow",
    )

    agent.add_dependency(
        "C1",
        "P2",
        DependencyType.SUPPORTS,
    )

    agent.add_dependency(
        "P2",
        "A2",
        DependencyType.REQUIRES,
    )

    # ------------------------------------------------------
    # BRANCH 3 — CONTEXT
    # ------------------------------------------------------

    agent.create_node(
        node_id="P3",
        node_type=NodeType.PLAN,
        content="Prepare API request context",
    )

    agent.create_node(
        node_id="A3",
        node_type=NodeType.ACTION,
        content="Execute contextual request",
    )

    agent.add_dependency(
        "C1",
        "P3",
        DependencyType.CONTEXT,
    )

    agent.add_dependency(
        "P3",
        "A3",
        DependencyType.REQUIRES,
    )

    # ------------------------------------------------------
    # UNRELATED BRANCH
    # ------------------------------------------------------

    agent.create_belief(
        belief_id="B4",
        content="Authentication token is valid",
        value=True,
        confidence=0.95,
        source="authentication-service",
    )

    agent.create_node(
        node_id="C4",
        node_type=NodeType.CONCLUSION,
        content="Authenticated requests can be executed",
    )

    agent.create_node(
        node_id="P4",
        node_type=NodeType.PLAN,
        content="Prepare authenticated request",
    )

    agent.create_node(
        node_id="A4",
        node_type=NodeType.ACTION,
        content="Send authenticated request",
    )

    agent.add_dependency(
        "B4",
        "C4",
        DependencyType.REQUIRES,
    )

    agent.add_dependency(
        "C4",
        "P4",
        DependencyType.REQUIRES,
    )

    agent.add_dependency(
        "P4",
        "A4",
        DependencyType.REQUIRES,
    )

    return agent


# ==========================================================
# TEST 1 — SHARED BELIEF HAS MULTIPLE DOWNSTREAM BRANCHES
# ==========================================================


def test_shared_belief_has_multiple_dependency_branches():

    agent = build_multi_branch_graph()

    impact = agent.graph.propagate_state_impact(
    "B1",
    NodeStatus.INVALID,
)

    assert "C1" in impact
    assert "P1" in impact
    assert "P2" in impact
    assert "P3" in impact

    # Unrelated branch must not appear.
    assert "B4" not in impact
    assert "C4" not in impact
    assert "P4" not in impact
    assert "A4" not in impact


# ==========================================================
# TEST 2 — REQUIRES BRANCH BECOMES INVALID
# ==========================================================


def test_requires_branch_becomes_invalid():

    agent = build_multi_branch_graph()

    impact = agent.graph.propagate_state_impact(
    "B1",
    NodeStatus.INVALID,
)

    assert impact["C1"]["impact"] == NodeStatus.INVALID
    assert impact["P1"]["impact"] == NodeStatus.INVALID
    assert impact["A1"]["impact"] == NodeStatus.INVALID


# ==========================================================
# TEST 3 — SUPPORTS BRANCH REQUIRES REEVALUATION
# ==========================================================


def test_supports_branch_requires_reevaluation():

    agent = build_multi_branch_graph()

    impact = agent.graph.propagate_state_impact(
    "B1",
    NodeStatus.INVALID,
)

    assert (
        impact["P2"]["impact"]
        == NodeStatus.REQUIRES_REEVALUATION
    )


# ==========================================================
# TEST 4 — CONTEXT BRANCH BECOMES UNCERTAIN
# ==========================================================


def test_context_branch_becomes_uncertain():

    agent = build_multi_branch_graph()

    impact = agent.graph.propagate_state_impact(
    "B1",
    NodeStatus.INVALID,
)
    assert (
        impact["P3"]["impact"]
        == NodeStatus.UNCERTAIN
    )


# ==========================================================
# TEST 5 — UNRELATED BRANCH REMAINS ACTIVE
# ==========================================================


def test_unrelated_branch_is_preserved():

    agent = build_multi_branch_graph()

    impact = agent.graph.propagate_state_impact(
    "B1",
    NodeStatus.INVALID,
)

    assert "B4" not in impact
    assert "C4" not in impact
    assert "P4" not in impact
    assert "A4" not in impact

    assert agent.graph.get_node(
        "B4"
    ).status == NodeStatus.ACTIVE

    assert agent.graph.get_node(
        "C4"
    ).status == NodeStatus.ACTIVE

    assert agent.graph.get_node(
        "P4"
    ).status == NodeStatus.ACTIVE

    assert agent.graph.get_node(
        "A4"
    ).status == NodeStatus.ACTIVE


# ==========================================================
# TEST 6 — PROPAGATION DEPTH
# ==========================================================


def test_multi_branch_propagation_depth():

    agent = build_multi_branch_graph()

    impact = agent.graph.propagate_state_impact(
    "B1",
    NodeStatus.INVALID,
)

    depths = [
        details["depth"]
        for details in impact.values()
        if isinstance(details, dict)
        and "depth" in details
    ]

    assert max(depths) == 3


# ==========================================================
# TEST 7 — SELECTIVE IMPACT
# ==========================================================


def test_only_dependency_region_is_affected():

    agent = build_multi_branch_graph()

    impact =agent.graph.propagate_state_impact(
    "B1",
    NodeStatus.INVALID,
)
    expected = {
        "C1",
        "P1",
        "A1",
        "P2",
        "P3",
    }

    assert set(impact.keys()) == expected