from app.benchmark import BenchmarkRunner


def test_naive_baseline_fails_after_api_version_change():
    runner = BenchmarkRunner()

    result = runner.run_baseline()

    assert result.strategy == "baseline"
    assert result.task_success is False
    assert result.recovery_success is False
    assert result.tool_calls == 1

    # Verify that the simulated environment rejected the stale version.
    environment_result = result.details["environment_result"]
    assert environment_result["success"] is False


def test_memory_baseline_recovers_after_api_version_change():
    runner = BenchmarkRunner()

    result = runner.run_memory_agent()

    assert result.strategy == "memory"
    assert result.task_success is True
    assert result.recovery_success is True
    assert result.tool_calls == 2

    # The first call uses stale knowledge.
    assert result.details["first_attempt"]["success"] is False

    # The second call uses the updated API version.
    assert result.details["second_attempt"]["success"] is True


def test_belief_graph_recovers_and_preserves_unrelated_nodes():
    runner = BenchmarkRunner()

    result = runner.run_belief_graph()

    assert result.strategy == "belief_graph"
    assert result.task_success is True
    assert result.recovery_success is True
    assert result.tool_calls == 2

    # Verify actual execution results, not just reported summary metrics.
    assert result.details["first_attempt"]["environment_result"]["success"] is False
    assert result.details["second_attempt"]["environment_result"]["success"] is True

    # Verify selective impact handling.
    assert result.propagation_depth == 3
    assert result.affected_node_count == 4
    assert result.preserved_node_count == 3

    assert set(result.details["affected_nodes"]) == {
        "B1", "C1", "P1", "A1"
    }
    assert set(result.details["preserved_nodes"]) == {
        "B3", "C3", "P3"
    }