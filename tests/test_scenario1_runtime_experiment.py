"""Integration tests for the Scenario 1 benchmark runtime experiment."""

from app.scenario1_runtime_experiment import (
    run_belief_graph_runtime_experiment,
)


def test_runtime_experiment_recovers_from_api_version_change():
    result = run_belief_graph_runtime_experiment()

    assert result.success is True
    assert result.final_status == "recovered"
    assert result.recovery_status == "recovered"

    assert (
        result.initial_api_call["environment_result"]["error"]
        == "API_VERSION_MISMATCH"
    )

    assert (
        result.retry_result["environment_result"]["success"]
        is True
    )


def test_runtime_experiment_preserves_unrelated_branches():
    result = run_belief_graph_runtime_experiment()

    expected_preserved = {
        "B2_U_S0001",
        "C2_U_S0001",
        "P2_U_S0001",
        "A2_U_S0001",
        "B3_U_S0001",
        "C3_U_S0001",
        "P3_U_S0001",
        "A3_U_S0001",
    }

    assert expected_preserved.issubset(
        set(result.preserved_nodes)
    )

    assert expected_preserved.isdisjoint(
        set(result.affected_nodes)
    )


def test_runtime_experiment_invalidates_expected_dependency_chain():
    result = run_belief_graph_runtime_experiment()

    expected_invalidated = {
        "B1_S0001",
        "C1_S0001",
        "P1_S0001",
        "A1_S0001",
    }

    assert set(result.affected_nodes) == expected_invalidated

    assert result.ground_truth_validation["invalidated"]["match"]
    assert result.ground_truth_validation["preserved"]["match"]


def test_runtime_experiment_records_recovery_and_validation_trace():
    result = run_belief_graph_runtime_experiment()

    events = [entry["event"] for entry in result.trace]

    assert events == [
        "benchmark_instance_created",
        "environment_changed",
        "initial_action_execution",
        "recovery_completed",
        "replacement_action_execution",
        "ground_truth_validation",
        "experiment_completed",
    ]

    assert (
        result.trace[2]["result"]["environment_result"]["success"]
        is False
    )

    assert (
        result.trace[4]["result"]["environment_result"]["success"]
        is True
    )

    assert result.trace[5]["passed"] is True
    assert result.trace[6]["final_status"] == "recovered"
    assert result.trace[6]["ground_truth_validation_passed"] is True


def test_runtime_experiment_ground_truth_matches_all_statuses():
    result = run_belief_graph_runtime_experiment()

    validation = result.ground_truth_validation

    assert validation["passed"] is True
    assert validation["invalidated"]["match"] is True
    assert validation["reevaluation"]["match"] is True
    assert validation["uncertain"]["match"] is True
    assert validation["preserved"]["match"] is True


def test_environment_changes_again_before_recovery_retry(monkeypatch):
    from app.agent import AgentRuntime

    original_execute = AgentRuntime.execute_api_action
    call_count = 0

    def execute_with_second_environment_change(
        self,
        environment,
        belief_id,
        action_id=None,
    ):
        nonlocal call_count
        call_count += 1

        if call_count == 2:
            environment.set_api_version("v3")

        return original_execute(
            self,
            environment,
            belief_id,
            action_id,
        )

    monkeypatch.setattr(
        AgentRuntime,
        "execute_api_action",
        execute_with_second_environment_change,
    )

    result = run_belief_graph_runtime_experiment()

    assert call_count == 2
    assert result.success is False
    assert result.final_status == "retry_failed"
    assert result.recovery_status == "recovered"

    retry_environment_result = (
        result.retry_result["environment_result"]
    )

    assert retry_environment_result["error"] == "API_VERSION_MISMATCH"
    assert retry_environment_result["expected"] == "v3"
    assert retry_environment_result["received"] == "v2"

    # Recovery execution can fail while dependency-state validation passes.
    assert result.ground_truth_validation["passed"] is True