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
        if not seeds:
            raise ValueError("At least one seed is required.")
        if len(set(seeds)) != len(seeds):
            raise ValueError("Seeds must be unique.")

        instances = [generator(seed) for seed in seeds]

        if len({x.instance_id for x in instances}) != len(instances):
            raise ValueError("Generated instance IDs must be unique.")

        return instances

    def run(self, instances: list[BenchmarkInstance]) -> list[SeedResult]:
        if not instances:
            raise ValueError("At least one benchmark instance is required.")

        results = []

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

                results.append(result)

        return results

    def aggregate(
        self, results: list[SeedResult]
    ) -> list[StrategyAggregate]:
        if not results:
            raise ValueError("Cannot aggregate an empty result set.")

        by_strategy: dict[str, list[SeedResult]] = {}

        for result in results:
            by_strategy.setdefault(result.strategy, []).append(result)

        aggregates = []

        for strategy, strategy_results in by_strategy.items():
            metric_names = set(strategy_results[0].metrics)

            for result in strategy_results[1:]:
                if set(result.metrics) != metric_names:
                    raise ValueError(
                        f"Inconsistent metric schema for strategy {strategy!r}."
                    )

            metrics = []

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
    def results_to_dict(results):
        return [asdict(result) for result in results]

    @staticmethod
    def aggregates_to_dict(aggregates):
        return [asdict(aggregate) for aggregate in aggregates]
