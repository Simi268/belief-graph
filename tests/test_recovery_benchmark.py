from types import SimpleNamespace

import pytest

from app.recovery_benchmark import (
    StrategyMeasurement,
    compare_strategies,
    measure_strategy,
)


def test_measure_strategy_records_elapsed_time_and_metrics():
    """The measurement should preserve the evaluator's actual output."""

    expected_metrics = {
        "task_success": True,
        "stale_actions": 0,
        "recomputed_node_count": 3,
    }

    expected_details = {
        "strategy_behavior": "test_policy",
    }

    def evaluator(instance):
        return SimpleNamespace(
            strategy="test_strategy",
            metrics=expected_metrics,
            details=expected_details,
        )

    result = measure_strategy(
        instance=object(),
        evaluator=evaluator,
    )

    assert isinstance(result, StrategyMeasurement)
    assert result.strategy == "test_strategy"
    assert result.metrics == expected_metrics
    assert result.details == expected_details
    assert result.elapsed_seconds >= 0


def test_measure_strategy_copies_metrics_and_details():
    """Later mutations to the evaluator's dictionaries must not alter results."""

    metrics = {"task_success": True}
    details = {"note": "original"}

    def evaluator(instance):
        return SimpleNamespace(
            strategy="test_strategy",
            metrics=metrics,
            details=details,
        )

    result = measure_strategy(object(), evaluator)

    metrics["task_success"] = False
    details["note"] = "modified"

    assert result.metrics["task_success"] is True
    assert result.details["note"] == "original"


def test_measure_strategy_propagates_evaluator_errors():
    """Failed evaluations must not silently become successful results."""

    def evaluator(instance):
        raise RuntimeError("simulated evaluation failure")

    with pytest.raises(
        RuntimeError,
        match="simulated evaluation failure",
    ):
        measure_strategy(object(), evaluator)


def test_compare_strategies_returns_all_three_strategies():
    """The comparison must invoke all three registered strategy adapters."""

    from app import recovery_benchmark

    calls = []

    def fake_evaluator(name):
        def evaluate(instance):
            calls.append((name, instance))
            return SimpleNamespace(
                strategy=name,
                metrics={"task_success": True},
                details={},
            )

        return evaluate

    original_evaluators = (
        recovery_benchmark.run_seeded_baseline,
        recovery_benchmark.run_seeded_memory,
        recovery_benchmark.run_seeded_belief_graph,
    )

    try:
        recovery_benchmark.run_seeded_baseline = fake_evaluator("baseline")
        recovery_benchmark.run_seeded_memory = fake_evaluator("memory")
        recovery_benchmark.run_seeded_belief_graph = fake_evaluator(
            "belief_graph"
        )

        instance = object()
        results = compare_strategies(instance)

        assert [result.strategy for result in results] == [
            "baseline",
            "memory",
            "belief_graph",
        ]

        assert len(calls) == 3
        assert all(called_instance is instance for _, called_instance in calls)

    finally:
        (
            recovery_benchmark.run_seeded_baseline,
            recovery_benchmark.run_seeded_memory,
            recovery_benchmark.run_seeded_belief_graph,
        ) = original_evaluators


def test_comparison_does_not_hide_failed_strategy():
    """A strategy failure must remain visible to the caller."""

    from app import recovery_benchmark

    original_baseline = recovery_benchmark.run_seeded_baseline
    original_memory = recovery_benchmark.run_seeded_memory
    original_belief_graph = recovery_benchmark.run_seeded_belief_graph

    try:
        recovery_benchmark.run_seeded_baseline = lambda instance: (
            SimpleNamespace(
                strategy="baseline",
                metrics={},
                details={},
            )
        )

        def fail(instance):
            raise RuntimeError("memory strategy failed")

        recovery_benchmark.run_seeded_memory = fail
        recovery_benchmark.run_seeded_belief_graph = lambda instance: (
            SimpleNamespace(
                strategy="belief_graph",
                metrics={},
                details={},
            )
        )

        with pytest.raises(RuntimeError, match="memory strategy failed"):
            compare_strategies(object())

    finally:
        recovery_benchmark.run_seeded_baseline = original_baseline
        recovery_benchmark.run_seeded_memory = original_memory
        recovery_benchmark.run_seeded_belief_graph = original_belief_graph