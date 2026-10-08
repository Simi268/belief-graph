import importlib
from pathlib import Path

from app.experiment import ExperimentRunner
from app.experiment_export import ExperimentExporter
from app.experiment_markdown import ExperimentMarkdownReport
from app.seeded_strategy_adapters import seeded_strategy_evaluators


SEEDS = [1, 2, 3, 4, 5]

RESULTS_DIR = Path("experiments/results")
REPORTS_DIR = Path("experiments/reports")


def discover_scenario_generators():
    """
    Discover all available generate_scenarioN_instance functions from
    app.benchmark_instances.

    This avoids hardcoding Scenario 2 and lets the experiment runner
    automatically pick up newly added benchmark-instance generators.
    """
    module = importlib.import_module("app.benchmark_instances")

    generators = []

    for name in dir(module):
        if not (
            name.startswith("generate_scenario")
            and name.endswith("_instance")
        ):
            continue

        generator = getattr(module, name)

        if not callable(generator):
            continue

        scenario_name = name[len("generate_") : -len("_instance")]
        generators.append((scenario_name, generator))

    generators.sort(key=lambda item: item[0])

    return generators


def run_scenario(scenario_name, generator):
    """Run one deterministic multi-seed experiment and export its reports."""

    print()
    print("=" * 70)
    print(f"{scenario_name.upper()} — MULTI-SEED EXPERIMENT")
    print("=" * 70)

    runner = ExperimentRunner(
        seeded_strategy_evaluators()
    )

    report = runner.run(
        seeds=SEEDS,
        generator=generator,
    )

    json_path = RESULTS_DIR / f"{scenario_name}_5seed.json"
    markdown_path = REPORTS_DIR / f"{scenario_name}_5seed_report.md"

    json_path = ExperimentExporter.report_to_json(
        report,
        str(json_path),
    )

    print(
        f"Experiment JSON exported to: {json_path}"
    )

    markdown_path = ExperimentMarkdownReport.from_json(
        json_path,
        str(markdown_path),
    )

    print(
        f"Experiment Markdown report generated: "
        f"{markdown_path}"
    )

    return report


def main():
    # ---------------------------------------------------------
    # Prepare experiment output directories
    # ---------------------------------------------------------

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # Discover all available benchmark-instance generators
    # ---------------------------------------------------------

    generators = discover_scenario_generators()

    if not generators:
        raise RuntimeError(
            "No generate_scenarioN_instance functions were found in "
            "app.benchmark_instances."
        )

    print("Discovered benchmark generators:")
    for scenario_name, _ in generators:
        print(f"  - {scenario_name}")

    # ---------------------------------------------------------
    # Run every discovered scenario
    # ---------------------------------------------------------

    successful = []
    failed = []

    for scenario_name, generator in generators:
        try:
            run_scenario(
                scenario_name,
                generator,
            )
            successful.append(scenario_name)

        except Exception as exc:
            failed.append((scenario_name, exc))

            print()
            print(f"ERROR while running {scenario_name}:")
            print(f"  {type(exc).__name__}: {exc}")

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------

    print()
    print("=" * 70)
    print("EXPERIMENT SUMMARY")
    print("=" * 70)

    print(f"Successful: {len(successful)}")

    for scenario_name in successful:
        print(f"  [OK] {scenario_name}")

    print(f"Failed: {len(failed)}")

    for scenario_name, exc in failed:
        print(
            f"  [FAILED] {scenario_name}: "
            f"{type(exc).__name__}: {exc}"
        )

    # Fail the command only after all scenarios have been attempted.
    if failed:
        raise RuntimeError(
            f"{len(failed)} experiment scenario(s) failed."
        )


if __name__ == "__main__":
    main()
