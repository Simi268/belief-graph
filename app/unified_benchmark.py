"""
Unified benchmark entry point for Belief-Graph.

Important:
- This runner reuses the existing BenchmarkRunner scenario methods.
- Existing baseline/memory methods in benchmark.py sometimes model strategy outcomes
  from ground-truth sets instead of executing independent agents. The report marks
  these as modelled unless the result details explicitly identify an executed path.
- Repeated runs are useful for reproducibility checks, but deterministic scenarios
  are not independent stochastic trials. Do not interpret repeats as statistical
  generalization.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.benchmark import BenchmarkRunner, BenchmarkResult


SCENARIOS = {
    "scenario1": {
        "label": "API version change",
        "method": "run_all",
    },
    "scenario2": {
        "label": "Multi-branch belief revision",
        "method": "run_scenario2_all",
    },
    "scenario3": {
        "label": "Database schema change",
        "method": "run_scenario3_all",
    },
    "scenario4": {
        "label": "Policy change",
        "method": "run_scenario4_all",
    },
    "scenario6": {
        "label": "Tool unavailable",
        "method": "run_scenario6_all",
    },
    "scenario7": {
        "label": "Stale information",
        "method": "run_scenario7_all",
    },
    "scenario8": {
        "label": "Simultaneous multiple failures",
        "method": "run_scenario8_all",
    },
}


def _strategy_evidence(
    result: BenchmarkResult,
    scenario_key: str = "",
) -> tuple[str, str]:
    """Classify how the current legacy method produced its result.

    Scenario 1 baseline and memory methods execute against DynamicAPIEnvironment.
    Baseline/memory methods in other scenarios may be modelled from ground truth,
    so they must not be reported as independently executed agent traces.
    """
    details = result.details or {}
    strategy = result.strategy.lower()

    # Scenario 1 actually calls the simulated API environment.
    if scenario_key == "scenario1" and strategy in {"baseline", "memory"}:
        return (
            "executed_simulation",
            "Executes the strategy against DynamicAPIEnvironment; "
            "this is a simulated API benchmark, not a production API.",
        )

    if strategy == "belief_graph":
        if details.get("direct_graph_execution"):
            return "executed_component", (
                "Runs Belief-Graph's scenario/impact-analysis component; "
                "not necessarily an end-to-end LLM-agent runtime."
            )
        if details.get("new_action_id") or details.get("second_attempt"):
            return "executed_recovery_path", (
                "Runs the existing Belief-Graph recovery path for this scenario."
            )
        return "scenario_execution", (
            "Runs the existing Belief-Graph scenario implementation."
        )

    # Baseline/memory methods outside Scenario 1 remain explicitly modelled.
    if strategy in {"baseline", "memory"}:
        return "modelled_baseline", (
            "Outcome is constructed by the existing benchmark method; "
            "it is not an independently executed baseline agent trace."
        )

    return "unknown", "Execution provenance was not identified."

def _flatten_result(
    result: BenchmarkResult,
    scenario_key: str,
    scenario_label: str,
    run_index: int,
    elapsed_ms: float,
) -> dict[str, Any]:
    provenance, provenance_note = _strategy_evidence(result, scenario_key)
    return {
        "scenario_key": scenario_key,
        "scenario_label": scenario_label,
        "run_index": run_index,
        "strategy": result.strategy,
        "scenario_id": result.scenario_id,
        "provenance": provenance,
        "provenance_note": provenance_note,
        "task_success": bool(result.task_success),
        "recovery_success": bool(result.recovery_success),
        "stale_actions": int(result.stale_actions),
        "stale_plans": int(result.stale_plans),
        "invalid_plans": int(result.invalid_plans),
        "unnecessary_invalidation": int(result.unnecessary_invalidation),
        "affected_node_count": int(result.affected_node_count),
        "invalidated_node_count": int(result.invalidated_node_count),
        "recomputed_node_count": int(result.recomputed_node_count),
        "unnecessary_recomputation": int(result.unnecessary_recomputation),
        "preserved_node_count": int(result.preserved_node_count),
        "preservation_ratio": float(result.preservation_ratio),
        "propagation_depth": int(result.propagation_depth),
        "recovery_steps": int(result.recovery_steps),
        "tool_calls": int(result.tool_calls),
        "elapsed_ms": round(elapsed_ms, 3),
        "details_json": json.dumps(result.details or {}, sort_keys=True, default=str),
    }


def run_suite(runs: int = 1) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if runs < 1:
        raise ValueError("--runs must be at least 1")

    raw_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    started_at = datetime.now(timezone.utc).isoformat()

    for run_index in range(1, runs + 1):
        for scenario_key, config in SCENARIOS.items():
            runner = BenchmarkRunner()
            method_name = config["method"]
            method = getattr(runner, method_name, None)
            if method is None:
                failures.append({
                    "scenario_key": scenario_key,
                    "run_index": run_index,
                    "error": f"BenchmarkRunner is missing {method_name}()",
                })
                continue

            start = time.perf_counter()
            try:
                results = method()
                elapsed_ms = (time.perf_counter() - start) * 1000
                for result in results:
                    raw_rows.append(
                        _flatten_result(
                            result=result,
                            scenario_key=scenario_key,
                            scenario_label=config["label"],
                            run_index=run_index,
                            elapsed_ms=elapsed_ms,
                        )
                    )
            except Exception as exc:  # preserve other scenarios if one fails
                elapsed_ms = (time.perf_counter() - start) * 1000
                failures.append({
                    "scenario_key": scenario_key,
                    "run_index": run_index,
                    "method": method_name,
                    "elapsed_ms": round(elapsed_ms, 3),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                })

    summary = summarize(raw_rows)
    metadata = {
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_runs_per_scenario": runs,
        "scenario_count": len(SCENARIOS),
        "scenario_registry": SCENARIOS,
        "result_row_count": len(raw_rows),
        "failed_scenario_runs": len(failures),
        "measurement_warning": (
            "Elapsed time measures local benchmark-method wall time, not model "
            "latency or production runtime. Existing baseline/memory results may "
            "be modelled from ground truth rather than independently executed. "
            "The legacy recovery_steps field counts strategy-specific internal "
            "recovery stages and is not yet normalized across every scenario; "
            "do not use it for cross-strategy cost claims without checking the "
            "scenario's operation definitions. tool_calls is reported separately."
        ),
        "metric_definitions": {
            "tool_calls": (
                "Number of simulated/executed tool calls reported by the "
                "scenario method; modelled scenarios may report assumed counts."
            ),
            "recovery_steps": (
                "Legacy count of internal recovery stages reported by the "
                "scenario method, excluding tool_calls where the method does so. "
                "Its event granularity is not normalized across all strategies "
                "and scenarios, so it is descriptive rather than a universally "
                "comparable cost metric."
            ),
            "elapsed_ms": (
                "Local wall-clock time for the benchmark method; not production "
                "latency, model latency, or an end-to-end deployment measurement."
            ),
        },
    }
    return raw_rows, failures, {"metadata": metadata, "summary": summary}


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[(row["scenario_key"], row["scenario_label"], row["strategy"])].append(row)

    output: list[dict[str, Any]] = []
    numeric_metrics = (
        "task_success",
        "recovery_success",
        "stale_actions",
        "stale_plans",
        "invalid_plans",
        "unnecessary_invalidation",
        "affected_node_count",
        "invalidated_node_count",
        "recomputed_node_count",
        "unnecessary_recomputation",
        "preserved_node_count",
        "preservation_ratio",
        "propagation_depth",
        "recovery_steps",
        "tool_calls",
        "elapsed_ms",
    )

    for (scenario_key, scenario_label, strategy), group in sorted(buckets.items()):
        row: dict[str, Any] = {
            "scenario_key": scenario_key,
            "scenario_label": scenario_label,
            "strategy": strategy,
            "provenance": group[0]["provenance"],
            "runs_completed": len(group),
        }
        for metric in numeric_metrics:
            values = [
                (1.0 if item[metric] else 0.0)
                if metric in {"task_success", "recovery_success"}
                else float(item[metric])
                for item in group
            ]
            row[f"mean_{metric}"] = round(statistics.mean(values), 6)
            row[f"min_{metric}"] = round(min(values), 6)
            row[f"max_{metric}"] = round(max(values), 6)
            if len(values) > 1:
                row[f"stdev_{metric}"] = round(statistics.pstdev(values), 6)
            else:
                row[f"stdev_{metric}"] = 0.0
        output.append(row)
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Keep the union of fields so optional fields remain exportable.
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, payload: dict[str, Any], failures: list[dict[str, Any]]) -> None:
    metadata = payload["metadata"]
    summary = payload["summary"]
    lines = [
        "# Belief-Graph Unified Benchmark Report",
        "",
        f"- Started (UTC): {metadata['started_at_utc']}",
        f"- Finished (UTC): {metadata['finished_at_utc']}",
        f"- Requested runs per scenario: {metadata['requested_runs_per_scenario']}",
        f"- Scenarios registered: {metadata['scenario_count']}",
        f"- Result rows: {metadata['result_row_count']}",
        f"- Failed scenario runs: {metadata['failed_scenario_runs']}",
        "",
        "## Results by scenario and strategy",
        "",
        "| Scenario | Strategy | Provenance | Runs | Task success (mean) | Recovery success (mean) | Stale actions (mean) | Recomputed nodes (mean) | Unnecessary recomputation (mean) | Preservation ratio (mean) | Time ms (mean) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            "| {scenario_label} | {strategy} | {provenance} | {runs_completed} | "
            "{mean_task_success:.3f} | {mean_recovery_success:.3f} | "
            "{mean_stale_actions:.3f} | {mean_recomputed_node_count:.3f} | "
            "{mean_unnecessary_recomputation:.3f} | {mean_preservation_ratio:.3f} | "
            "{mean_elapsed_ms:.3f} |".format(**row)
        )

    lines += [
        "",
        "## Interpretation cautions",
        "",
        "- `modelled_baseline` means the legacy benchmark method constructs a result from assumptions/ground truth rather than executing an independent agent. Do not treat it as measured agent performance.",
        "- `executed_component` means Belief-Graph's impact-analysis component ran; this is not necessarily a full LLM-agent comparison.",
        "- `elapsed_ms` is local Python benchmark-method wall time and is not production latency.",
        "- `tool_calls` and `recovery_steps` measure different things: tool calls count API/tool attempts, while recovery steps count internal recovery stages as encoded by each legacy scenario method.",
        "- `recovery_steps` is not yet normalized to the same event granularity across every strategy/scenario. Do not use it alone to claim lower recovery cost; inspect the scenario implementation and provenance first.",
        "- Repeated deterministic runs are reproducibility checks, not independent statistical trials.",
        "- A task-success mean is the fraction of returned runs marked successful; ground-truth checks are only as strong as the scenario's current assertions.",
    ]

    if failures:
        lines += ["", "## Failed scenario runs", ""]
        for failure in failures:
            lines.append(
                f"- `{failure.get('scenario_key')}` run {failure.get('run_index')}: "
                f"{failure.get('error_type', 'Error')}: {failure.get('error')}"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all registered Belief-Graph benchmark scenarios.")
    parser.add_argument("--runs", type=int, default=1, help="Repeat each scenario this many times (default: 1).")
    parser.add_argument(
        "--output-dir",
        default="benchmark_results",
        help="Directory for JSON, CSV, and Markdown output (default: benchmark_results).",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows, failures, payload = run_suite(runs=args.runs)
    payload["metadata"]["result_row_count"] = len(rows)
    payload["metadata"]["failed_scenario_runs"] = len(failures)
    payload["failures"] = failures
    payload["results"] = rows

    json_path = output_dir / "benchmark_results.json"
    csv_path = output_dir / "benchmark_results.csv"
    summary_csv_path = output_dir / "benchmark_summary.csv"
    markdown_path = output_dir / "benchmark_report.md"

    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    write_csv(csv_path, rows)
    write_csv(summary_csv_path, payload["summary"])
    write_markdown(markdown_path, payload, failures)

    print("\nBELIEF-GRAPH UNIFIED BENCHMARK")
    print("=" * 72)
    print(f"Scenarios registered : {len(SCENARIOS)}")
    print(f"Runs per scenario    : {args.runs}")
    print(f"Result rows          : {len(rows)}")
    print(f"Failed scenario runs : {len(failures)}")
    print(f"Output directory     : {output_dir.resolve()}")
    print("\nFiles:")
    print(f"  {json_path}")
    print(f"  {csv_path}")
    print(f"  {summary_csv_path}")
    print(f"  {markdown_path}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(
                f"  - {failure.get('scenario_key')} run {failure.get('run_index')}: "
                f"{failure.get('error_type', 'Error')}: {failure.get('error')}"
            )
        return 1

    print("\nNote: inspect provenance labels in the report before making comparative claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
