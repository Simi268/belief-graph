from app.benchmark_instances import generate_scenario1_instance
from app.seeded_strategy_adapters import run_seeded_belief_graph


def test_seeded_belief_graph_reports_simulated_recovery_without_claiming_task_success():
    instance = generate_scenario1_instance(seed=1)

    result = run_seeded_belief_graph(instance)

    assert result.metrics["classification_success"] is True
    assert result.metrics["recovery_execution_success"] is True
    assert result.metrics["task_success"] is None
    assert result.metrics["recovery_success"] is None

    details = result.details
    assert details["recovery_execution_mode"] == "benchmark_simulation"
    assert details["semantic_task_execution_performed"] is False
    assert details["semantic_result_verification_performed"] is False
    assert set(details["recovery_execution_order"]) == {
        "C1_S0001",
        "P1_S0001",
        "A1_S0001",
    }
    assert details["uncertain_nodes_deferred_for_review"] == []
    # These are simulated callback invocations, not actual task recomputations.
    assert result.metrics["recomputed_node_count"] == 0
    assert result.metrics["simulated_recomputed_node_count"] == 3
    assert result.metrics["unnecessary_recomputation"] == 0
    assert result.metrics["simulated_unnecessary_recomputation"] == 0
    assert set(details["simulated_recomputed_nodes"]) == {
        "C1_S0001",
        "P1_S0001",
        "A1_S0001",
    }

