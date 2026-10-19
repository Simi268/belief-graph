from app.benchmark_instances import generate_scenario2_instance
from app.seeded_strategy_adapters import run_seeded_belief_graph


def test_seeded_belief_graph_exposes_graph_operation_metrics():
    instance = generate_scenario2_instance(seed=1)

    result = run_seeded_belief_graph(instance)

    operation_metrics = result.details["graph_operation_metrics"]

    assert set(operation_metrics) == {
        "nodes_visited",
        "dependency_edges_examined",
        "impact_classifications_computed",
    }
    assert all(
        isinstance(value, int) and value >= 0
        for value in operation_metrics.values()
    )

    # Traversal instrumentation must not imply that recovery was executed.
    assert result.metrics["recomputed_node_count"] == 0
    assert result.details["direct_graph_execution"] is True
