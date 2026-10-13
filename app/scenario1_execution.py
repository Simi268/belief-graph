"""Executable Scenario 1: API version change recovery experiment.

Compares:
1. Baseline: continues with its stale API version.
2. Full restart: reconstructs the task state and retries.
3. Belief-Graph: invalidates affected state and selectively recovers.

All strategies use the same generated instance and API environment rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

from app.benchmark_instances import (
    BenchmarkInstance,
    generate_scenario1_instance,
)
from app.environment import DynamicAPIEnvironment
from app.seeded_strategy_adapters import _build_graph
from app.models import NodeStatus


@dataclass
class ExecutionResult:
    strategy: str
    instance_id: str
    task_success: bool
    stale_actions: int
    api_calls: int
    recomputed_nodes: int
    unnecessary_recomputation: int
    recovery_steps: int
    execution_seconds: float
    trace: list[dict[str, Any]]


def _record(
    trace: list[dict[str, Any]],
    event: str,
    **details: Any,
) -> None:
    trace.append({"event": event, **details})


def _execute_api(
    environment: DynamicAPIEnvironment,
    version: str,
    trace: list[dict[str, Any]],
) -> bool:
    result = environment.call_api(version)

    _record(
        trace,
        "api_call",
        requested_version=version,
        actual_version=environment.get_api_version(),
        result=result,
    )

    return bool(result["success"])


def _prepare(
    instance: BenchmarkInstance,
) -> DynamicAPIEnvironment:
    """Create the same initial API state for each strategy."""
    environment = DynamicAPIEnvironment()
    environment.set_api_version("v1")
    return environment


def run_baseline(
    instance: BenchmarkInstance,
) -> ExecutionResult:
    """Keep the original plan and attempt its stale API call."""
    started = perf_counter()
    trace: list[dict[str, Any]] = []
    environment = _prepare(instance)

    _record(trace, "task_started", api_version="v1")
    environment.set_api_version("v2")
    _record(trace, "environment_changed", api_version="v2")

    success = _execute_api(environment, "v1", trace)

    return ExecutionResult(
        strategy="baseline",
        instance_id=instance.instance_id,
        task_success=success,
        stale_actions=int(not success),
        api_calls=1,
        recomputed_nodes=0,
        unnecessary_recomputation=0,
        recovery_steps=0,
        execution_seconds=perf_counter() - started,
        trace=trace,
    )


def run_full_restart(
    instance: BenchmarkInstance,
) -> ExecutionResult:
    """Rebuild all task nodes before retrying with the current API version."""
    started = perf_counter()
    trace: list[dict[str, Any]] = []
    environment = _prepare(instance)

    _record(trace, "task_started", api_version="v1")
    environment.set_api_version("v2")
    _record(trace, "environment_changed", api_version="v2")

    first_success = _execute_api(environment, "v1", trace)

    if first_success:
        success = True
        recomputed_nodes = 0
        recovery_steps = 0
    else:
        _record(trace, "full_restart_started")

        # This experiment models reconstruction of all benchmark task nodes.
        recomputed_nodes = len(instance.nodes)
        recovery_steps = 1

        current_version = environment.get_api_version()
        _record(
            trace,
            "task_reconstructed",
            recomputed_node_count=recomputed_nodes,
            api_version=current_version,
        )

        success = _execute_api(environment, current_version, trace)

    return ExecutionResult(
        strategy="full_restart",
        instance_id=instance.instance_id,
        task_success=success,
        stale_actions=int(not first_success),
        api_calls=len(
            [event for event in trace if event["event"] == "api_call"]
        ),
        recomputed_nodes=recomputed_nodes,
        unnecessary_recomputation=len(instance.expected_preserved)
        if recomputed_nodes
        else 0,
        recovery_steps=recovery_steps,
        execution_seconds=perf_counter() - started,
        trace=trace,
    )


def run_belief_graph(
    instance: BenchmarkInstance,
) -> ExecutionResult:
    """Use graph impact analysis to target recovery."""
    started = perf_counter()
    trace: list[dict[str, Any]] = []
    environment = _prepare(instance)
    graph = _build_graph(instance)

    _record(trace, "task_started", api_version="v1")
    environment.set_api_version("v2")
    _record(trace, "environment_changed", api_version="v2")

    first_success = _execute_api(environment, "v1", trace)

    recomputed_nodes = 0
    recovery_steps = 0
    success = first_success

    if not first_success:
        impact = graph.propagate_state_impact(
            instance.changed_belief,
            initial_status=NodeStatus.INVALID,
        )
        graph.apply_state_impact(impact)

        affected = {
            instance.changed_belief,
            *(
                node_id
                for node_id, details in impact.items()
                if details["impact"] != NodeStatus.ACTIVE
            ),
        }

        # Preserve unrelated branches. Recompute only affected task artifacts.
        recomputed_nodes = len(affected)
        recovery_steps = 1

        _record(
            trace,
            "selective_revision",
            affected_nodes=sorted(affected),
            preserved_nodes=sorted(set(instance.node_ids) - affected),
        )

        current_version = environment.get_api_version()
        _record(
            trace,
            "plan_reconstructed",
            api_version=current_version,
            recomputed_node_count=recomputed_nodes,
        )

        success = _execute_api(environment, current_version, trace)

    affected_nodes = set(instance.node_ids) - set(instance.expected_preserved)

    return ExecutionResult(
        strategy="belief_graph",
        instance_id=instance.instance_id,
        task_success=success,
        stale_actions=int(not first_success),
        api_calls=len(
            [event for event in trace if event["event"] == "api_call"]
        ),
        recomputed_nodes=recomputed_nodes,
        unnecessary_recomputation=len(
            set(instance.expected_preserved) & affected_nodes
        ),
        recovery_steps=recovery_steps,
        execution_seconds=perf_counter() - started,
        trace=trace,
    )


def run_scenario1(seed: int = 1) -> dict[str, Any]:
    """Run each strategy on the same generated scenario."""
    instance = generate_scenario1_instance(seed=seed)

    strategies = (
        run_baseline,
        run_full_restart,
        run_belief_graph,
    )

    results = [
        asdict(strategy(instance))
        for strategy in strategies
    ]

    return {
        "scenario": "scenario1_api_version_change",
        "seed": seed,
        "instance_id": instance.instance_id,
        "results": results,
        "note": (
            "API calls execute against DynamicAPIEnvironment. "
            "Task reconstruction and recomputation counts are explicit "
            "simulation policies, not measured LLM-agent execution."
        ),
    }


if __name__ == "__main__":
    import json

    result = run_scenario1(seed=1)
    print(json.dumps(result, indent=2))