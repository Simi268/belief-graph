"""Branching/shared-dependency semantic recomputation benchmark.

Run from the BeliefGraph repository root:
    python semantic_recomputation_graph_benchmark.py --trials 100

Compares full recomputation with selective recomputation after B0 changes.
The graph contains branching, a shared downstream dependency, and an unrelated
cached branch. This is a controlled microbenchmark, not an end-to-end recovery
pipeline benchmark.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from app.agent import AgentRuntime
from app.models import DependencyType, NodeType
from app.semantic_recomputation import SemanticRecomputer


def build_scenario():
    agent = AgentRuntime()
    agent.create_belief("B0", "Changed input", value=2)
    agent.create_belief("BU", "Independent input", value=100)

    node_types = {
        "N1": NodeType.CONCLUSION,
        "N2": NodeType.PLAN,
        "N3": NodeType.CONCLUSION,
        "N4": NodeType.PLAN,
        "U1": NodeType.CONCLUSION,
        "U2": NodeType.PLAN,
    }
    descriptions = {
        "N1": "First transform",
        "N2": "Left branch transform",
        "N3": "Right branch transform",
        "N4": "Join shared dependencies",
        "U1": "Independent transform",
        "U2": "Independent downstream transform",
    }
    for node_id, node_type in node_types.items():
        agent.create_node(node_id, node_type, descriptions[node_id])

    # Main graph: B0 -> N1 -> {N2, N3} -> N4.
    edges = [
        ("B0", "N1"),
        ("N1", "N2"),
        ("N1", "N3"),
        ("N2", "N4"),
        ("N3", "N4"),
        # Independent branch: BU -> U1 -> U2.
        ("BU", "U1"),
        ("U1", "U2"),
    ]
    for source, target in edges:
        agent.add_dependency(source, target, DependencyType.REQUIRES)

    evaluators = {
        "N1": lambda node, parents: parents["B0"] + 1,
        "N2": lambda node, parents: parents["N1"] + 2,
        "N3": lambda node, parents: parents["N1"] * 3,
        "N4": lambda node, parents: parents["N2"] + parents["N3"],
        "U1": lambda node, parents: parents["BU"] + 7,
        "U2": lambda node, parents: parents["U1"] * 2,
    }
    return agent, evaluators


def topological_derived_ids(agent):
    import networkx as nx

    ordered = nx.topological_sort(agent.graph.graph)
    result = []
    for node_id in ordered:
        data = agent.graph.graph.nodes[node_id].get("data")
        if data is not None and data.node_type != NodeType.BELIEF:
            result.append(node_id)
    return result


def calculate_expected(b0_value=5):
    n1 = b0_value + 1
    n2 = n1 + 2
    n3 = n1 * 3
    return {"N1": n1, "N2": n2, "N3": n3, "N4": n2 + n3, "U1": 107, "U2": 214}


def run_trial(strategy: str, trial: int):
    agent, evaluators = build_scenario()
    recomputer = SemanticRecomputer(agent, evaluators)

    initial = recomputer.recompute_nodes(topological_derived_ids(agent))
    if not initial["success"]:
        raise RuntimeError(f"Initial evaluation failed: {initial['failures']}")

    # Change the source belief and recompute the affected dependency closure.
    agent.graph.get_node("B0").value = 5
    if strategy == "full":
        selected = topological_derived_ids(agent)
    elif strategy == "selective":
        selected = ["N1", "N2", "N3", "N4"]
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    started = time.perf_counter()
    result = recomputer.recompute_nodes(selected)
    elapsed_ms = (time.perf_counter() - started) * 1000

    expected = calculate_expected()
    actual = {node_id: agent.graph.get_node(node_id).value for node_id in expected}
    correct = result["success"] and actual == expected
    independent_preserved = actual["U1"] == 107 and actual["U2"] == 214
    return {
        "strategy": strategy,
        "trial": trial,
        "selected_count": len(selected),
        "evaluated_count": len(result["recomputed_node_ids"]),
        "correct": bool(correct),
        "independent_branch_preserved": bool(independent_preserved),
        "elapsed_ms": round(elapsed_ms, 6),
        "failures": result["failures"],
    }


def summarize(rows):
    summary = {}
    for strategy in ("full", "selective"):
        subset = [row for row in rows if row["strategy"] == strategy]
        latencies = sorted(row["elapsed_ms"] for row in subset)
        summary[strategy] = {
            "trials": len(subset),
            "correct_trials": sum(row["correct"] for row in subset),
            "independent_branch_preserved_trials": sum(row["independent_branch_preserved"] for row in subset),
            "mean_evaluated_nodes": statistics.mean(row["evaluated_count"] for row in subset),
            "mean_latency_ms": statistics.mean(latencies),
            "median_latency_ms": statistics.median(latencies),
            "p95_latency_ms": latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))],
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("artifacts/branching_semantic_recomputation_benchmark.json"))
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("--trials must be positive")

    rows = [
        run_trial(strategy, trial)
        for trial in range(1, args.trials + 1)
        for strategy in ("full", "selective")
    ]
    summary = summarize(rows)
    report = {
        "benchmark": "beliefgraph_branching_semantic_recomputation",
        "trials_per_strategy": args.trials,
        "total_trials": len(rows),
        "graph": "B0 -> N1 -> (N2, N3) -> N4; independent BU -> U1 -> U2",
        "expected_after_change": calculate_expected(),
        "summary": summary,
        "measurements": rows,
        "limitations": [
            "Controlled deterministic graph; not a production workload.",
            "Does not yet exercise the complete recovery pipeline.",
            "Latency is a microbenchmark and may be affected by measurement noise.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Trials per strategy: {args.trials}")
    print(f"Total trials: {len(rows)}")
    print(f"{'Strategy':<12} {'Correct':>12} {'Branch kept':>13} {'Mean nodes':>12} {'Mean ms':>12} {'Median ms':>12} {'P95 ms':>12}")
    print("-" * 91)
    for strategy, values in summary.items():
        print(
            f"{strategy:<12} {values['correct_trials']:>5}/{values['trials']:<6} "
            f"{values['independent_branch_preserved_trials']:>5}/{values['trials']:<7} "
            f"{values['mean_evaluated_nodes']:>12.2f} {values['mean_latency_ms']:>12.4f} "
            f"{values['median_latency_ms']:>12.4f} {values['p95_latency_ms']:>12.4f}"
        )
    print(f"\nJSON report written to: {args.output}")


if __name__ == "__main__":
    main()
