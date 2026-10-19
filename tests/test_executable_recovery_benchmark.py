from app.executable_recovery_benchmark import (
    SCENARIO_CHANGED_BELIEFS,
    _new_graph,
    _run_one,
    run_experiment,
)


def test_selective_recovery_matches_full_recomputation_for_every_scenario_and_seed():
    for scenario in SCENARIO_CHANGED_BELIEFS:
        for seed in range(1, 6):
            result = _run_one(scenario, seed, "belief_graph")
            assert result["metrics"]["output_correct"] is True
            assert result["metrics"]["mismatched_node_count"] == 0
            assert result["metrics"]["preserved_derived_values_unchanged"] is True
            assert result["metrics"]["unnecessary_recomputation"] == 0
            assert result["metrics"]["recovery_success"] is True


def test_selective_recovery_recomputes_fewer_nodes_than_full_recompute():
    for scenario in SCENARIO_CHANGED_BELIEFS:
        selective = _run_one(scenario, 1, "belief_graph")
        full = _run_one(scenario, 1, "full_recompute")
        assert selective["metrics"]["output_correct"] is True
        assert full["metrics"]["output_correct"] is True
        assert (
            selective["metrics"]["recomputed_node_count"]
            <= full["metrics"]["recomputed_node_count"]
        )


def test_baseline_exposes_stale_derived_values_when_dependency_changes():
    result = _run_one("price_change", 1, "baseline")
    assert result["metrics"]["output_correct"] is False
    assert result["metrics"]["mismatched_node_count"] > 0


def test_disconnected_belief_change_recomputes_only_its_own_branch():
    result = _run_one("disconnected_belief_change", 1, "belief_graph")
    assert result["metrics"]["output_correct"] is True
    assert result["metrics"]["recomputed_node_count"] == 1
    assert result["details"]["recomputed_nodes"] == ["spare_metric"]


def test_experiment_has_expected_measurement_count_and_strategies():
    results = run_experiment()
    assert len(results) == 105
    assert {row["strategy"] for row in results} == {
        "baseline",
        "full_recompute",
        "belief_graph",
    }


def test_initial_derived_values_are_computed_from_beliefs():
    graph = _new_graph(1)
    assert graph.values["subtotal"] == graph.values["price"] * graph.values["quantity"]
    assert graph.values["tax"] == graph.values["subtotal"] * graph.values["tax_rate"]
