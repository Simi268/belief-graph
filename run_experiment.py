from app.benchmark_instances import generate_scenario2_instance
from app.experiment import ExperimentRunner
from app.experiment_export import ExperimentExporter
from app.experiment_markdown import ExperimentMarkdownReport
from app.seeded_strategy_adapters import seeded_strategy_evaluators


def main():
    # ---------------------------------------------------------
    # Run deterministic multi-seed experiment
    # ---------------------------------------------------------

    runner = ExperimentRunner(
        seeded_strategy_evaluators()
    )

    report = runner.run(
        seeds=[1, 2, 3, 4, 5],
        generator=generate_scenario2_instance,
    )

    # ---------------------------------------------------------
    # Export machine-readable JSON
    # ---------------------------------------------------------

    json_path = ExperimentExporter.report_to_json(
        report,
        "experiments/results/scenario2_5seed.json",
    )

    print(
        f"Experiment JSON exported to: {json_path}"
    )

    # ---------------------------------------------------------
    # Generate human-readable Markdown report
    # ---------------------------------------------------------

    markdown_path = ExperimentMarkdownReport.from_json(
        json_path,
        "experiments/reports/scenario2_5seed_report.md",
    )

    print(
        f"Experiment Markdown report generated: "
        f"{markdown_path}"
    )


if __name__ == "__main__":
    main()