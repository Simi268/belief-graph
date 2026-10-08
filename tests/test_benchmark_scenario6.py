from app.benchmark import BenchmarkRunner


def test_scenario6_benchmark_returns_all_strategies():
    results = BenchmarkRunner().run_scenario6_all()

    assert len(results) == 3

    strategies = {result.strategy for result in results}

    assert strategies == {
        "baseline",
        "memory",
        "belief_graph",
    }


def test_scenario6_belief_graph_matches_ground_truth():
    results = BenchmarkRunner().run_scenario6_all()

    belief_graph = next(
        result
        for result in results
        if result.strategy == "belief_graph"
    )

    assert belief_graph.task_success is True
    assert belief_graph.recovery_success is True

    assert belief_graph.affected_node_count == 4
    assert belief_graph.invalidated_node_count == 4
    assert belief_graph.invalid_plans == 1

    assert belief_graph.recomputed_node_count == 0
    assert belief_graph.unnecessary_recomputation == 0

    assert belief_graph.preserved_node_count == 4
    assert belief_graph.preservation_ratio == 0.5

    assert belief_graph.propagation_depth == 3

    assert belief_graph.details["detected_affected_nodes"] == [
        "A1",
        "B1",
        "C1",
        "P1",
    ]

    assert belief_graph.details["preserved_nodes"] == [
        "A2",
        "B2",
        "C2",
        "P2",
    ]


def test_scenario6_memory_recomputes_unnecessary_nodes():
    results = BenchmarkRunner().run_scenario6_all()

    memory = next(
        result
        for result in results
        if result.strategy == "memory"
    )

    assert memory.task_success is True
    assert memory.recomputed_node_count == 8
    assert memory.unnecessary_recomputation == 4
    assert memory.preserved_node_count == 0
    assert memory.preservation_ratio == 0.0


def test_scenario6_baseline_detects_stale_action():
    results = BenchmarkRunner().run_scenario6_all()

    baseline = next(
        result
        for result in results
        if result.strategy == "baseline"
    )

    assert baseline.task_success is False
    assert baseline.stale_actions == 1
    assert baseline.stale_plans == 1

    # Baseline does not perform dependency-aware impact analysis.
    assert baseline.affected_node_count == 0
    assert baseline.invalidated_node_count == 0

    assert baseline.details["ground_truth_affected_nodes"] == [
        "A1",
        "B1",
        "C1",
        "P1",
    ]

    assert baseline.details["strategy_detected_affected_nodes"] == []