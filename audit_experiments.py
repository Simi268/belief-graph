import json
from pathlib import Path
from statistics import mean

RESULTS_DIR = Path("experiments/results")

STRATEGIES = ("baseline", "memory", "belief_graph")

METRICS = (
    "task_success",
    "recovery_success",
    "stale_actions",
    "stale_plans",
    "unnecessary_invalidation",
    "recomputed_node_count",
    "unnecessary_recomputation",
    "preserved_node_count",
    "preservation_ratio",
)


def load_results(path: Path) -> list[dict]:
    """Load JSON and support common experiment result formats."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("results", "runs", "seed_results"):
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError(
        f"Unrecognized result structure in {path}. "
        "Inspect the JSON schema before auditing it."
    )


def get_strategy(record: dict) -> str | None:
    """Read the strategy label from common result formats."""
    if isinstance(record.get("strategy"), str):
        return record["strategy"]

    metrics = record.get("metrics")
    if isinstance(metrics, dict):
        return metrics.get("strategy")

    return None


def get_metrics(record: dict) -> dict:
    """Support flat records and nested metrics."""
    metrics = record.get("metrics")

    if isinstance(metrics, dict):
        return metrics

    return record


def audit_file(path: Path) -> None:
    records = load_results(path)

    print(f"\n{'=' * 75}")
    print(f"FILE: {path}")
    print(f"Records loaded: {len(records)}")
    print("=" * 75)

    grouped = {strategy: [] for strategy in STRATEGIES}

    for record in records:
        strategy = get_strategy(record)

        if strategy in grouped:
            grouped[strategy].append(get_metrics(record))

    for strategy, runs in grouped.items():
        print(f"\n[{strategy.upper()}]")

        if not runs:
            print("WARNING: No records found for this strategy.")
            continue

        for metric in METRICS:
            values = [
                run[metric]
                for run in runs
                if isinstance(run.get(metric), (int, float))
                and not isinstance(run.get(metric), bool)
            ]

            if values:
                print(
                    f"{metric:30} "
                    f"mean={mean(values):.4f} "
                    f"runs={len(values)}"
                )

        for run in runs:
            details = run.get("details", {})

            if details.get("direct_graph_execution") is True:
                print(
                    "NOTE: At least one record reports direct graph "
                    "execution; this is not necessarily a full agent run."
                )

    if any(not grouped[strategy] for strategy in STRATEGIES):
        print(
            "\nAUDIT WARNING: The three strategies were not all "
            "found under the expected labels. Inspect the file schema."
        )


def main() -> None:
    files = sorted(RESULTS_DIR.glob("scenario*_5seed.json"))

    if not files:
        raise SystemExit(
            f"No experiment JSON files found in {RESULTS_DIR.resolve()}"
        )

    print(f"Auditing {len(files)} experiment files.")

    for path in files:
        try:
            audit_file(path)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            print(f"\nAUDIT ERROR in {path}: {exc}")

    print("\nAudit complete.")
    print("These summaries do not establish causal superiority.")


if __name__ == "__main__":
    main()