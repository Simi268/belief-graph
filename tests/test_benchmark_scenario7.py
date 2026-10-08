from app.benchmark import BenchmarkRunner


def test_scenario7_runs_all_strategies():
    runner = BenchmarkRunner()

    results = runner.run_scenario7_all()

    assert len(results) == 3
    assert [result.strategy for result in results] == [
        "baseline",
        "memory",
        "belief_graph",
    ]


def test_scenario7_belief_graph_matches_ground_truth():
    runner = BenchmarkRunner()

    results = runner.run_scenario7_all()
    belief_graph = next(
        result
        for result in results
        if result.strategy == "belief_graph"
    )

    assert belief_graph.task_success is True
    assert belief_graph.recovery_success is True
    assert belief_graph.invalid_plans == 1
    assert belief_graph.affected_node_count == 4
    assert belief_graph.invalidated_node_count == 4
    assert belief_graph.recomputed_node_count == 0
    assert belief_graph.unnecessary_recomputation == 0
    assert belief_graph.preserved_node_count == 4
    assert belief_graph.preservation_ratio == 0.5
    assert belief_graph.propagation_depth == 3


def test_scenario7_memory_recomputes_unnecessarily():
    runner = BenchmarkRunner()

    results = runner.run_scenario7_all()
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


def test_scenario7_baseline_uses_stale_information():
    runner = BenchmarkRunner()

    results = runner.run_scenario7_all()
    baseline = next(
        result
        for result in results
        if result.strategy == "baseline"
    )

    assert baseline.task_success is False
    assert baseline.stale_actions == 1
    assert baseline.stale_plans == 1
    assert baseline.recovery_success is False