from dataclasses import dataclass
from typing import Any, Callable

from .benchmark_instances import BenchmarkInstance
from .multiseed_benchmark import (
    MultiSeedBenchmarkRunner,
    SeedResult,
    StrategyAggregate,
)


@dataclass(frozen=True)
class ExperimentReport:
    """
    Complete result of one controlled multi-strategy experiment.
    """

    seeds: tuple[int, ...]
    results: tuple[SeedResult, ...]
    aggregates: tuple[StrategyAggregate, ...]


class ExperimentRunner:
    """
    Runs multiple strategies over the exact same generated instances.

    The runner deliberately keeps experiment orchestration separate from:
    - scenario generation
    - strategy implementation
    - metric aggregation
    """

    def __init__(
        self,
        strategy_evaluators: dict[
            str, Callable[[BenchmarkInstance], SeedResult]
        ],
    ) -> None:
        self.runner = MultiSeedBenchmarkRunner(strategy_evaluators)

    def run(
        self,
        seeds: list[int] | tuple[int, ...],
        generator: Callable[[int], BenchmarkInstance],
    ) -> ExperimentReport:
        instances = self.runner.generate_instances(
            seeds=seeds,
            generator=generator,
        )

        results = self.runner.run(instances)
        aggregates = self.runner.aggregate(results)

        self._validate_experiment(
            seeds=seeds,
            instances=instances,
            results=results,
        )

        return ExperimentReport(
            seeds=tuple(seeds),
            results=tuple(results),
            aggregates=tuple(aggregates),
        )

    @staticmethod
    def _validate_experiment(
        seeds: list[int] | tuple[int, ...],
        instances: list[BenchmarkInstance],
        results: list[SeedResult],
    ) -> None:
        """
        Verify that every strategy was evaluated against the same instances.
        """

        expected_instances = {
            instance.seed: instance.instance_id
            for instance in instances
        }

        if len(expected_instances) != len(seeds):
            raise ValueError(
                "Experiment instances must have unique seeds."
            )

        for result in results:
            expected_instance_id = expected_instances.get(result.seed)

            if expected_instance_id is None:
                raise ValueError(
                    f"Result contains unexpected seed {result.seed}."
                )

            if result.instance_id != expected_instance_id:
                raise ValueError(
                    f"Strategy {result.strategy!r} evaluated "
                    f"instance {result.instance_id!r} for seed "
                    f"{result.seed}, expected "
                    f"{expected_instance_id!r}."
                )

    @staticmethod
    def report_to_dict(report: ExperimentReport) -> dict[str, Any]:
        return {
            "seeds": list(report.seeds),
            "results": [
                {
                    "seed": result.seed,
                    "instance_id": result.instance_id,
                    "strategy": result.strategy,
                    "metrics": result.metrics,
                    "details": result.details,
                }
                for result in report.results
            ],
            "aggregates": [
                {
                    "strategy": aggregate.strategy,
                    "instances": aggregate.instances,
                    "metrics": [
                        {
                            "metric": metric.metric,
                            "mean": metric.mean,
                            "population_std": metric.population_std,
                        }
                        for metric in aggregate.metrics
                    ],
                }
                for aggregate in report.aggregates
            ],
        }