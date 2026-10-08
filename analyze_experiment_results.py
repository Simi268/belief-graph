from __future__ import annotations

import json
from pathlib import Path
from statistics import mean


RESULTS_DIR = Path("experiments/results")
KEY_METRICS = (
    "task_success",
    "stale_actions",
    "invalid_plans",
    "affected_node_count",
    "invalidated_node_count",
    "recomputed_node_count",
    "unnecessary_recomputation",
    "preserved_node_count",
    "preservation_ratio",
    "propagation_depth",
    "evidence_selection_correct",
    "revision_count",
)


def load_reports() -> list[tuple[str, dict]]:
    reports = sorted(
        RESULTS_DIR.glob("scenario*_5seed.json"),
        key=lambda p: p.name,
    )

    if not reports:
        raise FileNotFoundError(
            "No scenario*_5seed.json files found in experiments/results."
        )

    loaded = []
    for path in reports:
        with path.open("r", encoding="utf-8") as f:
            loaded.append((path.stem, json.load(f)))

    return loaded


def validate_report(name: str, report: dict) -> None:
    seeds = report.get("seeds", [])
    results = report.get("results", [])
    aggregates = report.get("aggregates", [])

    if len(seeds) != 5:
        raise ValueError(
            f"{name}: expected 5 seeds, found {len(seeds)}."
        )

    expected_results = 5 * 3
    if len(results) != expected_results:
        raise ValueError(
            f"{name}: expected {expected_results} results, "
            f"found {len(results)}."
        )

    strategies = {
        result["strategy"]
        for result in results
    }

    expected_strategies = {
        "baseline",
        "memory",
        "belief_graph",
    }

    if strategies != expected_strategies:
        raise ValueError(
            f"{name}: unexpected strategies {sorted(strategies)}."
        )

    for strategy in sorted(expected_strategies):
        strategy_results = [
            result
            for result in results
            if result["strategy"] == strategy
        ]

        result_seeds = {
            result["seed"]
            for result in strategy_results
        }

        if result_seeds != set(seeds):
            raise ValueError(
                f"{name}: {strategy} does not cover the exact seed set."
            )

    if len(aggregates) != 3:
        raise ValueError(
            f"{name}: expected 3 strategy aggregates, "
            f"found {len(aggregates)}."
        )


def aggregate_lookup(report: dict) -> dict[str, dict[str, dict]]:
    lookup = {}

    for aggregate in report["aggregates"]:
        strategy = aggregate["strategy"]
        lookup[strategy] = {
            metric["metric"]: metric
            for metric in aggregate["metrics"]
        }

    return lookup


def fmt(value):
    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, float):
        return f"{value:.3f}"

    return str(value)


def main() -> None:
    reports = load_reports()

    all_keys = []

    for name, report in reports:
        validate_report(name, report)
        lookup = aggregate_lookup(report)
        all_keys.append((name, lookup))

    print("=" * 100)
    print("BELIEF-GRAPH — CROSS-SCENARIO EXPERIMENT SUMMARY")
    print("=" * 100)
    print()
    print(
        "Coverage: "
        f"{len(all_keys)} scenarios × 5 seeds × 3 strategies "
        f"= {len(all_keys) * 15} strategy runs"
    )
    print()

    for scenario_name, lookup in all_keys:
        print("-" * 100)
        print(scenario_name)
        print("-" * 100)

        for strategy in ("baseline", "memory", "belief_graph"):
            metrics = lookup[strategy]

            values = []
            for metric in KEY_METRICS:
                if metric in metrics:
                    values.append(
                        f"{metric}={fmt(metrics[metric]['mean'])}"
                    )

            print(f"{strategy:12} " + " | ".join(values))

        print()

    # ---------------------------------------------------------
    # Selectivity comparison across scenarios
    # ---------------------------------------------------------

    print("=" * 100)
    print("SELECTIVITY-RELEVANT METRICS")
    print("=" * 100)
    print()

    header = (
        f"{'Scenario':18}"
        f"{'Strategy':14}"
        f"{'Affected':10}"
        f"{'Recomputed':12}"
        f"{'Unnecessary':13}"
        f"{'Preserved':11}"
        f"{'Pres. Ratio':12}"
        f"{'Task OK':9}"
    )
    print(header)
    print("-" * len(header))

    for scenario_name, lookup in all_keys:
        display_name = scenario_name.replace(
            "_5seed", ""
        )

        for strategy in (
            "baseline",
            "memory",
            "belief_graph",
        ):
            metrics = lookup[strategy]

            def metric(name, default="-"):
                item = metrics.get(name)
                return (
                    fmt(item["mean"])
                    if item is not None
                    else default
                )

            print(
                f"{display_name:18}"
                f"{strategy:14}"
                f"{metric('affected_node_count'):10}"
                f"{metric('recomputed_node_count'):12}"
                f"{metric('unnecessary_recomputation'):13}"
                f"{metric('preserved_node_count'):11}"
                f"{metric('preservation_ratio'):12}"
                f"{metric('task_success'):9}"
            )

    # ---------------------------------------------------------
    # Check whether the multi-seed variation actually changes
    # measured quantities.
    # ---------------------------------------------------------

    print()
    print("=" * 100)
    print("MULTI-SEED VARIATION CHECK")
    print("=" * 100)
    print()

    for scenario_name, report in reports:
        by_strategy = {}
        for result in report["results"]:
            by_strategy.setdefault(
                result["strategy"], {}
            ).setdefault(
                result["seed"], result["metrics"]
            )

        print(f"{scenario_name}:")

        for strategy in (
            "baseline",
            "memory",
            "belief_graph",
        ):
            seed_metrics = by_strategy[strategy]

            changing_metrics = []

            for metric in KEY_METRICS:
                values = [
                    metrics[metric]
                    for metrics in seed_metrics.values()
                    if metric in metrics
                ]

                if len(values) >= 2 and len(set(values)) > 1:
                    changing_metrics.append(metric)

            if changing_metrics:
                print(
                    f"  {strategy}: variation in "
                    + ", ".join(changing_metrics)
                )
            else:
                print(
                    f"  {strategy}: no measured metric variation"
                )

    print()
    print(
        "Note: this script reports the generated experimental results only. "
        "It does not infer causal conclusions or statistical significance."
    )


if __name__ == "__main__":
    main()
