"""Actual-runtime recovery strategy benchmark for BeliefGraph.

Run from the repository root:
    python -m app.actual_runtime_recovery_benchmark --trials 10

This benchmark invokes AgentRuntime and RecoveryEngine for every strategy.
The recompute callback is a deterministic workload proxy, not a domain-specific
semantic recomputation engine. Results therefore measure real recovery
orchestration and callback workload, not general agent reasoning quality.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment
from app.models import DependencyType, NodeType
from app.recovery import RecoveryEngine


STRATEGIES = ("baseline_no_callback", "full_callback_pass", "engine_selective")


def build_failed_runtime() -> tuple[AgentRuntime, DynamicAPIEnvironment, dict[str, Any]]:
    """Create the same API-version failure and an independent branch per trial."""
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief("B1", "Customer API version is v1", value="v1")
    agent.create_node("C1", NodeType.CONCLUSION, "Customer data can be retrieved")
    agent.create_node("P1", NodeType.PLAN, "Retrieve customer data")
    agent.create_node("A1", NodeType.ACTION, "Call customer API using v1")
    agent.add_dependency("B1", "C1", DependencyType.REQUIRES)
    agent.add_dependency("C1", "P1", DependencyType.REQUIRES)
    agent.add_dependency("P1", "A1", DependencyType.REQUIRES)

    agent.create_belief("B3", "Reporting database is available", value=True)
    agent.create_node("C3", NodeType.CONCLUSION, "Reporting data can be generated")
    agent.create_node("P3", NodeType.PLAN, "Generate reporting data")
    agent.add_dependency("B3", "C3", DependencyType.REQUIRES)
    agent.add_dependency("C3", "P3", DependencyType.REQUIRES)

    environment.set_api_version("v2")
    failed_result = agent.execute_api_action(
        environment=environment,
        belief_id="B1",
        action_id="A1",
    )
    if failed_result.get("environment_result", {}).get("success") is not False:
        raise RuntimeError("Benchmark setup failed: expected the v1 API call to fail.")
    return agent, environment, failed_result


def _callback_work(node: Any, observed_ids: list[str]) -> dict[str, Any]:
    """Record an evaluation; intentionally does not claim to recompute semantics."""
    observed_ids.append(node.id)
    # A small deterministic result makes callback invocation observable.
    return {"node_id": node.id, "callback_evaluated": True}


def run_trial(strategy: str, trial_index: int) -> dict[str, Any]:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")

    started = time.perf_counter()
    agent, environment, failed_result = build_failed_runtime()
    callback_node_ids: list[str] = []
    callback: Callable[[Any], dict[str, Any]] = (
        lambda node: _callback_work(node, callback_node_ids)
    )

    engine = RecoveryEngine(agent)
    kwargs: dict[str, Any] = {
        "action_result": failed_result,
        "evidence_id": f"E-{strategy}-{trial_index}",
        "new_belief_id": "B2",
        "new_action_id": "A2",
        "environment": environment,
    }

    if strategy == "engine_selective":
        result = engine.recover_from_action_failure(**kwargs, recompute_node=callback)
    else:
        result = engine.recover_from_action_failure(**kwargs)
        if strategy == "full_callback_pass":
            # Full-work policy: evaluate every node present after the same
            # real recovery path. This is a workload proxy, not semantic recompute.
            for node_id, attributes in list(agent.graph.graph.nodes(data=True)):
                # Evidence/conflict identifiers may also appear in the NetworkX
                # graph but are not BeliefNode objects and have no "data" field.
                node = attributes.get("data")
                if node is not None:
                    callback(node)

    elapsed_ms = (time.perf_counter() - started) * 1000
    execution = result.get("execution") or {}
    independent_branch_preserved = all(
        agent.graph.get_node(node_id).status.value == "active"
        for node_id in ("B3", "C3", "P3")
    )
    replacement_succeeded = execution.get("success") is True
    callback_failures = (
        (result.get("selective_recovery") or {}).get("metrics", {}).get(
            "failed_recomputations", 0
        )
    )

    # The API's expected result is independently known: v1 must fail against v2,
    # and the replacement based on revised belief B2 must succeed.
    correct = (
        replacement_succeeded
        and independent_branch_preserved
        and callback_failures == 0
    )

    return {
        "strategy": strategy,
        "trial": trial_index,
        "correct": correct,
        "replacement_succeeded": replacement_succeeded,
        "independent_branch_preserved": independent_branch_preserved,
        "callback_evaluation_count": len(callback_node_ids),
        "callback_node_ids": callback_node_ids,
        "callback_failures": callback_failures,
        "recovery_engine_status": result.get("status"),
        "end_to_end_elapsed_ms": round(elapsed_ms, 3),
        "recovery_engine_elapsed_ms": (
            (result.get("recovery_metrics") or {}).get("recovery_duration_ms")
        ),
        "graph_node_count_after_recovery": len(agent.graph.graph.nodes),
    }


def run_benchmark(trials: int) -> dict[str, Any]:
    if trials < 1:
        raise ValueError("--trials must be at least 1")

    measurements = [
        run_trial(strategy, trial)
        for trial in range(1, trials + 1)
        for strategy in STRATEGIES
    ]

    summary: dict[str, Any] = {}
    for strategy in STRATEGIES:
        rows = [row for row in measurements if row["strategy"] == strategy]
        latencies = [row["end_to_end_elapsed_ms"] for row in rows]
        callback_counts = [row["callback_evaluation_count"] for row in rows]
        summary[strategy] = {
            "trials": len(rows),
            "correct_trials": sum(row["correct"] for row in rows),
            "correctness_rate": round(
                sum(row["correct"] for row in rows) / len(rows), 4
            ),
            "replacement_success_rate": round(
                sum(row["replacement_succeeded"] for row in rows) / len(rows), 4
            ),
            "unrelated_branch_preservation_rate": round(
                sum(row["independent_branch_preserved"] for row in rows) / len(rows),
                4,
            ),
            "mean_callback_evaluations": round(statistics.mean(callback_counts), 3),
            "mean_end_to_end_elapsed_ms": round(statistics.mean(latencies), 3),
            "median_end_to_end_elapsed_ms": round(statistics.median(latencies), 3),
            "mean_recovery_engine_elapsed_ms": round(
                statistics.mean(
                    row["recovery_engine_elapsed_ms"]
                    for row in rows
                    if row["recovery_engine_elapsed_ms"] is not None
                ),
                3,
            ),
        }

    return {
        "benchmark": "beliefgraph_actual_runtime_recovery_strategy_comparison",
        "measurement_note": (
            "RecoveryEngine/AgentRuntime are exercised for every trial. "
            "Callback evaluations are a workload proxy; the callback does not "
            "perform domain-specific semantic recomputation. Timing is local "
            "process timing and is not a production latency claim."
        ),
        "trials_per_strategy": trials,
        "total_trials": len(measurements),
        "summary": summary,
        "measurements": measurements,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/actual_runtime_recovery_benchmark.json"),
        help="Output JSON path (default: artifacts/actual_runtime_recovery_benchmark.json)",
    )
    args = parser.parse_args()

    report = run_benchmark(args.trials)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Trials per strategy: {report['trials_per_strategy']}")
    print(f"Total trials: {report['total_trials']}")
    print()
    print(
        f"{'Strategy':<24} {'Correct':>9} {'Mean callbacks':>15} "
        f"{'Mean E2E ms':>13} {'Median E2E ms':>15}"
    )
    print("-" * 82)
    for strategy, values in report["summary"].items():
        print(
            f"{strategy:<24} "
            f"{values['correct_trials']}/{values['trials']:>7} "
            f"{values['mean_callback_evaluations']:>15.3f} "
            f"{values['mean_end_to_end_elapsed_ms']:>13.3f} "
            f"{values['median_end_to_end_elapsed_ms']:>15.3f}"
        )
    print(f"\nJSON report written to: {args.output}")


if __name__ == "__main__":
    main()
