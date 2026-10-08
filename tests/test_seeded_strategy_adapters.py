from app.benchmark_instances import generate_scenario2_instance
from app.multiseed_benchmark import MultiSeedBenchmarkRunner
from app.seeded_strategy_adapters import (
    run_seeded_baseline,
    run_seeded_belief_graph,
    run_seeded_memory,
    seeded_strategy_evaluators,
)


def test_seeded_baseline_matches_strategy_semantics():
    instance = generate_scenario2_instance(1)

    result = run_seeded_baseline(instance)

    assert result.strategy == "baseline"
    assert result.metrics["task_success"] is False
    assert result.metrics["stale_actions"] == 3
    assert result.metrics["stale_plans"] == 3

    # Baseline does not perform dependency-aware impact analysis.
    assert result.metrics["affected_node_count"] == 0
    assert result.metrics["invalidated_node_count"] == 0
    assert result.metrics["recomputed_node_count"] == 0
    assert result.metrics["preserved_node_count"] == 0
    assert result.metrics["preservation_ratio"] == 0.0

    assert result.details["dependency_tracking"] is False
    assert result.details["strategy_detected_affected_nodes"] == []

    assert (
        result.details["ground_truth_affected_node_count"]
        == len(instance.affected_nodes)
    )

    assert (
        result.details["ground_truth_preserved_node_count"]
        == len(instance.expected_preserved)
    )


def test_seeded_memory_matches_full_restart_semantics():
    instance = generate_scenario2_instance(1)

    result = run_seeded_memory(instance)

    assert result.strategy == "memory"
    assert result.metrics["task_success"] is True
    assert result.metrics["recomputed_node_count"] == 12
    assert result.metrics["unnecessary_recomputation"] == 6
    assert result.metrics["preserved_node_count"] == 0
    assert result.metrics["preservation_ratio"] == 0.0


def test_seeded_belief_graph_matches_ground_truth():
    instance = generate_scenario2_instance(1)

    result = run_seeded_belief_graph(instance)

    assert result.metrics["task_success"] is True
    assert result.metrics["affected_node_count"] == 6
    assert result.metrics["invalidated_node_count"] == 4
    assert result.metrics["invalid_plans"] == 1
    assert result.metrics["propagation_depth"] == 3
    assert result.metrics["preserved_node_count"] == 6
    assert result.metrics["preservation_ratio"] == 0.5


def test_seeded_belief_graph_uses_generated_namespace_directly():
    instance = generate_scenario2_instance(17)

    result = run_seeded_belief_graph(instance)

    assert result.metrics["task_success"] is True
    assert all(
        "_S0017" in node_id
        for node_id in result.details["affected_nodes"]
    )


def test_real_strategies_run_over_five_identical_seeded_instances():
    runner = MultiSeedBenchmarkRunner(seeded_strategy_evaluators())

    instances = runner.generate_instances(
        [1, 2, 3, 4, 5],
        generate_scenario2_instance,
    )
    results = runner.run(instances)

    assert len(results) == 15

    for instance in instances:
        rows = [
            result for result in results
            if result.instance_id == instance.instance_id
        ]
        assert {row.strategy for row in rows} == {
            "baseline",
            "memory",
            "belief_graph",
        }

    aggregates = runner.aggregate(results)

    assert {item.strategy for item in aggregates} == {
        "baseline",
        "memory",
        "belief_graph",
    }

    belief_graph = next(
        item for item in aggregates
        if item.strategy == "belief_graph"
    )

    preservation = next(
        metric for metric in belief_graph.metrics
        if metric.metric == "preservation_ratio"
    )

    assert preservation.mean == 0.5
    assert preservation.population_std == 0.0
