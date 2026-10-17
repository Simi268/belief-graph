"""
Belief-Graph Controlled Benchmark v2.

Evaluates three strategies across three dependency graph structures:

1. Linear dependencies
2. Multiple dependency branches
3. Shared dependencies

Strategies:
- NaiveBaseline
- FullRecomputationBaseline
- BeliefGraphStrategy

Measures:
- Impact precision, recall, and F1-score
- False positives and false negatives
- Missed downstream nodes
- Recomputed nodes
- Unnecessary recomputation
- Unaffected-node preservation
- Declared operation counts

IMPORTANT:
This benchmark evaluates graph impact classification and modeled
recomputation. It does not establish end-to-end agent performance,
production latency, or actual recovery cost.
"""

from __future__ import annotations

import csv
import json

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.baseline_strategies import (
    NaiveBaseline,
    FullRecomputationBaseline,
    BeliefGraphStrategy,
)

from app.graph import BeliefGraph
from app.models import BeliefNode, NodeType, DependencyType



# ============================================================
# 1. EXPERIMENT DEFINITIONS
# ============================================================

# Ground truth is specified independently of strategy outputs.
# Each scenario uses a fresh graph for every strategy.

SCENARIOS = {
    "linear": {
        "label": "Linear Dependency",
        "changed_node": "B1",
        "nodes": {
            "B1": ("BELIEF", "API version changed"),
            "C1": ("CONCLUSION", "API conclusion"),
            "P1": ("PLAN", "API plan"),
            "A1": ("ACTION", "API action"),
            "B2": ("BELIEF", "Independent service availability"),
        },
        "edges": [
            ("B1", "C1"),
            ("C1", "P1"),
            ("P1", "A1"),
        ],
        "expected_affected": {"B1", "C1", "P1", "A1"},
        "expected_preserved": {"B2"},
    },

    "multi_branch": {
        "label": "Multiple Dependency Branches",
        "changed_node": "B1",
        "nodes": {
            "B1": ("BELIEF", "Shared root belief"),
            "C1": ("CONCLUSION", "Branch one conclusion"),
            "P1": ("PLAN", "Branch one plan"),
            "A1": ("ACTION", "Branch one action"),
            "C2": ("CONCLUSION", "Branch two conclusion"),
            "P2": ("PLAN", "Branch two plan"),
            "A2": ("ACTION", "Branch two action"),
            "B2": ("BELIEF", "Independent root belief"),
            "C3": ("CONCLUSION", "Independent conclusion"),
        },
        "edges": [
            ("B1", "C1"),
            ("C1", "P1"),
            ("P1", "A1"),
            ("B1", "C2"),
            ("C2", "P2"),
            ("P2", "A2"),
            ("B2", "C3"),
        ],
        "expected_affected": {
            "B1", "C1", "P1", "A1", "C2", "P2", "A2"
        },
        "expected_preserved": {"B2", "C3"},
    },

    "shared_dependency": {
        "label": "Shared Dependency",
        "changed_node": "B1",
        "nodes": {
            "B1": ("BELIEF", "Changed belief"),
            "B2": ("BELIEF", "Unchanged shared input"),
            "C1": ("CONCLUSION", "Conclusion with two inputs"),
            "P1": ("PLAN", "Dependent plan"),
            "A1": ("ACTION", "Dependent action"),
            "B3": ("BELIEF", "Independent belief"),
        },
        "edges": [
            ("B1", "C1"),
            ("B2", "C1"),
            ("C1", "P1"),
            ("P1", "A1"),
        ],
        "expected_affected": {"B1", "C1", "P1", "A1"},
        "expected_preserved": {"B2", "B3"},
    },
        "deep_chain": {
        "label": "Deep Dependency Chain",
        "changed_node": "B1",
        "nodes": {
            "B1": ("BELIEF", "Changed root belief"),
            "C1": ("CONCLUSION", "First conclusion"),
            "P1": ("PLAN", "First plan"),
            "A1": ("ACTION", "First action"),
            "C2": ("CONCLUSION", "Second conclusion"),
            "P2": ("PLAN", "Second plan"),
            "A2": ("ACTION", "Second action"),
            "B2": ("BELIEF", "Independent belief"),
        },
        "edges": [
            ("B1", "C1"),
            ("C1", "P1"),
            ("P1", "A1"),
            ("A1", "C2"),
            ("C2", "P2"),
            ("P2", "A2"),
        ],
        "expected_affected": {
            "B1", "C1", "P1", "A1", "C2", "P2", "A2"
        },
        "expected_preserved": {"B2"},
    },
        "diamond_dependency": {
        "label": "Diamond Dependency",
        "changed_node": "B1",
        "nodes": {
            "B1": ("BELIEF", "Changed root belief"),
            "C1": ("CONCLUSION", "Left branch conclusion"),
            "C2": ("CONCLUSION", "Right branch conclusion"),
            "P1": ("PLAN", "Converged plan"),
            "A1": ("ACTION", "Dependent action"),
            "B2": ("BELIEF", "Independent belief"),
        },
        "edges": [
            ("B1", "C1"),
            ("B1", "C2"),
            ("C1", "P1"),
            ("C2", "P1"),
            ("P1", "A1"),
        ],
        "expected_affected": {"B1", "C1", "C2", "P1", "A1"},
        "expected_preserved": {"B2"},
    },
    "multi_belief_change": {
        "label": "Simultaneous Multi-Belief Change",
        "changed_nodes": ["B1", "B2"],
        "changed_node": "B1",
        "nodes": {
            "B1": ("BELIEF", "First changed belief"),
            "B2": ("BELIEF", "Second changed belief"),
            "C1": ("CONCLUSION", "Conclusion dependent on B1"),
            "C2": ("CONCLUSION", "Conclusion dependent on B2"),
            "P1": ("PLAN", "Plan depending on both conclusions"),
            "A1": ("ACTION", "Action depending on the shared plan"),
            "B3": ("BELIEF", "Independent unchanged belief"),
            "C3": ("CONCLUSION", "Conclusion depending on B3"),
        },
        "edges": [
            ("B1", "C1"),
            ("B2", "C2"),
            ("C1", "P1"),
            ("C2", "P1"),
            ("P1", "A1"),
            ("B3", "C3"),
        ],
        "expected_affected": {
            "B1", "B2", "C1", "C2", "P1", "A1"
        },
        "expected_preserved": {"B3", "C3"},
    },

}


# ============================================================
# 2. NODE TYPE MAPPING
# ============================================================

NODE_TYPE_MAP = {
    "BELIEF": NodeType.BELIEF,
    "CONCLUSION": NodeType.CONCLUSION,
    "PLAN": NodeType.PLAN,
    "ACTION": NodeType.ACTION,
}


# ============================================================
# 3. GRAPH CONSTRUCTION
# ============================================================

def build_graph(scenario: dict[str, Any]) -> BeliefGraph:
    """Construct a fresh graph from a scenario definition."""

    graph = BeliefGraph()

    for node_id, (node_type, description) in scenario["nodes"].items():
        graph.add_node(
            BeliefNode(
                id=node_id,
                node_type=NODE_TYPE_MAP[node_type],
                content=description,
            )
        )

    for source, target in scenario["edges"]:
        graph.add_dependency(
            source,
            target,
            DependencyType.REQUIRES,
        )

    return graph


# ============================================================
# 4. METRIC HELPERS
# ============================================================

def safe_divide(
    numerator: float,
    denominator: float,
) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator


def calculate_classification_metrics(
    predicted: set[str],
    expected: set[str],
) -> dict[str, Any]:
    """Compare a strategy's impact footprint with fixed ground truth."""

    true_positives = predicted & expected
    false_positives = predicted - expected
    false_negatives = expected - predicted

    precision = safe_divide(
        len(true_positives),
        len(predicted),
    )

    recall = safe_divide(
        len(true_positives),
        len(expected),
    )

    f1_score = safe_divide(
        2 * precision * recall,
        precision + recall,
    )

    return {
        "true_positives": sorted(true_positives),
        "false_positives": sorted(false_positives),
        "false_negatives": sorted(false_negatives),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
    }


# ============================================================
# 5. STRATEGY EVALUATION
# ============================================================

def evaluate_strategy(
    scenario_key: str,
    strategy_name: str,
    strategy: Any,
) -> dict[str, Any]:
    """Evaluate one strategy on a fresh graph."""

    scenario = SCENARIOS[scenario_key]

    graph = build_graph(scenario)

    changed_nodes = scenario.get(
        "changed_nodes",
        [scenario["changed_node"]],
    )
    changed_node = changed_nodes[0]
    changed_root_set = set(changed_nodes)

    expected_affected = set(
        scenario["expected_affected"]
    )
    expected_preserved = set(
        scenario["expected_preserved"]
    )

    all_nodes = set(graph.graph.nodes)

    # Ground-truth sets must describe the complete graph.
    if expected_affected & expected_preserved:
        raise ValueError(
            f"{scenario_key}: affected and preserved sets overlap."
        )

    if expected_affected | expected_preserved != all_nodes:
        raise ValueError(
            f"{scenario_key}: ground truth does not cover every node."
        )

    # Evaluate the selected strategy.
    result = strategy.evaluate(
        graph=graph,
        changed_nodes=changed_nodes,
        expected_affected=expected_affected,
    )

    # --------------------------------------------------------
    # Impact footprint
    # --------------------------------------------------------
    #
    # Naive:
    #   Predicts no affected nodes.
    #
    # Full recomputation:
    #   Uses its complete recomputation footprint as the impact
    #   footprint. This is a conservative operational footprint,
    #   NOT a claim that every recomputed node truly depends on
    #   the changed node.
    #
    # Belief-Graph:
    #   Uses dependency-aware predicted affected nodes.

    if strategy_name == "naive":
        predicted_affected = set(result.affected_nodes)

    elif strategy_name == "full_recomputation":
        predicted_affected = set(result.recomputed_nodes)

    elif strategy_name == "belief_graph":
        predicted_affected = set(result.affected_nodes)

    else:
        raise ValueError(
            f"Unknown strategy: {strategy_name}"
        )

    # --------------------------------------------------------
    # Classification metrics
    # --------------------------------------------------------

    metrics = calculate_classification_metrics(
        predicted=predicted_affected,
        expected=expected_affected,
    )

    false_positives = set(metrics["false_positives"])
    false_negatives = set(metrics["false_negatives"])

    # --------------------------------------------------------
    # Stale downstream nodes
    # --------------------------------------------------------
    #
    # The changed node itself is excluded because this metric
    # measures missed propagation to dependent nodes.

    expected_downstream = (
        expected_affected - changed_root_set
    )

    stale_downstream = (
        expected_downstream - predicted_affected
    )

    # --------------------------------------------------------
    # Recalculation costs
    # --------------------------------------------------------

    recomputed_nodes = set(result.recomputed_nodes)

    unnecessary_recomputation = (
        recomputed_nodes & expected_preserved
    )

    # --------------------------------------------------------
    # Preservation
    # --------------------------------------------------------
    #
    # Only independently known unaffected nodes count.
    # The denominator is fixed by the scenario ground truth.

    preserved_nodes = set(result.preserved_nodes)

    correctly_preserved = (
        preserved_nodes & expected_preserved
    )

    preservation_ratio = safe_divide(
        len(correctly_preserved),
        len(expected_preserved),
    )

    return {
        "scenario_key": scenario_key,
        "scenario_label": scenario["label"],
        "strategy": strategy_name,
        "impact_metric_interpretation": {
            "naive": "impact_prediction",
            "full_recomputation": "recomputation_footprint_proxy",
            "belief_graph": "impact_prediction",
        }[strategy_name],
        "recomputation_is_modeled": True,
        "changed_node": changed_node,
        "changed_nodes": changed_nodes,

        "total_nodes": len(all_nodes),

        "expected_affected": sorted(expected_affected),
        "expected_preserved": sorted(expected_preserved),

        "predicted_affected": sorted(predicted_affected),

        "true_positives": metrics["true_positives"],
        "false_positives": metrics["false_positives"],
        "false_negatives": metrics["false_negatives"],

        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1_score": metrics["f1_score"],

        "stale_downstream_nodes": sorted(stale_downstream),
        "stale_downstream_count": len(stale_downstream),

        "recomputed_nodes": sorted(recomputed_nodes),
        "recomputed_node_count": len(recomputed_nodes),

        "unnecessary_recomputation": sorted(
            unnecessary_recomputation
        ),
        "unnecessary_recomputation_count": len(
            unnecessary_recomputation
        ),

        "correctly_preserved_nodes": sorted(
            correctly_preserved
        ),
        "preserved_unaffected_count": len(
            correctly_preserved
        ),
        "preservation_ratio": round(
            preservation_ratio,
            4,
        ),

        "declared_operations": result.operations,
        "strategy_details": result.details,

        "classification_success": (
            predicted_affected == expected_affected
        ),

        "measurement_scope": (
            "Graph impact classification and modeled recomputation; "
            "not end-to-end agent execution or production latency."
        ),
    }


# ============================================================
# 6. RUN ALL SCENARIOS
# ============================================================

def run_benchmark() -> list[dict[str, Any]]:
    """Evaluate all strategies against all defined scenarios."""

    strategy_factories = {
        "naive": NaiveBaseline,
        "full_recomputation": FullRecomputationBaseline,
        "belief_graph": BeliefGraphStrategy,
    }

    results = []

    for scenario_key in SCENARIOS:
        for strategy_name, factory in strategy_factories.items():
            result = evaluate_strategy(
                scenario_key=scenario_key,
                strategy_name=strategy_name,
                strategy=factory(),
            )

            results.append(result)

    return results


# ============================================================
# 7. SAVE RESULTS
# ============================================================

def save_results(
    results: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    """Write machine-readable results and print a summary."""

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata = {
        "benchmark": "Belief-Graph Controlled Benchmark v2",
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),

        "scenario_count": len(SCENARIOS),
        "strategy_count": 3,
        "result_count": len(results),

                "scenarios": {
            key: {
                "label": scenario["label"],
                "changed_node": scenario["changed_node"],
                "changed_nodes": scenario.get(
                    "changed_nodes",
                    [scenario["changed_node"]],
                ),
                "expected_affected": sorted(
                    scenario["expected_affected"]
                ),
                "expected_preserved": sorted(
                    scenario["expected_preserved"]
                ),
            }
            for key, scenario in SCENARIOS.items()
        },

        "measurement_warning": (
            "Impact classification and modeled recomputation only. "
            "The benchmark does not establish end-to-end agent "
            "recovery, production latency, or independent stochastic "
            "generalization."
        ),
    }

    json_path = output_dir / "controlled_results.json"
    csv_path = output_dir / "controlled_results.csv"

    json_path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if results:
        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(results[0].keys()),
            )

            writer.writeheader()

            for row in results:
                writer.writerow({
                    key: (
                        json.dumps(value)
                        if isinstance(value, (list, dict))
                        else value
                    )
                    for key, value in row.items()
                })

    # --------------------------------------------------------
    # Console report
    # --------------------------------------------------------

    print("\nBELIEF-GRAPH CONTROLLED BENCHMARK V2")
    print("=" * 88)

    print(f"Scenarios: {len(SCENARIOS)}")
    print("Strategies: 3")
    print(f"Evaluations: {len(results)}")

    for scenario_key, scenario in SCENARIOS.items():
        print("\n" + "=" * 88)
        print(f"SCENARIO: {scenario['label']}")
        changed_nodes = scenario.get(
            "changed_nodes",
            [scenario["changed_node"]],
        )
        print(f"Changed roots: {changed_nodes}")
        print(
            "Expected affected: "
            f"{sorted(scenario['expected_affected'])}"
        )
        print(
            "Expected preserved: "
            f"{sorted(scenario['expected_preserved'])}"
        )

        print("-" * 88)

        scenario_results = [
            row
            for row in results
            if row["scenario_key"] == scenario_key
        ]

        for row in scenario_results:
            print(f"\nStrategy: {row['strategy']}")

            print(
                f"  Precision / Recall / F1: "
                f"{row['precision']:.4f} / "
                f"{row['recall']:.4f} / "
                f"{row['f1_score']:.4f}"
            )

            print(
                "  Predicted affected: "
                f"{row['predicted_affected']}"
            )

            print(
                "  Stale downstream nodes: "
                f"{row['stale_downstream_nodes']}"
            )

            print(
                "  Recomputed nodes: "
                f"{row['recomputed_nodes']}"
            )

            print(
                "  Unnecessary recomputation: "
                f"{row['unnecessary_recomputation']}"
            )

            print(
                "  Preservation ratio: "
                f"{row['preservation_ratio']:.4f}"
            )

            print(
                "  Classification correct: "
                f"{row['classification_success']}"
            )

    # --------------------------------------------------------
    # Overall classification summary
    # --------------------------------------------------------

    print("\n" + "=" * 88)
    print("CLASSIFICATION SUMMARY")
    print("-" * 88)

    for strategy_name in (
        "naive",
        "full_recomputation",
        "belief_graph",
    ):
        strategy_results = [
            row
            for row in results
            if row["strategy"] == strategy_name
        ]

        correct_count = sum(
            row["classification_success"]
            for row in strategy_results
        )

        scenario_count = len(strategy_results)

        mean_f1 = (
            sum(row["f1_score"] for row in strategy_results)
            / scenario_count
            if scenario_count
            else 0.0
        )

        print(
            f"{strategy_name}: "
            f"{correct_count}/{scenario_count} scenarios classified "
            f"exactly; mean F1={mean_f1:.4f}"
        )

    print("\nOUTPUT FILES")
    print(f"JSON: {json_path.resolve()}")
    print(f"CSV:  {csv_path.resolve()}")

    print(
        "\nNote: these results measure impact classification and "
        "modeled recomputation, not end-to-end agent performance."
    )


# ============================================================
# 8. ENTRY POINT
# ============================================================

if __name__ == "__main__":
    output_directory = (
        Path("benchmark_results")
        / "controlled_v2"
    )

    results = run_benchmark()

    save_results(
        results=results,
        output_dir=output_directory,
    )

