from dataclasses import dataclass

from .experiment import ExperimentReport

@dataclass(frozen=True)
class StrategyComparison:
    strategy: str
    task_success: float
    recovery_success: float
    preservation_ratio: float
    affected_node_count: float
    invalidated_node_count: float
    recomputed_node_count: float
    unnecessary_recomputation: float

@dataclass(frozen=True)
class StrategyMetricPoint:
    strategy: str
    metric: str
    value: float


class ExperimentVisualizationData:
    """
    Converts measured experiment results into visualization-ready data.

    No benchmark values are hard-coded here.
    """

    @staticmethod
    def metric_points(
        report: ExperimentReport,
        metric: str,
    ) -> tuple[StrategyMetricPoint, ...]:
        points = []

        for aggregate in report.aggregates:
            value = next(
                (
                    item.mean
                    for item in aggregate.metrics
                    if item.metric == metric
                ),
                None,
            )

            if value is None:
                raise ValueError(
                    f"Metric {metric!r} is not available "
                    f"for strategy {aggregate.strategy!r}."
                )

            points.append(
                StrategyMetricPoint(
                    strategy=aggregate.strategy,
                    metric=metric,
                    value=value,
                )
            )

        return tuple(points)

    @staticmethod
    def to_chart_data(
        report: ExperimentReport,
        metric: str,
    ) -> list[dict[str, str | float]]:
        points = ExperimentVisualizationData.metric_points(
            report,
            metric,
        )

        return [
            {
                "strategy": point.strategy,
                "value": point.value,
            }
            for point in points
        ]

    @staticmethod
    def strategy_comparison(
        report: ExperimentReport,
        metrics: tuple[str, ...],
    ) -> dict[str, dict[str, float]]:
        comparison: dict[str, dict[str, float]] = {}

        for aggregate in report.aggregates:
            strategy_metrics: dict[str, float] = {}

            for metric_name in metrics:
                value = next(
                    (
                        metric.mean
                        for metric in aggregate.metrics
                        if metric.metric == metric_name
                    ),
                    None,
                )

                if value is None:
                    raise ValueError(
                        f"Metric {metric_name!r} is not available "
                        f"for strategy {aggregate.strategy!r}."
                    )

                strategy_metrics[metric_name] = value

            comparison[aggregate.strategy] = strategy_metrics

        return comparison

    @staticmethod
    def dashboard_data(
        report: ExperimentReport,
    ) -> tuple[StrategyComparison, ...]:
        metrics = (
            "task_success",
            "recovery_success",
            "preservation_ratio",
            "affected_node_count",
            "invalidated_node_count",
            "recomputed_node_count",
            "unnecessary_recomputation",
        )

        comparison = ExperimentVisualizationData.strategy_comparison(
            report,
            metrics,
        )

        return tuple(
            StrategyComparison(
                strategy=strategy,
                task_success=values["task_success"],
                recovery_success=values["recovery_success"],
                preservation_ratio=values["preservation_ratio"],
                affected_node_count=values["affected_node_count"],
                invalidated_node_count=values["invalidated_node_count"],
                recomputed_node_count=values["recomputed_node_count"],
                unnecessary_recomputation=values[
                    "unnecessary_recomputation"
                ],
            )
            for strategy, values in comparison.items()
        )