import json
from pathlib import Path

path = Path("experiments/results/recovery_comparison.json")
data = json.loads(path.read_text(encoding="utf-8"))

runs = [
    result
    for result in data["results"]
    if result["strategy"] == "belief_graph"
    and result["metrics"].get("impact_ground_truth_match") is False
]

print(f"BeliefGraph mismatches: {len(runs)}")
print("=" * 60)

for run in runs:
    metrics = run["metrics"]
    details = run["details"]

    print(f"\nScenario: {run['scenario']}")
    print(f"Seed: {run['seed']}")
    print(f"Instance: {run['instance_id']}")
    print("True positives:", metrics.get("impact_true_positives"))
    print("False positives:", metrics.get("impact_false_positives"))
    print("False negatives:", metrics.get("impact_false_negatives"))

    for key in (
        "invalidated_nodes",
        "affected_nodes",
        "strategy_detected_affected_nodes",
        "preserved_nodes",
    ):
        if key in details:
            print(f"{key}: {details[key]}")