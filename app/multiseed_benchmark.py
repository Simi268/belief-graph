from dataclasses import dataclass, asdict
from statistics import mean, pstdev
from typing import Any, Callable

from .benchmark_instances import BenchmarkInstance


@dataclass(frozen=True)
class SeedResult:
    seed: int
    instance_id: str
    strategy: str
    metrics: dict[str, float | int | bool]
    details: dict[str, Any]


@dataclass(frozen=True)
class AggregateMetric:
    metric: str
    mean: float
    population_std: float


@dataclass(frozen=True)
class StrategyAggregate:
    strategy: str
    instances: int
    metrics: tuple[AggregateMetric, ...]


class MultiSeedBenchmarkRunner:
    """Run injected strategies over the exact same generated instances."""

    def __init__(
        self,
        strategy_evaluators: dict[
            str, Callable[[BenchmarkInstance], SeedResult]
        ],
    ) -> None:
        if not strategy_evaluators:
            raise ValueError("At least one strategy evaluator is required.")

        self.strategy_evaluators = dict(strategy_evaluators)

    def generate_instances(
        self,
        seeds: list[int] | tuple[int, ...],
        generator: Callable[[int], BenchmarkInstance],
    ) -> list[BenchmarkInstance]:
        """
        Generate and validate one deterministic benchmark instance per seed.

        The runner verifies that:
        - at least one seed was supplied,
        - seeds are unique,
        - the generator preserves the requested seed,
        - generated instance IDs are unique,
        - every generated BenchmarkInstance passes its own validation.
        """
        if not seeds:
            raise ValueError("At least one seed is required.")

        if len(set(seeds)) != len(seeds):
            raise ValueError("Seeds must be unique.")

        instances: list[BenchmarkInstance] = []

        for seed in seeds:
            instance = generator(seed)

            if instance.seed != seed:
                raise ValueError(
                    f"Generator returned instance seed {instance.seed}, "
                    f"expected {seed}."
                )

            instance.validate()
            instances.append(instance)

        if len({x.instance_id for x in instances}) != len(instances):
            raise ValueError("Generated instance IDs must be unique.")

        return instances

    def run(self, instances: list[BenchmarkInstance]) -> list[SeedResult]:
        """
        Evaluate every registered strategy on every generated instance.

        The runner enforces that each result corresponds exactly to the
        instance and strategy that produced it, and rejects duplicate
        (strategy, seed, instance) records.
        """
        if not instances:
            raise ValueError("At least one benchmark instance is required.")

        expected_seeds = {instance.seed for instance in instances}
        expected_instance_ids = {
            instance.seed: instance.instance_id
            for instance in instances
        }

        if len(expected_seeds) != len(instances):
            raise ValueError(
                "Benchmark instances must have unique seeds."
            )

        results: list[SeedResult] = []
        seen_keys: set[tuple[str, int, str]] = set()

        for instance in instances:
            for strategy_name, evaluator in self.strategy_evaluators.items():
                result = evaluator(instance)

                if result.seed != instance.seed:
                    raise ValueError(
                        f"{strategy_name} returned seed {result.seed}, "
                        f"expected {instance.seed}."
                    )

                if result.instance_id != instance.instance_id:
                    raise ValueError(
                        f"{strategy_name} returned instance "
                        f"{result.instance_id!r}, expected "
                        f"{instance.instance_id!r}."
                    )

                if result.strategy != strategy_name:
                    raise ValueError(
                        f"Evaluator registered as {strategy_name!r} "
                        f"returned strategy {result.strategy!r}."
                    )

                if result.seed not in expected_instance_ids:
                    raise ValueError(
                        f"Result contains unexpected seed {result.seed}."
                    )

                key = (
                    result.strategy,
                    result.seed,
                    result.instance_id,
                )

                if key in seen_keys:
                    raise ValueError(
                        "Duplicate benchmark result detected for "
                        f"strategy={result.strategy!r}, "
                        f"seed={result.seed}, "
                        f"instance={result.instance_id!r}."
                    )

                seen_keys.add(key)
                results.append(result)

        expected_result_count = (
            len(instances) * len(self.strategy_evaluators)
        )

        if len(results) != expected_result_count:
            raise ValueError(
                "Incomplete benchmark results: expected "
                f"{expected_result_count}, received {len(results)}."
            )

        return results

    def aggregate(
        self, results: list[SeedResult]
    ) -> list[StrategyAggregate]:
        """
        Aggregate results only when every registered strategy has exactly
        one result for every seed.

        This prevents partial strategy coverage from producing misleading
        aggregate statistics.
        """
        if not results:
            raise ValueError("Cannot aggregate an empty result set.")

        expected_strategies = set(self.strategy_evaluators)
        observed_strategies = {result.strategy for result in results}

        unexpected_strategies = observed_strategies - expected_strategies
        if unexpected_strategies:
            raise ValueError(
                "Results contain unregistered strategies: "
                f"{sorted(unexpected_strategies)}"
            )

        missing_strategies = expected_strategies - observed_strategies
        if missing_strategies:
            raise ValueError(
                "Results are missing registered strategies: "
                f"{sorted(missing_strategies)}"
            )

        expected_seeds = {result.seed for result in results}

        # Reject duplicate (strategy, seed, instance) records before
        # calculating means/stds.
        seen_keys: set[tuple[str, int, str]] = set()

        for result in results:
            key = (
                result.strategy,
                result.seed,
                result.instance_id,
            )

            if key in seen_keys:
                raise ValueError(
                    "Duplicate result cannot be aggregated for "
                    f"strategy={result.strategy!r}, "
                    f"seed={result.seed}, "
                    f"instance={result.instance_id!r}."
                )

            seen_keys.add(key)

        by_strategy: dict[str, list[SeedResult]] = {}

        for result in results:
            by_strategy.setdefault(result.strategy, []).append(result)

        # Every strategy must cover the same seed set.
        for strategy, strategy_results in by_strategy.items():
            strategy_seeds = {result.seed for result in strategy_results}

            if strategy_seeds != expected_seeds:
                missing = expected_seeds - strategy_seeds
                extra = strategy_seeds - expected_seeds

                raise ValueError(
                    f"Incomplete seed coverage for strategy "
                    f"{strategy!r}: missing={sorted(missing)}, "
                    f"extra={sorted(extra)}."
                )

            if len(strategy_results) != len(expected_seeds):
                raise ValueError(
                    f"Strategy {strategy!r} has "
                    f"{len(strategy_results)} results for "
                    f"{len(expected_seeds)} expected seeds."
                )

        aggregates: list[StrategyAggregate] = []

        for strategy, strategy_results in by_strategy.items():
            metric_names = set(strategy_results[0].metrics)

            for result in strategy_results[1:]:
                if set(result.metrics) != metric_names:
                    raise ValueError(
                        f"Inconsistent metric schema for strategy "
                        f"{strategy!r}."
                    )

            metrics: list[AggregateMetric] = []

            for metric in sorted(metric_names):
                values = [
                    float(result.metrics[metric])
                    for result in strategy_results
                ]

                metrics.append(
                    AggregateMetric(
                        metric=metric,
                        mean=mean(values),
                        population_std=pstdev(values),
                    )
                )

            aggregates.append(
                StrategyAggregate(
                    strategy=strategy,
                    instances=len(strategy_results),
                    metrics=tuple(metrics),
                )
            )

        return aggregates

    @staticmethod
    def results_to_dict(results: list[SeedResult]):
        return [asdict(result) for result in results]

    @staticmethod
    def aggregates_to_dict(
        aggregates: list[StrategyAggregate],
    ):
        return [asdict(aggregate) for aggregate in aggregates]
