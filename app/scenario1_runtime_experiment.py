"""Scenario 1: execute recovery on a generated benchmark instance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.agent import AgentRuntime
from app.benchmark_instances import generate_scenario1_instance
from app.environment import DynamicAPIEnvironment
from app.models import DependencyType, NodeType
from app.recovery import RecoveryEngine


@dataclass
class RuntimeExperimentResult:
    strategy: str
    success: bool
    final_status: str
    initial_api_call: dict[str, Any]
    recovery_status: str
    retry_result: dict[str, Any] | None
    affected_nodes: list[str]
    preserved_nodes: list[str]
    trace: list[dict[str, Any]]
    ground_truth_validation: dict[str, Any]


def run_belief_graph_runtime_experiment(
    seed: int = 1,
) -> RuntimeExperimentResult:
    """Run recovery on a generated instance and validate its node states."""

    instance = generate_scenario1_instance(seed=seed)
    runtime = AgentRuntime()
    environment = DynamicAPIEnvironment()
    trace: list[dict[str, Any]] = []

    # Build every node from the generated benchmark instance.
    for instance_node in instance.nodes:
        node_id = instance_node.id
        node_type = NodeType(instance_node.node_type.value)

        if node_type == NodeType.BELIEF:
            if node_id == instance.changed_belief:
                runtime.create_belief(
                    belief_id=node_id,
                    content="The customer API uses version v1.",
                    value="v1",
                    source="initial_environment",
                )
            else:
                runtime.create_belief(
                    belief_id=node_id,
                    content=f"Independent benchmark belief: {node_id}",
                    value=f"independent_{node_id}",
                    source="benchmark_instance",
                )
        else:
            runtime.create_node(
                node_id=node_id,
                node_type=node_type,
                content=f"Benchmark {node_type.value}: {node_id}",
            )

    # Use the generated edges, preserving their dependency semantics.
    for edge in instance.edges:
        runtime.add_dependency(
            edge.source,
            edge.target,
            DependencyType(edge.dependency_type.value),
        )

    original_node_ids = {node.id for node in instance.nodes}
    old_action_id = next(
        node.id
        for node in instance.nodes
        if node.node_type == NodeType.ACTION
        and node.id.startswith("A1_")
    )

    trace.append({
        "event": "benchmark_instance_created",
        "instance_id": instance.instance_id,
        "seed": seed,
        "node_count": len(instance.nodes),
        "edge_count": len(instance.edges),
        "changed_belief": instance.changed_belief,
    })

    # Change the environment after creating the initial belief graph.
    environment.set_api_version("v2")

    trace.append({
        "event": "environment_changed",
        "actual_api_version": environment.get_api_version(),
    })

    # Execute the original action through AgentRuntime.
    initial_result = runtime.execute_api_action(
        environment,
        belief_id=instance.changed_belief,
        action_id=old_action_id,
    )

    trace.append({
        "event": "initial_action_execution",
        "result": initial_result,
    })

    # Recover using the real recovery engine.
    recovery = RecoveryEngine(runtime).recover_from_action_failure(
        action_result=initial_result,
        evidence_id=f"evidence_v2_seed_{seed}",
        new_belief_id=f"{instance.changed_belief}_v2",
        new_action_id=f"{old_action_id}_v2",
    )

    recovery_status = recovery.get("status", "unknown")
    new_action = recovery.get("new_action")

    trace.append({
        "event": "recovery_completed",
        "status": recovery_status,
        "new_action_created": new_action is not None,
    })

    retry_result = None

    if new_action is not None:
        retry_result = runtime.execute_api_action(
            environment,
            belief_id=f"{instance.changed_belief}_v2",
            action_id=new_action.id,
        )

        trace.append({
            "event": "replacement_action_execution",
            "result": retry_result,
        })

    # Only compare nodes belonging to the original generated instance.
    # Newly created recovery nodes are not part of its ground truth.
    actual_statuses: dict[str, str] = {}

    for node_id in original_node_ids:
        node_data = runtime.graph.graph.nodes[node_id].get("data")

        if node_data is None:
            raise RuntimeError(
                f"Benchmark node {node_id!r} has no BeliefNode data."
            )

        actual_statuses[node_id] = node_data.status.value

    actual_invalidated = {
        node_id
        for node_id, status in actual_statuses.items()
        if status == "invalid"
    }
    actual_reevaluation = {
        node_id
        for node_id, status in actual_statuses.items()
        if status == "requires_reevaluation"
    }
    actual_uncertain = {
        node_id
        for node_id, status in actual_statuses.items()
        if status == "uncertain"
    }
    actual_preserved = {
        node_id
        for node_id, status in actual_statuses.items()
        if status == "active"
    }

    # Expected sets come from the independently generated benchmark.
    expected_invalidated = set(instance.expected_invalidated)
    expected_reevaluation = set(instance.expected_reevaluation)
    expected_uncertain = set(instance.expected_uncertain)
    expected_preserved = set(instance.expected_preserved)

    validation = {
        "instance_id": instance.instance_id,
        "invalidated": {
            "expected": sorted(expected_invalidated),
            "actual": sorted(actual_invalidated),
            "match": actual_invalidated == expected_invalidated,
        },
        "reevaluation": {
            "expected": sorted(expected_reevaluation),
            "actual": sorted(actual_reevaluation),
            "match": actual_reevaluation == expected_reevaluation,
        },
        "uncertain": {
            "expected": sorted(expected_uncertain),
            "actual": sorted(actual_uncertain),
            "match": actual_uncertain == expected_uncertain,
        },
        "preserved": {
            "expected": sorted(expected_preserved),
            "actual": sorted(actual_preserved),
            "match": actual_preserved == expected_preserved,
        },
    }

    validation["passed"] = all(
        validation[key]["match"]
        for key in (
            "invalidated",
            "reevaluation",
            "uncertain",
            "preserved",
        )
    )

    retry_succeeded = bool(
        retry_result is not None
        and retry_result.get("environment_result", {}).get("success")
    )

    if retry_result is None:
        final_status = "recovery_failed"
    elif retry_succeeded:
        final_status = "recovered"
    else:
        final_status = "retry_failed"

    trace.append({
        "event": "ground_truth_validation",
        "passed": validation["passed"],
        "details": validation,
    })

    trace.append({
        "event": "experiment_completed",
        "final_status": final_status,
        "task_success": retry_succeeded,
        "ground_truth_validation_passed": validation["passed"],
    })

    return RuntimeExperimentResult(
        strategy="belief_graph_runtime",
        success=retry_succeeded,
        final_status=final_status,
        initial_api_call=initial_result,
        recovery_status=recovery_status,
        retry_result=retry_result,
        affected_nodes=sorted(actual_invalidated),
        preserved_nodes=sorted(actual_preserved),
        trace=trace,
        ground_truth_validation=validation,
    )


if __name__ == "__main__":
    import json

    result = run_belief_graph_runtime_experiment()

    print(json.dumps(asdict(result), indent=2, default=str))