from app.graph import BeliefGraph
from app.models import BeliefNode, NodeType, DependencyType
from app.baseline_strategies import (
    NaiveBaseline,
    FullRecomputationBaseline,
    BeliefGraphStrategy,
)


def build_test_graph():
    graph = BeliefGraph()

    nodes = [
        BeliefNode(
            id="B1",
            node_type=NodeType.BELIEF,
            content="API version is v1",
        ),
        BeliefNode(
            id="C1",
            node_type=NodeType.CONCLUSION,
            content="The API supports v1",
        ),
        BeliefNode(
            id="P1",
            node_type=NodeType.PLAN,
            content="Call the API using v1",
        ),
        BeliefNode(
            id="A1",
            node_type=NodeType.ACTION,
            content="Execute API request",
        ),
        BeliefNode(
            id="B2",
            node_type=NodeType.BELIEF,
            content="Independent fact",
        ),
    ]

    for node in nodes:
        graph.add_node(node)

    graph.add_dependency("B1", "C1", DependencyType.REQUIRES)
    graph.add_dependency("C1", "P1", DependencyType.REQUIRES)
    graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

    return graph


def test_belief_graph_matches_ground_truth():
    graph = build_test_graph()

    expected_affected = {"B1", "C1", "P1", "A1"}

    result = BeliefGraphStrategy().evaluate(
        graph,
        changed_node="B1",
        expected_affected=expected_affected,
    )

    assert result.success is True
    assert set(result.affected_nodes) == expected_affected
    assert set(result.preserved_nodes) == {"B2"}
    assert set(result.recomputed_nodes) == set()


def test_full_recomputation_includes_unaffected_node():
    graph = build_test_graph()

    expected_affected = {"B1", "C1", "P1", "A1"}

    result = FullRecomputationBaseline().evaluate(
        graph,
        changed_node="B1",
        expected_affected=expected_affected,
    )

    assert set(result.recomputed_nodes) == {
        "B1", "C1", "P1", "A1", "B2"
    }

    assert "B2" in result.details["unnecessary_recomputation"]


def test_naive_baseline_leaves_dependent_nodes_stale():
    graph = build_test_graph()

    expected_affected = {"B1", "C1", "P1", "A1"}

    result = NaiveBaseline().evaluate(
        graph,
        changed_node="B1",
        expected_affected=expected_affected,
    )

    assert set(result.stale_nodes) == {"C1", "P1", "A1"}
    assert result.success is False