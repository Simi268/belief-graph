from app.graph import BeliefGraph
from app.models import BeliefNode, NodeType, DependencyType
from app.baseline_strategies import BeliefGraphStrategy


def build_shared_dependency_graph():
    graph = BeliefGraph()

    nodes = [
        BeliefNode(
            id="B1",
            node_type=NodeType.BELIEF,
            content="API version is v1",
        ),
        BeliefNode(
            id="B2",
            node_type=NodeType.BELIEF,
            content="Authentication is supported",
        ),
        BeliefNode(
            id="C1",
            node_type=NodeType.CONCLUSION,
            content="The API is usable",
        ),
        BeliefNode(
            id="P1",
            node_type=NodeType.PLAN,
            content="Retrieve customer data",
        ),
        BeliefNode(
            id="A1",
            node_type=NodeType.ACTION,
            content="Call customer API",
        ),
        BeliefNode(
            id="B3",
            node_type=NodeType.BELIEF,
            content="Independent database is available",
        ),
    ]

    for node in nodes:
        graph.add_node(node)

    # Two beliefs support the same conclusion.
    graph.add_dependency("B1", "C1", DependencyType.REQUIRES)
    graph.add_dependency("B2", "C1", DependencyType.REQUIRES)

    # The conclusion supports the downstream plan and action.
    graph.add_dependency("C1", "P1", DependencyType.REQUIRES)
    graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

    return graph


def test_shared_dependency_is_classified_once():
    graph = build_shared_dependency_graph()

    expected_affected = {"B1", "C1", "P1", "A1"}

    result = BeliefGraphStrategy().evaluate(
        graph,
        changed_node="B1",
        expected_affected=expected_affected,
    )

    assert result.success is True
    assert set(result.affected_nodes) == expected_affected
    assert len(result.affected_nodes) == len(set(result.affected_nodes))


def test_unrelated_beliefs_remain_preserved():
    graph = build_shared_dependency_graph()

    expected_affected = {"B1", "C1", "P1", "A1"}

    result = BeliefGraphStrategy().evaluate(
        graph,
        changed_node="B1",
        expected_affected=expected_affected,
    )

    assert "B3" in result.preserved_nodes
    assert "B2" in result.preserved_nodes