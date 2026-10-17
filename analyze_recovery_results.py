import json
import statistics
from collections import defaultdict
from pathlib import Path


RESULTS_PATH = Path("experiments/results/recovery_comparison.json")
OUTPUT_PATH = Path("experiments/results/recovery_analysis.json")


def mean(values):
    return statistics.mean(values) if values else 0.0


def get_metrics(row):
    return row.get("metrics", {})


def summarize_runtime(rows):
    values = [
        r["elapsed_seconds"]
        for r in rows
        if r.get("elapsed_seconds") is not None
    ]

    if not values:
        return {
            "evaluations": len(rows),
            "mean_runtime_ms": None,
            "median_runtime_ms": None,
        }

    return {
        "evaluations": len(rows),
        "mean_runtime_ms": round(mean(values) * 1000, 4),
        "median_runtime_ms": round(
            statistics.median(values) * 1000, 4
        ),
    }


def summarize_classification(rows):
    """
    Summarize impact classification separately from recovery outcome.
    Classification metrics are included only when supplied by the
    benchmark and must not be inferred from recovery-success flags.
    """
    result = {}

    metric_names = [
        "impact_ground_truth_match",
        "category_exact_matches",
        "impact_true_positives",
        "impact_false_positives",
        "impact_false_negatives",
    ]

    for name in metric_names:
        values = [
            r.get(name, get_metrics(r).get(name))
            for r in rows
        ]
        values = [v for v in values if v is not None]

        if not values:
            continue

        if name == "category_exact_matches":
            categories = set()
            for value in values:
                if isinstance(value, dict):
                    categories.update(value.keys())

            result[name] = {
                category: {
                    "correct": sum(
                        1
                        for value in values
                        if isinstance(value, dict)
                        and value.get(category) is True
                    ),
                    "evaluated": sum(
                        1
                        for value in values
                        if isinstance(value, dict)
                        and value.get(category) is not None
                    ),
                }
                for category in sorted(categories)
            }

        elif all(isinstance(v, bool) for v in values):
            result[f"{name}_rate"] = round(
                sum(values) / len(values), 4
            )

        elif all(isinstance(v, (int, float)) for v in values):
            result[f"{name}_mean"] = round(mean(values), 4)

    tp = result.get("impact_true_positives_mean")
    fp = result.get("impact_false_positives_mean")
    fn = result.get("impact_false_negatives_mean")

    if tp is not None and fp is not None and fn is not None:
        precision_denominator = tp + fp
        recall_denominator = tp + fn

        precision = (
            tp / precision_denominator
            if precision_denominator
            else 0.0
        )
        recall = (
            tp / recall_denominator
            if recall_denominator
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        result["precision"] = round(precision, 4)
        result["recall"] = round(recall, 4)
        result["f1"] = round(f1, 4)

    return result


def summarize_recovery_outcome(rows):
    """
    Do not treat strategy-provided success flags as independently
    verified recovery outcomes.
    """
    return {
        "task_success_rate": None,
        "recovery_success_rate": None,
        "status": "not_independently_verified",
        "reason": (
            "A shared evaluator must verify the resulting state against "
            "the same acceptance conditions for every strategy."
        ),
    }


def summarize_recovery_cost(rows):
    metric_names = [
        "stale_actions",
        "stale_plans",
        "invalid_plans",
        "affected_node_count",
        "invalidated_node_count",
        "recomputed_node_count",
        "unnecessary_recomputation",
        "preservation_ratio",
        "recovery_steps",
        "tool_calls",
        "propagation_depth",
    ]

    summary = {}

    for name in metric_names:
        values = [
            get_metrics(row)[name]
            for row in rows
            if name in get_metrics(row)
            and get_metrics(row)[name] is not None
        ]

        if values:
            summary[f"{name}_mean"] = round(mean(values), 4)

    return summary


def summarize(rows):
    return {
        **summarize_runtime(rows),
        "impact_classification": summarize_classification(rows),
        "recovery_outcome": summarize_recovery_outcome(rows),
        "recovery_cost": summarize_recovery_cost(rows),
    }


def main():
    if not RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Results file not found: {RESULTS_PATH}"
        )

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    results = data.get("results", [])

    if not results:
        raise ValueError("The results file contains no evaluations.")

    by_strategy = defaultdict(list)
    by_scenario_strategy = defaultdict(list)

    for row in results:
        strategy = row["strategy"]
        scenario = row["scenario"]

        by_strategy[strategy].append(row)
        by_scenario_strategy[(scenario, strategy)].append(row)

    report = {
        "experiment": data.get("experiment"),
        "total_evaluations": len(results),
        "overall_by_strategy": {},
        "by_scenario": {},
        "interpretation_warning": (
            "Impact classification and recovery cost are reported "
            "separately. Task success and recovery success are deliberately "
            "marked not independently verified because strategy-provided "
            "success flags do not use a common independent evaluator. "
            "Runtime measures adapter execution, not necessarily "
            "end-to-end agent runtime. Stale-action metrics must not be "
            "interpreted as residual stale state unless the benchmark "
            "explicitly measures stale actions remaining after recovery."
        ),
    }

    for strategy, rows in sorted(by_strategy.items()):
        report["overall_by_strategy"][strategy] = summarize(rows)

    for scenario in sorted({row["scenario"] for row in results}):
        report["by_scenario"][scenario] = {}

        for strategy in sorted(by_strategy):
            rows = by_scenario_strategy.get((scenario, strategy), [])
            if rows:
                report["by_scenario"][scenario][strategy] = summarize(rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("RECOVERY ANALYSIS")
    print("=" * 60)
    print("Evaluations:", len(results))

    for strategy, summary in report["overall_by_strategy"].items():
        print(f"\nSTRATEGY: {strategy}")
        print("-" * 40)
        print("Runtime:", summary["mean_runtime_ms"], "ms mean")
        print("Classification:", summary["impact_classification"])
        print("Recovery outcome:", summary["recovery_outcome"])
        print("Recovery cost:", summary["recovery_cost"])

    print("\nReport saved to:", OUTPUT_PATH)


if __name__ == "__main__":
    main()