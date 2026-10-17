"""Reproducible multi-strategy recovery benchmark."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
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
    """Evaluate strategies using shared, category-aware ground truth."""
    evaluators = (
        run_seeded_baseline,
        run_seeded_memory,
        run_seeded_belief_graph,
    )

    measurements = []

    expected_categories = None

    if all(
        hasattr(instance, attr)
        for attr in (
            "expected_invalidated",
            "expected_reevaluation",
            "expected_uncertain",
            "expected_preserved",
        )
    ):
        expected_categories = {
            "invalidated_nodes": set(instance.expected_invalidated),
            "reevaluation_nodes": set(instance.expected_reevaluation),
            "uncertain_nodes": set(instance.expected_uncertain),
            "preserved_nodes": set(instance.expected_preserved),
        }

    for evaluator in evaluators:
        measurement = measure_strategy(
            instance=instance,
            evaluator=evaluator,
            scenario=scenario,
        )

        details = measurement.details

        # Only evaluate category-level predictions when the strategy
        # explicitly exposes all four categories.
        has_all_categories = (
            expected_categories is not None
            and all(key in details for key in expected_categories)
        )
        measurement.metrics["impact_classification_available"] = (
            has_all_categories
        )

        if has_all_categories:
            category_matches = {
                category: set(details[category]) == expected
                for category, expected in expected_categories.items()
            }

            measurement.metrics["category_exact_matches"] = (
                category_matches
            )
            measurement.metrics["impact_ground_truth_match"] = all(
                category_matches.values()
            )

            measurement.metrics["impact_true_positives"] = sum(
                len(set(details[category]) & expected)
                for category, expected in expected_categories.items()
                if category != "preserved_nodes"
            )

            measurement.metrics["impact_false_positives"] = sum(
                len(set(details[category]) - expected)
                for category, expected in expected_categories.items()
                if category != "preserved_nodes"
            )

            measurement.metrics["impact_false_negatives"] = sum(
                len(expected - set(details[category]))
                for category, expected in expected_categories.items()
                if category != "preserved_nodes"
            )
        else:
            measurement.metrics["category_exact_matches"] = None
            measurement.metrics["impact_ground_truth_match"] = None
            measurement.metrics["impact_true_positives"] = None
            measurement.metrics["impact_false_positives"] = None
            measurement.metrics["impact_false_negatives"] = None

        measurements.append(measurement)

    return measurements


def generate_instance(
    scenario: str,
    seed: int,
) -> BenchmarkInstance:
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
    selected_scenarios = scenarios or list(SCENARIO_GENERATORS)
    selected_seeds = seeds or [1, 2, 3, 4, 5]

    unknown = set(selected_scenarios) - set(SCENARIO_GENERATORS)
    if unknown:
        raise ValueError(f"Unknown scenarios: {sorted(unknown)}")

    if not selected_seeds:
        raise ValueError("At least one seed is required.")

    measurements: list[StrategyMeasurement] = []

    for scenario in selected_scenarios:
        for seed in selected_seeds:
            instance = generate_instance(scenario, seed)
            measurements.extend(compare_strategies(instance, scenario))

    return measurements


def export_json(
    measurements: list[StrategyMeasurement],
    output_path: str | Path,
) -> Path:
    """Export measurements as structured JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "experiment": "belief_graph_recovery_comparison",
        "measurement_count": len(measurements),
        "scenarios": sorted({m.scenario for m in measurements}),
        "seeds": sorted({m.seed for m in measurements}),
        "strategies": sorted({m.strategy for m in measurements}),
        "interpretation_warning": (
            "Elapsed time measures adapter execution, not necessarily "
            "full agent runtime. Strategy semantics differ; metrics "
            "must be interpreted according to each strategy's policy."
        ),
        "results": [asdict(m) for m in measurements],
    }

    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
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
    print(f"Scenarios: {len({m.scenario for m in measurements})}")
    print(f"Seeds: {len({m.seed for m in measurements})}")
    print(f"Strategies: {sorted({m.strategy for m in measurements})}")
    print(f"JSON exported to: {output}")


if __name__ == "__main__":
    main()