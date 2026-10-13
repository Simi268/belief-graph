"""Scenario 3: selective invalidation and independent-branch preservation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.agent import AgentRuntime
from app.benchmark_instances import generate_scenario3_instance
from app.models import DependencyType, NodeStatus, NodeType
from app.stale_action_detector import detect_stale_actions


@dataclass
class Scenario3Result:
    strategy: str
    instance_id: str
    success: bool
    invalidated_nodes: list[str]
    reevaluation_nodes: list[str]
    uncertain_nodes: list[str]
    preserved_nodes: list[str]
    stale_actions: list[str]
    validation: dict[str, Any]
    trace: list[dict[str, Any]]


def run_scenario3_runtime_experiment(
    seed: int = 1,
) -> Scenario3Result:
    """Validate selective invalidation against Scenario 3 ground truth."""

    instance = generate_scenario3_instance(seed=seed)
    runtime = AgentRuntime()
    trace: list[dict[str, Any]] = []

    # 1. Build the runtime graph from the benchmark nodes.
    for instance_node in instance.nodes:
        node_id = instance_node.id
        node_type = NodeType(instance_node.node_type.value)

        if node_type == NodeType.BELIEF:
            runtime.create_belief(
                belief_id=node_id,
                content=f"Benchmark belief: {node_id}",
                value="v1",
                source="scenario3_benchmark",
            )
        else:
            runtime.create_node(
                node_id=node_id,
                node_type=node_type,
                content=f"Benchmark {node_type.value}: {node_id}",
            )

    # 2. Add the benchmark's actual dependency edges.
    for edge in instance.edges:
        runtime.add_dependency(
            edge.source,
            edge.target,
            DependencyType(edge.dependency_type.value),
        )

    trace.append({
        "event": "benchmark_instance_created",
        "instance_id": instance.instance_id,
        "seed": seed,
        "node_count": len(instance.nodes),
        "edge_count": len(instance.edges),
        "changed_belief": instance.changed_belief,
    })

    # 3. Calculate the impact of invalidating the changed belief.
    impact = runtime.graph.propagate_state_impact(
        instance.changed_belief,
        initial_status=NodeStatus.INVALID,
    )

    # 4. Apply the calculated impact.
    runtime.graph.apply_state_impact(impact)

    # The root belief is also invalid.
    runtime.graph.get_node(
        instance.changed_belief
    ).status = NodeStatus.INVALID

    trace.append({
        "event": "state_impact_applied",
        "impacted_nodes": {
            node_id: {
                "status": details["impact"].value,
                "dependency_type": details["dependency_type"].value,
                "depth": details["depth"],
                "source": details["source"],
            }
            for node_id, details in impact.items()
        },
    })

    # 5. Inspect actual runtime states for original benchmark nodes.
    original_node_ids = {
        node.id for node in instance.nodes
    }

    actual_statuses = {
        node_id: runtime.graph.get_node(node_id).status.value
        for node_id in original_node_ids
    }

    invalidated = {
        node_id
        for node_id, status in actual_statuses.items()
        if status == NodeStatus.INVALID.value
    }

    reevaluation = {
        node_id
        for node_id, status in actual_statuses.items()
        if status == NodeStatus.REQUIRES_REEVALUATION.value
    }

    uncertain = {
        node_id
        for node_id, status in actual_statuses.items()
        if status == NodeStatus.UNCERTAIN.value
    }

    preserved = {
        node_id
        for node_id, status in actual_statuses.items()
        if status == NodeStatus.ACTIVE.value
    }

    # 6. Independently detect stale actions from the runtime graph.
    stale_actions = detect_stale_actions(runtime.graph)
    stale_actions &= original_node_ids

    # 7. Compare actual outcomes with benchmark expectations.
    expected = {
        "invalidated": set(instance.expected_invalidated),
        "reevaluation": set(instance.expected_reevaluation),
        "uncertain": set(instance.expected_uncertain),
        "preserved": set(instance.expected_preserved),
        "stale_actions": set(instance.expected_stale_actions),
    }

    actual = {
        "invalidated": invalidated,
        "reevaluation": reevaluation,
        "uncertain": uncertain,
        "preserved": preserved,
        "stale_actions": stale_actions,
    }

    validation: dict[str, Any] = {
        category: {
            "expected": sorted(expected[category]),
            "actual": sorted(actual[category]),
            "match": expected[category] == actual[category],
        }
        for category in expected
    }

    validation["passed"] = all(
        validation[category]["match"]
        for category in expected
    )

    trace.append({
        "event": "ground_truth_validation",
        "passed": validation["passed"],
        "details": validation,
    })

    # 8. Return a reproducible experiment result.
    return Scenario3Result(
        strategy="belief_graph_scenario3",
        instance_id=instance.instance_id,
        success=validation["passed"],
        invalidated_nodes=sorted(invalidated),
        reevaluation_nodes=sorted(reevaluation),
        uncertain_nodes=sorted(uncertain),
        preserved_nodes=sorted(preserved),
        stale_actions=sorted(stale_actions),
        validation=validation,
        trace=trace,
    )


if __name__ == "__main__":
    import json

    result = run_scenario3_runtime_experiment()

    print(
        json.dumps(
            asdict(result),
            indent=2,
            default=str,
        )
    )