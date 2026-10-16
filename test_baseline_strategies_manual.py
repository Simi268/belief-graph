from app.graph import BeliefGraph
from app.models import BeliefNode, NodeType, DependencyType
from app.baseline_strategies import (
    NaiveBaseline,
    FullRecomputationBaseline,
    BeliefGraphStrategy,
)


def build_test_graph():
    graph = BeliefGraph()

    # Dependency chain:
    # B1 -> C1 -> P1 -> A1
    #
    # B2 is independent and should remain unaffected.

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

    # Add nodes to the graph.
    for node in nodes:
        graph.add_node(node)

    # Define dependencies.
    graph.add_dependency("B1", "C1", DependencyType.REQUIRES)
    graph.add_dependency("C1", "P1", DependencyType.REQUIRES)
    graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

    return graph


def main():
    graph = build_test_graph()

    # Expected affected nodes when B1 changes.
    expected_affected = {"B1", "C1", "P1", "A1"}

    strategies = [
        NaiveBaseline(),
        FullRecomputationBaseline(),
        BeliefGraphStrategy(),
    ]

    for strategy in strategies:
        result = strategy.evaluate(
            graph,
            changed_node="B1",
            expected_affected=expected_affected,
        )

        print("\n" + "=" * 50)
        print(f"Strategy: {result.strategy}")
        print(f"Affected nodes: {result.affected_nodes}")
        print(f"Invalidated nodes: {result.invalidated_nodes}")
        print(f"Preserved nodes: {result.preserved_nodes}")
        print(f"Recomputed nodes: {result.recomputed_nodes}")
        print(f"Stale nodes: {result.stale_nodes}")
        print(f"Operations: {result.operations}")
        print(f"Classification correct: {result.success}")
        print(f"Details: {result.details}")


if __name__ == "__main__":
    main()