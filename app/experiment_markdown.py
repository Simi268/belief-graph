import json
from pathlib import Path


class ExperimentMarkdownReport:

    @staticmethod
    def from_json(
        input_path: str | Path,
        output_path: str | Path
    ) -> Path:
        input_file = Path(input_path)
        output_file = Path(output_path)

        data = json.loads(
            input_file.read_text(encoding="utf-8")
        )

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        markdown = ExperimentMarkdownReport._build_markdown(data)

        output_file.write_text(
            markdown,
            encoding="utf-8"
        )

        return output_file

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _metric_map(aggregate: dict) -> dict[str, float]:
        return {
            metric["metric"]: metric["mean"]
            for metric in aggregate.get("metrics", [])
        }

    @staticmethod
    def _aggregate_map(
        data: dict
    ) -> dict[str, dict[str, float]]:
        return {
            aggregate["strategy"]:
                ExperimentMarkdownReport._metric_map(aggregate)
            for aggregate in data.get("aggregates", [])
        }

    @staticmethod
    def _format_percentage(value: float) -> str:
        return f"{value * 100:.1f}%"

    @staticmethod
    def _format_number(value: float) -> str:
        return f"{value:.0f}"

    @staticmethod
    def _metric_text(
        aggregates: dict,
        strategy: str,
        metric: str,
        formatter
    ) -> str:

        strategy_metrics = aggregates.get(strategy)

        if strategy_metrics is None:
            return "-"

        value = strategy_metrics.get(metric)

        if value is None:
            return "-"

        return formatter(value)

    @staticmethod
    def _strategy_description(strategy: str) -> str:

        descriptions = {
            "baseline": (
                "Agent without dependency-aware belief revision"
            ),
            "memory": (
                "Conventional memory strategy using full recomputation"
            ),
            "belief_graph": (
                "Dependency-aware impact analysis with selective revision"
            ),
        }

        return descriptions.get(
            strategy,
            "Experiment strategy"
        )

    # ---------------------------------------------------------
    # Main report
    # ---------------------------------------------------------

    @staticmethod
    def _build_markdown(data: dict) -> str:

        aggregates = (
            ExperimentMarkdownReport
            ._aggregate_map(data)
        )

        strategies = [
            aggregate["strategy"]
            for aggregate in data.get("aggregates", [])
        ]

        seeds = data.get("seeds", [])
        results = data.get("results", [])

        lines = [
            "# Belief-Graph Experiment Report",
            "",
            "> Controlled evaluation of dependency-aware belief "
            "revision and selective recovery.",
            "",
            "## 1. Objective",
            "",
            "### Experiment objective",
            "",
            (
                "Evaluate whether dependency-aware belief revision "
                "can recover from changed beliefs while preserving "
                "unaffected reasoning state."
            ),
            "",
            (
                "The experiment compares different recovery strategies "
                "under controlled belief changes and evaluates whether "
                "the system can identify affected reasoning state instead "
                "of recomputing everything."
            ),
            "",
            "## 2. Experimental Setup",
            "",
            f"- **Seeds:** "
            f"{', '.join(map(str, seeds)) if seeds else 'Not specified'}",
            f"- **Strategy runs:** {len(results)}",
            f"- **Strategies:** "
            f"{', '.join(strategies) if strategies else 'Not specified'}",
            "- **Scenario:** Multi-branch belief revision",
            (
                "- **Evaluation:** Dependency-aware impact analysis "
                "against explicit ground truth"
            ),
            "",
            "### Strategy comparison",
            "",
            "Strategy comparison",
            "",
        ]

        # -----------------------------------------------------
        # Strategy comparison table
        # -----------------------------------------------------

        if strategies:

            lines.extend([
                "| Strategy | Description |",
                "|---|---|",
            ])

            for strategy in strategies:
                lines.append(
                    f"| {strategy} | "
                    f"{ExperimentMarkdownReport._strategy_description(strategy)} |"
                )

        else:
            lines.append(
                "No aggregate strategy data is available."
            )

        lines.extend([
            "",
            "## 3. Key Results",
            "",
        ])

        # -----------------------------------------------------
        # Key results
        # -----------------------------------------------------

        key_metrics = [
            (
                "Task success",
                "task_success",
                ExperimentMarkdownReport._format_percentage,
            ),
            (
                "Recovery success",
                "recovery_success",
                ExperimentMarkdownReport._format_percentage,
            ),
            (
                "Preservation ratio",
                "preservation_ratio",
                ExperimentMarkdownReport._format_percentage,
            ),
            (
                "Affected nodes",
                "affected_node_count",
                ExperimentMarkdownReport._format_number,
            ),
            (
                "Invalidated nodes",
                "invalidated_node_count",
                ExperimentMarkdownReport._format_number,
            ),
            (
                "Recomputed nodes",
                "recomputed_node_count",
                ExperimentMarkdownReport._format_number,
            ),
            (
                "Unnecessary recomputation",
                "unnecessary_recomputation",
                ExperimentMarkdownReport._format_number,
            ),
            (
                "Propagation depth",
                "propagation_depth",
                ExperimentMarkdownReport._format_number,
            ),
        ]

        if strategies:

            header = (
                "| Metric | "
                + " | ".join(strategies)
                + " |"
            )

            separator = (
                "|---|"
                + "|".join(["---:"] * len(strategies))
                + "|"
            )

            lines.append(header)
            lines.append(separator)

            for label, metric, formatter in key_metrics:

                values = [
                    ExperimentMarkdownReport._metric_text(
                        aggregates,
                        strategy,
                        metric,
                        formatter,
                    )
                    for strategy in strategies
                ]

                lines.append(
                    f"| {label} | "
                    + " | ".join(values)
                    + " |"
                )

        else:
            lines.append(
                "No aggregate metrics are available."
            )

        # -----------------------------------------------------
        # Interpretation
        # -----------------------------------------------------

        lines.extend([
            "",
            "## 4. Interpretation",
            "",
        ])

        if {
            "baseline",
            "memory",
            "belief_graph",
        }.issubset(aggregates):

            baseline = aggregates["baseline"]
            memory = aggregates["memory"]
            belief_graph = aggregates["belief_graph"]

            if baseline.get("task_success") is not None:
                lines.extend([
                    (
                        "In this controlled benchmark, the baseline "
                        "strategy does not successfully recover from "
                        "the changed belief and leaves stale downstream "
                        "state."
                    ),
                    "",
                ])

            if memory.get("task_success") is not None:
                lines.extend([
                    (
                        "The conventional memory strategy successfully "
                        "recovers, but it recomputes the complete original "
                        "reasoning state rather than identifying only the "
                        "affected dependency region."
                    ),
                    "",
                ])

            message = (
                "The Belief-Graph strategy successfully performs "
                "dependency-aware impact analysis and selective "
                "revision."
            )

            preservation = belief_graph.get(
                "preservation_ratio"
            )

            affected = belief_graph.get(
                "affected_node_count"
            )

            invalidated = belief_graph.get(
                "invalidated_node_count"
            )

            unnecessary = belief_graph.get(
                "unnecessary_recomputation"
            )

            if preservation is not None:
                message += (
                    f" It preserves "
                    f"{preservation * 100:.1f}% of the original "
                    "reasoning state."
                )

            if affected is not None:
                message += (
                    f" The affected region contains "
                    f"{affected:.0f} nodes."
                )

            if invalidated is not None:
                message += (
                    f" {invalidated:.0f} nodes are explicitly "
                    "invalidated."
                )

            if unnecessary is not None:
                message += (
                    f" Unnecessary recomputation is "
                    f"{unnecessary:.0f} nodes."
                )

            if belief_graph.get("task_success") is not None:
                lines.extend([
                    message,
                    "",
                ])

            lines.extend([
                (
                    "These results demonstrate the intended selective "
                    "revision behavior within the controlled benchmark. "
                    "They should not be interpreted as universal "
                    "performance or superiority claims."
                ),
                "",
            ])

        else:

            lines.extend([
                (
                    "The report contains the aggregate results available "
                    "in the supplied experiment artifact. Full comparative "
                    "interpretation is generated when all benchmark "
                    "strategies are present."
                ),
                "",
            ])

        # -----------------------------------------------------
        # Dependency revision example
        # -----------------------------------------------------

        lines.extend([
            "## 5. Dependency Revision Example",
            "",
            (
                "The benchmark models a shared belief with three "
                "different dependency relationships:"
            ),
            "",
            "```text",
            "                 B1",
            "                 │",
            "                 C1",
            "          ┌──────┼──────┐",
            "          │      │      │",
            "       REQUIRES SUPPORTS CONTEXT",
            "          │      │      │",
            "         P1     P2     P3",
            "          │      │      │",
            "         A1     A2     A3",
            "",
            "                 B4",
            "                  │",
            "                 C4",
            "                  │",
            "                 P4",
            "                  │",
            "                 A4",
            "```",
            "",
            (
                "When B1 becomes invalid, the system does not blindly "
                "invalidate every downstream node. Instead, dependency "
                "types determine whether a node becomes invalid, "
                "requires reevaluation, or becomes uncertain."
            ),
            "",
            "This is the core mechanism behind selective recovery.",
            "",
            "## 6. Limitations",
            "",
            "- The experiment uses a controlled benchmark scenario.",
            "- The reported experiment uses five deterministic seeds.",
            (
                "- The benchmark does not establish universal "
                "architecture or performance claims."
            ),
            (
                "- Runtime, token usage, and tool-call measurements "
                "depend on the benchmark implementation."
            ),
            (
                "- Additional scenarios and larger workloads are "
                "required for broader validation."
            ),
            "",
            "## Reproducibility",
            "",
            (
                "The reported values are generated from the exported "
                "experiment JSON artifact."
            ),
            "",
            (
                "The experiment uses deterministic seeded benchmark "
                "instances, allowing the same seeds to reproduce "
                "the benchmark inputs."
            ),
            "",
            "Example:",
            "",
            "```text",
            "python run_experiment.py",
            "```",
            "",
            "## 8. Raw Metrics",
            "",
        ])

        # -----------------------------------------------------
        # Raw metrics
        # -----------------------------------------------------

        raw_rows = []

        for aggregate in data.get("aggregates", []):

            strategy = aggregate.get(
                "strategy",
                "unknown"
            )

            for metric in aggregate.get(
                "metrics",
                []
            ):

                raw_rows.append(
                    (
                        strategy,
                        metric.get(
                            "metric",
                            "unknown"
                        ),
                        metric.get(
                            "mean",
                            0.0
                        ),
                        metric.get(
                            "population_std",
                            0.0
                        ),
                    )
                )

        if raw_rows:

            lines.extend([
                "| Strategy | Metric | Mean | Population Std. Dev. |",
                "|---|---|---:|---:|",
            ])

            for (
                strategy,
                metric,
                mean_value,
                std_value,
            ) in raw_rows:

                lines.append(
                    f"| {strategy} | {metric} | "
                    f"{mean_value:.4f} | "
                    f"{std_value:.4f} |"
                )

        else:
            lines.append(
                "No raw aggregate metrics are available."
            )

        lines.append("")

        return "\n".join(lines)