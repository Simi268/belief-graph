from dataclasses import dataclass

from .experiment import ExperimentReport
from .multiseed_benchmark import StrategyAggregate


@dataclass(frozen=True)
class MetricSpec:
    name: str
    label: str
    format_type: str


@dataclass(frozen=True)
class MetricComparison:
    metric: str
    label: str
    format_type: str
    values: dict[str, float]


@dataclass(frozen=True)
class ExperimentSummary:
    seeds: tuple[int, ...]
    strategies: tuple[str, ...]
    comparisons: tuple[MetricComparison, ...]


METRIC_SPECS = {
    "task_success": MetricSpec(
        "task_success",
        "Task success",
        "percentage",
    ),
    "recovery_success": MetricSpec(
        "recovery_success",
        "Recovery success",
        "percentage",
    ),
    "preservation_ratio": MetricSpec(
        "preservation_ratio",
        "Preservation ratio",
        "percentage",
    ),
    "affected_node_count": MetricSpec(
        "affected_node_count",
        "Affected nodes",
        "integer",
    ),
    "invalidated_node_count": MetricSpec(
        "invalidated_node_count",
        "Invalidated nodes",
        "integer",
    ),
    "preserved_node_count": MetricSpec(
        "preserved_node_count",
        "Preserved nodes",
        "integer",
    ),
    "recomputed_node_count": MetricSpec(
        "recomputed_node_count",
        "Recomputed nodes",
        "integer",
    ),
    "unnecessary_recomputation": MetricSpec(
        "unnecessary_recomputation",
        "Unnecessary recomputation",
        "integer",
    ),
    "invalid_plans": MetricSpec(
        "invalid_plans",
        "Invalid plans",
        "integer",
    ),
    "stale_actions": MetricSpec(
        "stale_actions",
        "Stale actions",
        "integer",
    ),
    "stale_plans": MetricSpec(
        "stale_plans",
        "Stale plans",
        "integer",
    ),
    "propagation_depth": MetricSpec(
        "propagation_depth",
        "Propagation depth",
        "integer",
    ),
    "recovery_steps": MetricSpec(
        "recovery_steps",
        "Recovery steps",
        "integer",
    ),
    "tool_calls": MetricSpec(
        "tool_calls",
        "Tool calls",
        "integer",
    ),
    "unnecessary_invalidation": MetricSpec(
        "unnecessary_invalidation",
        "Unnecessary invalidation",
        "integer",
    ),
}


class ExperimentReportBuilder:
    """
    Converts raw experiment aggregates into a presentation-ready summary.

    This layer only formats measured benchmark results.
    It does not alter benchmark semantics or choose a winner.
    """

    @staticmethod
    def build(report: ExperimentReport) -> ExperimentSummary:
        strategies = tuple(
            aggregate.strategy
            for aggregate in report.aggregates
        )

        metric_names = sorted(
            {
                metric.metric
                for aggregate in report.aggregates
                for metric in aggregate.metrics
            }
        )

        comparisons = []

        for metric_name in metric_names:
            spec = METRIC_SPECS.get(
                metric_name,
                MetricSpec(
                    metric_name,
                    metric_name.replace("_", " ").title(),
                    "decimal",
                ),
            )

            values = {}

            for aggregate in report.aggregates:
                for metric in aggregate.metrics:
                    if metric.metric == metric_name:
                        values[aggregate.strategy] = metric.mean
                        break

            comparisons.append(
                MetricComparison(
                    metric=metric_name,
                    label=spec.label,
                    format_type=spec.format_type,
                    values=values,
                )
            )

        return ExperimentSummary(
            seeds=report.seeds,
            strategies=strategies,
            comparisons=tuple(comparisons),
        )

    @staticmethod
    def _format_value(
        value: float,
        format_type: str,
    ) -> str:
        if format_type == "percentage":
            return f"{value * 100:.1f}%"

        if format_type == "integer":
            return f"{value:.0f}"

        return f"{value:.4f}"

    @staticmethod
    def to_text(summary: ExperimentSummary) -> str:
        lines = [
            "BELIEF-GRAPH EXPERIMENT",
            "=" * 24,
            f"Seeds: {', '.join(map(str, summary.seeds))}",
            "",
            "Strategy comparison",
            "-" * 24,
        ]

        for comparison in summary.comparisons:
            lines.append(f"{comparison.label}:")

            for strategy in summary.strategies:
                value = comparison.values.get(strategy)

                if value is None:
                    continue

                formatted = ExperimentReportBuilder._format_value(
                    value,
                    comparison.format_type,
                )

                lines.append(
                    f"  {strategy}: {formatted}"
                )

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def to_table(summary: ExperimentSummary) -> str:
        if not summary.comparisons:
            return "No experiment metrics available."

        headers = ["Metric", *summary.strategies]

        rows = []

        for comparison in summary.comparisons:
            row = [comparison.label]

            for strategy in summary.strategies:
                value = comparison.values.get(strategy)

                if value is None:
                    row.append("-")
                else:
                    row.append(
                        ExperimentReportBuilder._format_value(
                            value,
                            comparison.format_type,
                        )
                    )

            rows.append(row)

        widths = [
            max(
                len(headers[index]),
                *(len(row[index]) for row in rows),
            )
            for index in range(len(headers))
        ]

        def format_row(row):
            return " | ".join(
                value.ljust(widths[index])
                for index, value in enumerate(row)
            )

        separator = "-+-".join(
            "-" * width
            for width in widths
        )

        output = [
            format_row(headers),
            separator,
        ]

        output.extend(
            format_row(row)
            for row in rows
        )

        return "\n".join(output)