"""Reproducible multi-strategy recovery benchmark with explicit summaries.

The exported report separates actual recomputation from benchmark simulation.
Benchmark adapter timing is not equivalent to end-to-end agent runtime, and
semantic task/recovery success remains unknown unless a strategy verifies it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any, Callable

from .benchmark_instances import (
    BenchmarkInstance,
    generate_scenario1_instance,
    generate_scenario2_instance,
    generate_scenario3_instance,
    generate_scenario4_instance,
    generate_scenario5_instance,
    generate_scenario6_instance,
    generate_scenario7_instance,
)
from .seeded_strategy_adapters import (
    run_seeded_baseline,
    run_seeded_memory,
    run_seeded_belief_graph,
)


ScenarioGenerator = Callable[..., BenchmarkInstance]


SCENARIO_GENERATORS: dict[str, ScenarioGenerator] = {
    "scenario1": generate_scenario1_instance,
    "scenario2": generate_scenario2_instance,
    "scenario3": generate_scenario3_instance,
    "scenario4": generate_scenario4_instance,
    "scenario5": generate_scenario5_instance,
    "scenario6": generate_scenario6_instance,
    "scenario7": generate_scenario7_instance,
}

STRATEGIES = (
    ("baseline", run_seeded_baseline),
    ("memory", run_seeded_memory),
    ("belief_graph", run_seeded_belief_graph),
)


@dataclass
class StrategyMeasurement:
    scenario: str
    seed: int
    instance_id: str
    strategy: str
    elapsed_seconds: float
    metrics: dict[str, Any]
    details: dict[str, Any] = field(default_factory=dict)


def measure_strategy(
    instance: BenchmarkInstance,
    evaluator: Callable[[BenchmarkInstance], Any],
    scenario: str = "unspecified",
) -> StrategyMeasurement:
    """Measure one strategy without hiding evaluator failures."""
    start = perf_counter()
    result = evaluator(instance)
    elapsed = perf_counter() - start

    return StrategyMeasurement(
        scenario=scenario,
        seed=getattr(instance, "seed", 0),
        instance_id=getattr(instance, "instance_id", "unknown"),
        strategy=result.strategy,
        elapsed_seconds=elapsed,
        metrics=dict(result.metrics),
        details=dict(result.details),
    )


def compare_strategies(
    instance: BenchmarkInstance,
    scenario: str = "unspecified",
) -> list[StrategyMeasurement]:
    """Evaluate the currently registered strategy functions on one instance.

    Resolve the module-level functions at call time rather than relying on the
    import-time STRATEGIES tuple. This keeps the registry patchable for tests,
    instrumentation, and controlled benchmark experiments.
    """
    evaluators = (
        ("baseline", run_seeded_baseline),
        ("memory", run_seeded_memory),
        ("belief_graph", run_seeded_belief_graph),
    )
    return [
        measure_strategy(instance=instance, evaluator=evaluator, scenario=scenario)
        for _, evaluator in evaluators
    ]


def generate_instance(scenario: str, seed: int) -> BenchmarkInstance:
    """Generate a scenario instance using its registered generator."""
    try:
        generator = SCENARIO_GENERATORS[scenario]
    except KeyError as exc:
        raise ValueError(
            f"Unknown scenario {scenario!r}. "
            f"Choose from: {', '.join(SCENARIO_GENERATORS)}"
        ) from exc
    return generator(seed=seed)


def run_experiment(
    scenarios: list[str] | None = None,
    seeds: list[int] | None = None,
) -> list[StrategyMeasurement]:
    """Run every selected strategy on every selected scenario and seed."""
    selected_scenarios = (
        list(SCENARIO_GENERATORS) if scenarios is None else list(scenarios)
    )
    selected_seeds = [1, 2, 3, 4, 5] if seeds is None else list(seeds)

    unknown = set(selected_scenarios) - set(SCENARIO_GENERATORS)
    if unknown:
        raise ValueError(f"Unknown scenarios: {sorted(unknown)}")
    if not selected_scenarios:
        raise ValueError("At least one scenario is required.")
    if not selected_seeds:
        raise ValueError("At least one seed is required.")
    if len(set(selected_scenarios)) != len(selected_scenarios):
        raise ValueError("Scenario names must not be duplicated.")
    if len(set(selected_seeds)) != len(selected_seeds):
        raise ValueError("Seeds must not be duplicated.")

    measurements: list[StrategyMeasurement] = []
    for scenario in selected_scenarios:
        for seed in selected_seeds:
            instance = generate_instance(scenario, seed)
            measurements.extend(compare_strategies(instance, scenario))
    return measurements


def _numeric_summary(values: list[Any]) -> dict[str, Any]:
    """Summarize finite numeric values, excluding booleans and nulls."""
    numeric = [
        float(value)
        for value in values
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
    ]
    if not numeric:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(numeric),
        "mean": mean(numeric),
        "median": median(numeric),
        "min": min(numeric),
        "max": max(numeric),
    }


def summarize_measurements(
    measurements: list[StrategyMeasurement],
) -> dict[str, Any]:
    """Aggregate metrics per strategy while preserving unknown values as unknown."""
    by_strategy: dict[str, list[StrategyMeasurement]] = {}
    for measurement in measurements:
        by_strategy.setdefault(measurement.strategy, []).append(measurement)

    metric_names = sorted(
        {
            metric_name
            for measurement in measurements
            for metric_name in measurement.metrics
        }
    )
    summary: dict[str, Any] = {}

    for strategy, rows in sorted(by_strategy.items()):
        metric_summary: dict[str, Any] = {}
        for metric_name in metric_names:
            values = [
                row.metrics.get(metric_name)
                for row in rows
                if metric_name in row.metrics
            ]
            numeric = _numeric_summary(values)
            if numeric["count"]:
                metric_summary[metric_name] = numeric
            else:
                # Keep the number of known/unknown values visible for metrics
                # such as task_success and recovery_success.
                known = [value for value in values if value is not None]
                metric_summary[metric_name] = {
                    "count": 0,
                    "known_count": len(known),
                    "unknown_count": len(values) - len(known),
                    "values": sorted({str(value) for value in known}),
                }

        operation_metric_names = (
            "nodes_visited",
            "dependency_edges_examined",
            "impact_classifications_computed",
        )
        graph_operation_summary: dict[str, Any] = {}
        for operation_name in operation_metric_names:
            operation_values = [
                row.details.get("graph_operation_metrics", {}).get(operation_name)
                for row in rows
                if isinstance(row.details.get("graph_operation_metrics"), dict)
                and operation_name
                in row.details.get("graph_operation_metrics", {})
            ]
            if operation_values:
                graph_operation_summary[operation_name] = _numeric_summary(
                    operation_values
                )

        summary[strategy] = {
            "evaluations": len(rows),
            "mean_runtime_ms": mean(row.elapsed_seconds for row in rows) * 1000,
            "median_runtime_ms": median(row.elapsed_seconds for row in rows) * 1000,
            "metrics": metric_summary,
            "graph_operation_metrics": graph_operation_summary,
        }

    return summary


def export_json(
    measurements: list[StrategyMeasurement],
    output_path: str | Path,
) -> Path:
    """Export individual measurements plus aggregate strategy summaries."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    scenario_names = sorted({measurement.scenario for measurement in measurements})
    seeds = sorted({measurement.seed for measurement in measurements})
    strategies = sorted({measurement.strategy for measurement in measurements})

    payload = {
        "experiment": "belief_graph_recovery_comparison",
        "measurement_count": len(measurements),
        "scenarios": scenario_names,
        "seeds": seeds,
        "strategies": strategies,
        "design": {
            "scenario_count": len(scenario_names),
            "seed_count": len(seeds),
            "strategy_count": len(strategies),
            "expected_measurements": len(scenario_names) * len(seeds) * len(strategies),
        },
        "metric_semantics": {
            "recomputed_node_count": (
                "Actual recomputation count. Remains zero for benchmark adapters "
                "that do not execute real node/task recomputation."
            ),
            "simulated_recomputed_node_count": (
                "Number of benchmark-level simulated recomputation invocations; "
                "not evidence of real task execution."
            ),
            "task_success": (
                "Unknown/null when the scenario contains no executable task "
                "payload and verified expected output."
            ),
            "recovery_success": (
                "Unknown/null unless recovery is semantically executed and verified."
            ),
            "recovery_execution_success": (
                "Success of the benchmark-level simulation only when the adapter "
                "labels its recovery execution mode as benchmark_simulation."
            ),
            "elapsed_seconds": (
                "Adapter execution time, not end-to-end agent runtime."
            ),
        },
        "interpretation_warning": (
            "Strategies have different policies. Compare metric semantics, not just "
            "raw values. BeliefGraph's simulated recomputation is reported separately "
            "from actual recomputation; simulated success is not semantic task success."
        ),
        "summary_by_strategy": summarize_measurements(measurements),
        "results": [asdict(measurement) for measurement in measurements],
    }

    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return path


def main() -> None:
    measurements = run_experiment()
    output = export_json(
        measurements,
        "experiments/results/recovery_comparison.json",
    )

    print(f"Measurements: {len(measurements)}")
    print(f"Scenarios: {len({measurement.scenario for measurement in measurements})}")
    print(f"Seeds: {len({measurement.seed for measurement in measurements})}")
    print(f"Strategies: {sorted({measurement.strategy for measurement in measurements})}")
    print("Summary by strategy:")
    print(json.dumps(summarize_measurements(measurements), indent=2))
    print(f"JSON exported to: {output}")


if __name__ == "__main__":
    main()
