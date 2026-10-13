"""Integration tests for the Scenario 2 runtime experiment."""

from app.scenario2_runtime_experiment import (
    run_scenario2_runtime_experiment,
)


def test_scenario2_experiment_passes_ground_truth_validation():
    result = run_scenario2_runtime_experiment(seed=1)

    assert result.success is True
    assert result.validation["passed"] is True


def test_scenario2_invalidated_nodes_match_ground_truth():
    result = run_scenario2_runtime_experiment(seed=1)

    assert set(result.invalidated_nodes) == {
        "B1_S0001",
        "C1_S0001",
        "P1_S0001",
        "A1_S0001",
    }


def test_scenario2_reevaluation_nodes_match_ground_truth():
    result = run_scenario2_runtime_experiment(seed=1)

    assert set(result.reevaluation_nodes) == {
        "P2_S0001",
    }


def test_scenario2_uncertain_nodes_match_ground_truth():
    result = run_scenario2_runtime_experiment(seed=1)

    assert set(result.uncertain_nodes) == {
        "P3_S0001",
    }


def test_scenario2_preserves_independent_branch():
    result = run_scenario2_runtime_experiment(seed=1)

    assert {
        "B4_S0001",
        "C4_S0001",
        "P4_S0001",
        "A4_S0001",
    }.issubset(set(result.preserved_nodes))


def test_scenario2_detects_stale_actions():
    result = run_scenario2_runtime_experiment(seed=1)

    assert set(result.stale_actions) == {
        "A1_S0001",
        "A2_S0001",
        "A3_S0001",
    }


def test_scenario2_trace_contains_validation_event():
    result = run_scenario2_runtime_experiment(seed=1)

    event_names = {
        event["event"]
        for event in result.trace
    }

    assert "benchmark_instance_created" in event_names
    assert "state_impact_applied" in event_names
    assert "ground_truth_validation" in event_names