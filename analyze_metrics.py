import json
from pathlib import Path

path = Path("experiments/results/recovery_comparison.json")
data = json.loads(path.read_text(encoding="utf-8"))

print(f"{'STRATEGY':<15} {'RUNS':>5} {'PRECISION':>10} {'RECALL':>10} {'F1':>10} {'EXACT MATCH':>12}")
print("-" * 67)

strategies = sorted({r["strategy"] for r in data["results"]})

for strategy in strategies:
    runs = [
        r for r in data["results"]
        if r["strategy"] == strategy
        and r["metrics"].get("impact_classification_available") is True
    ]

    if not runs:
        print(f"{strategy:<15} {'N/A':>5}")
        continue

    tp = sum(r["metrics"].get("impact_true_positives") or 0 for r in runs)
    fp = sum(r["metrics"].get("impact_false_positives") or 0 for r in runs)
    fn = sum(r["metrics"].get("impact_false_negatives") or 0 for r in runs)

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0
    )

    exact = sum(
        r["metrics"].get("impact_ground_truth_match") is True
        for r in runs
    )

    print(
        f"{strategy:<15} {len(runs):>5} "
        f"{precision:>10.3f} {recall:>10.3f} "
        f"{f1:>10.3f} {exact:>5}/{len(runs):<7}"
    )