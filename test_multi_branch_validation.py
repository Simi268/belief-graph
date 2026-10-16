from app.graph import BeliefGraph
from app.models import BeliefNode, NodeType, DependencyType
from app.baseline_strategies import BeliefGraphStrategy


def build_multi_branch_graph():
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
            content="Customer endpoint supports v1",
        ),
        BeliefNode(
            id="P1",
            node_type=NodeType.PLAN,
            content="Retrieve customer information",
        ),
        BeliefNode(
            id="A1",
            node_type=NodeType.ACTION,
            content="Call customer endpoint",
        ),
        BeliefNode(
            id="C2",
            node_type=NodeType.CONCLUSION,
            content="Reporting endpoint supports v1",
        ),
        BeliefNode(
            id="P2",
            node_type=NodeType.PLAN,
            content="Generate report",
        ),
        BeliefNode(
            id="A2",
            node_type=NodeType.ACTION,
            content="Call reporting endpoint",
        ),
        BeliefNode(
            id="B2",
            node_type=NodeType.BELIEF,
            content="Independent database is available",
        ),
        BeliefNode(
            id="C3",
            node_type=NodeType.CONCLUSION,
            content="Independent reporting remains possible",
        ),
    ]

    for node in nodes:
        graph.add_node(node)

    # Branch A
    graph.add_dependency("B1", "C1", DependencyType.REQUIRES)
    graph.add_dependency("C1", "P1", DependencyType.REQUIRES)
    graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

    # Branch B shares the original belief.
    graph.add_dependency("B1", "C2", DependencyType.REQUIRES)
    graph.add_dependency("C2", "P2", DependencyType.REQUIRES)
    graph.add_dependency("P2", "A2", DependencyType.REQUIRES)

    # Branch C is independent.
    graph.add_dependency("B2", "C3", DependencyType.REQUIRES)

    return graph


def test_multi_branch_impact_matches_ground_truth():
    graph = build_multi_branch_graph()

    expected_affected = {
        "B1", "C1", "P1", "A1", "C2", "P2", "A2"
    }

    result = BeliefGraphStrategy().evaluate(
        graph,
        changed_node="B1",
        expected_affected=expected_affected,
    )

    assert result.success is True
    assert set(result.affected_nodes) == expected_affected
    assert set(result.preserved_nodes) == {"B2", "C3"}


def test_multi_branch_recovery_does_not_recompute_independent_branch():
    graph = build_multi_branch_graph()

    expected_affected = {
        "B1", "C1", "P1", "A1", "C2", "P2", "A2"
    }

    result = BeliefGraphStrategy().evaluate(
        graph,
        changed_node="B1",
        expected_affected=expected_affected,
    )

    assert set(result.recomputed_nodes) == set()
    assert "B2" in result.preserved_nodes
    assert "C3" in result.preserved_nodes