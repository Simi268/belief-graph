"""Controlled semantic recomputation benchmark.

Run from repository root:
    python semantic_recomputation_benchmark.py --trials 100

This benchmark uses the project's AgentRuntime/BeliefGraph storage and a
registered, deterministic evaluator contract. It compares a full topological
recompute with selective recomputation of the changed node's descendants.
Ground truth is computed independently from the graph engine.
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


def build_scenario(chain_length: int):
    if chain_length < 2:
        raise ValueError("chain_length must be >= 2")
    agent = AgentRuntime()
    agent.create_belief("B0", "Input", value=2)

    evaluator_map = {}
    previous_id = "B0"
    derived_ids = []
    for index in range(1, chain_length + 1):
        node_id = f"N{index}"
        node_type = NodeType.CONCLUSION if index % 2 else NodeType.PLAN
        agent.create_node(node_id, node_type, f"Deterministic transform {index}")
        agent.add_dependency(previous_id, node_id, DependencyType.REQUIRES)
        # Every node adds its one-based index to its predecessor value.
        evaluator_map[node_id] = (
            lambda node, parents, _previous=previous_id, _i=index:
            parents[_previous] + _i
        )
        previous_id = node_id
        derived_ids.append(node_id)

    # Unrelated branch proves selective recomputation avoids independent work.
    agent.create_belief("BU", "Independent input", value=100)
    agent.create_node("U1", NodeType.CONCLUSION, "Independent transform")
    agent.create_node("U2", NodeType.PLAN, "Independent transform")
    agent.add_dependency("BU", "U1", DependencyType.REQUIRES)
    agent.add_dependency("U1", "U2", DependencyType.REQUIRES)
    evaluator_map["U1"] = lambda node, parents: parents["BU"] + 7
    evaluator_map["U2"] = lambda node, parents: parents["U1"] * 2

    return agent, evaluator_map, derived_ids


def topological_derived_ids(agent):
    import networkx as nx

    order = list(nx.topological_sort(agent.graph.graph))
    result = []
    for node_id in order:
        attrs = agent.graph.graph.nodes[node_id]
        if attrs.get("data") is not None:
            node = attrs["data"]
            if node.node_type != NodeType.BELIEF:
                result.append(node_id)
    return result


def expected_values(chain_length):
    values = {"B0": 2, "BU": 100}
    for index in range(1, chain_length + 1):
        predecessor_id = "B0" if index == 1 else f"N{index - 1}"
        values[f"N{index}"] = values[predecessor_id] + index
    values["U1"] = 107
    values["U2"] = 214
    return values


def run_trial(strategy, chain_length, trial):
    agent, evaluator_map, derived_ids = build_scenario(chain_length)
    recomputer = SemanticRecomputer(agent, evaluator_map)

    # Establish valid cached values for every branch before the change.
    # This ensures selective recovery can legitimately preserve the independent
    # branch instead of comparing untouched None values with expected outputs.
    initial_order = topological_derived_ids(agent)
    initial_result = recomputer.recompute_nodes(initial_order)
    if not initial_result["success"]:
        raise RuntimeError(f"Initial graph evaluation failed: {initial_result['failures']}")

    # Simulate a source-belief change. Ground truth is computed independently
    # from the same explicit mathematical specification.
    agent.graph.get_node("B0").value = 5
    expected = expected_values(chain_length)
    expected["B0"] = 5
    running = 5
    for index in range(1, chain_length + 1):
        running += index
        expected[f"N{index}"] = running

    if strategy == "full":
        selected = topological_derived_ids(agent)
    elif strategy == "selective":
        # Only the changed source's descendants are candidates. Independent
        # branch U1/U2 is deliberately excluded.
        selected = list(derived_ids)
    else:
        raise ValueError(strategy)

    started = time.perf_counter()
    result = recomputer.recompute_nodes(selected)
    elapsed_ms = (time.perf_counter() - started) * 1000

    checked_ids = [*derived_ids, "U1", "U2"]
    actual = {node_id: agent.graph.get_node(node_id).value for node_id in checked_ids}
    # For selective, independent nodes retain their pre-run values; those are
    # computed from their own source and are valid and expected.
    correctness = (
        result["success"]
        and all(actual[node_id] == expected[node_id] for node_id in checked_ids)
    )
    return {
        "strategy": strategy,
        "trial": trial,
        "chain_length": chain_length,
        "selected_count": len(selected),
        "evaluated_count": len(result["recomputed_node_ids"]),
        "correct": correctness,
        "elapsed_ms": round(elapsed_ms, 4),
        "failed_nodes": result["failures"],
    }


def run_benchmark(trials, sizes):
    rows = [
        run_trial(strategy, size, trial)
        for size in sizes
        for trial in range(1, trials + 1)
        for strategy in ("full", "selective")
    ]
    summary = {}
    for size in sizes:
        for strategy in ("full", "selective"):
            subset = [
                row for row in rows
                if row["chain_length"] == size and row["strategy"] == strategy
            ]
            latencies = [row["elapsed_ms"] for row in subset]
            counts = [row["evaluated_count"] for row in subset]
            summary[f"{strategy}_n{size}"] = {
                "trials": len(subset),
                "correct_trials": sum(row["correct"] for row in subset),
                "correctness_rate": sum(row["correct"] for row in subset) / len(subset),
                "mean_evaluated_nodes": statistics.mean(counts),
                "mean_latency_ms": statistics.mean(latencies),
                "median_latency_ms": statistics.median(latencies),
                "p95_latency_ms": sorted(latencies)[min(len(latencies)-1, int(0.95 * len(latencies)))],
            }
    return {
        "benchmark": "beliefgraph_semantic_recomputation",
        "trials_per_strategy_per_size": trials,
        "graph_chain_sizes": sizes,
        "total_trials": len(rows),
        "semantics": "Each derived node adds its one-based position to its predecessor. The independent branch computes (100 + 7) * 2.",
        "summary": summary,
        "measurements": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--sizes", type=int, nargs="+", default=[5, 20, 50])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/semantic_recomputation_benchmark.json"),
    )
    args = parser.parse_args()
    if args.trials < 1 or any(size < 2 for size in args.sizes):
        parser.error("--trials must be positive and every size must be >= 2")

    report = run_benchmark(args.trials, args.sizes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Trials per strategy per size: {args.trials}")
    print(f"Graph chain sizes: {args.sizes}")
    print(f"Total trials: {report['total_trials']}")
    print(f"{'Case':<18} {'Correct':>10} {'Mean nodes':>12} {'Mean ms':>12} {'Median ms':>12} {'P95 ms':>12}")
    print("-" * 82)
    for case, values in report["summary"].items():
        print(
            f"{case:<18} "
            f"{values['correct_trials']}/{values['trials']:>7} "
            f"{values['mean_evaluated_nodes']:>12.2f} "
            f"{values['mean_latency_ms']:>12.4f} "
            f"{values['median_latency_ms']:>12.4f} "
            f"{values['p95_latency_ms']:>12.4f}"
        )
    print(f"\nJSON report written to: {args.output}")


if __name__ == "__main__":
    main()
