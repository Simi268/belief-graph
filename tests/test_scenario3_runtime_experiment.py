"""Integration tests for the Scenario 3 runtime experiment."""

from app.scenario3_runtime_experiment import (
    run_scenario3_runtime_experiment,
)


def test_scenario3_experiment_passes_ground_truth_validation():
    result = run_scenario3_runtime_experiment(seed=1)

    assert result.success is True
    assert result.validation["passed"] is True


def test_scenario3_invalidates_only_the_affected_branch():
    result = run_scenario3_runtime_experiment(seed=1)

    assert set(result.invalidated_nodes) == {
        "B1_S0001",
        "C1_S0001",
        "P1_S0001",
        "A1_S0001",
    }


def test_scenario3_has_no_reevaluation_nodes():
    result = run_scenario3_runtime_experiment(seed=1)

    assert result.reevaluation_nodes == []


def test_scenario3_has_no_uncertain_nodes():
    result = run_scenario3_runtime_experiment(seed=1)

    assert result.uncertain_nodes == []


def test_scenario3_preserves_independent_branches():
    result = run_scenario3_runtime_experiment(seed=1)

    expected_preserved = {
        "B2_S0001",
        "C2_S0001",
        "P2_S0001",
        "A2_S0001",
        "B3_S0001",
        "C3_S0001",
        "P3_S0001",
        "A3_S0001",
        "B4_U_S0001",
        "C4_U_S0001",
        "P4_U_S0001",
        "A4_U_S0001",
    }

    assert set(result.preserved_nodes) == expected_preserved


def test_scenario3_detects_only_the_affected_stale_action():
    result = run_scenario3_runtime_experiment(seed=1)

    assert result.stale_actions == ["A1_S0001"]


def test_scenario3_trace_contains_validation_events():
    result = run_scenario3_runtime_experiment(seed=1)

    event_names = {
        event["event"]
        for event in result.trace
    }

    assert "benchmark_instance_created" in event_names
    assert "state_impact_applied" in event_names
    assert "ground_truth_validation" in event_names