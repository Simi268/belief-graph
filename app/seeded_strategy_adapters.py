from typing import Any

from .benchmark import BenchmarkResult
from .benchmark_instances import BenchmarkInstance
from .graph import BeliefGraph
from .models import BeliefNode, NodeStatus
from .multiseed_benchmark import SeedResult


def _prefix(node_id: str) -> str:
    return node_id.split("_", 1)[0]


def run_seeded_baseline(instance: BenchmarkInstance) -> SeedResult:
    """
    Blind strategy: after the changed belief, every reachable task artifact
    remains stale because the strategy has no dependency-aware revision.
    """
    stale_nodes = set(instance.affected_nodes) - {instance.changed_belief}
    stale_actions = len(instance.expected_stale_actions)
    stale_plans = sum(
        1
        for node_id in stale_nodes
        if _prefix(node_id).startswith("P")
    )

    metrics = {
        "task_success": False,
        "stale_actions": stale_actions,
        "stale_plans": stale_plans,
        "invalid_plans": 0,
        "recovery_success": False,
        "unnecessary_invalidation": 0,
        "propagation_depth": 0,
        "recovery_steps": 0,
        "tool_calls": 0,
        "affected_node_count": len(stale_nodes),
        "invalidated_node_count": 0,
        "recomputed_node_count": 0,
        "unnecessary_recomputation": 0,
        "preserved_node_count": len(instance.expected_preserved),
        "preservation_ratio": (
            len(instance.expected_preserved) / len(instance.nodes)
        ),
    }

    return SeedResult(
        seed=instance.seed,
        instance_id=instance.instance_id,
        strategy="baseline",
        metrics=metrics,
        details={
            "changed_belief": instance.changed_belief,
            "stale_nodes": sorted(stale_nodes),
            "dependency_tracking": False,
            "strategy_behavior": "leave_downstream_state_unchanged",
        },
    )


def run_seeded_memory(instance: BenchmarkInstance) -> SeedResult:
    """
    Conventional-memory strategy: it can learn the changed fact but has no
    dependency graph, so recovery conservatively recomputes the whole task.
    """
    original_nodes = set(instance.node_ids)
    preserved_nodes = set()
    recomputed_nodes = original_nodes

    unnecessary_recomputation = len(
        recomputed_nodes & set(instance.expected_preserved)
    )

    metrics = {
        "task_success": True,
        "stale_actions": 0,
        "stale_plans": 0,
        "invalid_plans": 0,
        "recovery_success": True,
        "unnecessary_invalidation": 0,
        "propagation_depth": 0,
        "recovery_steps": 2,
        "tool_calls": 3,
        "affected_node_count": len(recomputed_nodes),
        "invalidated_node_count": 0,
        "recomputed_node_count": len(recomputed_nodes),
        "unnecessary_recomputation": unnecessary_recomputation,
        "preserved_node_count": len(preserved_nodes),
        "preservation_ratio": 0.0,
    }

    return SeedResult(
        seed=instance.seed,
        instance_id=instance.instance_id,
        strategy="memory",
        metrics=metrics,
        details={
            "changed_belief": instance.changed_belief,
            "recomputed_nodes": sorted(recomputed_nodes),
            "preserved_nodes": [],
            "dependency_tracking": False,
            "recovery_policy": "full_restart",
        },
    )


def _build_graph(instance: BenchmarkInstance) -> BeliefGraph:
    graph = BeliefGraph()

    for node in instance.nodes:
        node_type = node.node_type
        graph.add_node(
            BeliefNode(
                id=node.id,
                node_type=node_type,
                content=f"Benchmark node {node.id}",
            )
        )

    for edge in instance.edges:
        graph.add_dependency(
            edge.source,
            edge.target,
            edge.dependency_type,
        )

    return graph


def run_seeded_belief_graph(instance: BenchmarkInstance) -> SeedResult:
    """
    Run the actual state-aware BeliefGraph propagation engine on a generated
    instance. The generated IDs and edges are used directly.
    """
    graph = _build_graph(instance)

    impact = graph.propagate_state_impact(
        instance.changed_belief,
        initial_status=NodeStatus.INVALID,
    )

    graph.apply_state_impact(impact)

    actual_invalidated = {
        instance.changed_belief,
        *(
            node_id
            for node_id, details in impact.items()
            if details["impact"] == NodeStatus.INVALID
        ),
    }

    actual_reevaluation = {
        node_id
        for node_id, details in impact.items()
        if details["impact"] == NodeStatus.REQUIRES_REEVALUATION
    }

    actual_uncertain = {
        node_id
        for node_id, details in impact.items()
        if details["impact"] == NodeStatus.UNCERTAIN
    }

    actual_affected = (
        actual_invalidated
        | actual_reevaluation
        | actual_uncertain
    )

    actual_preserved = set(instance.node_ids) - actual_affected

    expected_success = (
        actual_invalidated == set(instance.expected_invalidated)
        and actual_reevaluation == set(instance.expected_reevaluation)
        and actual_uncertain == set(instance.expected_uncertain)
        and actual_preserved == set(instance.expected_preserved)
    )

    invalidated_plans = sum(
        1
        for node_id in actual_invalidated
        if _prefix(node_id).startswith("P")
    )

    max_depth = max(
        (
            details["depth"]
            for details in impact.values()
            if isinstance(details, dict) and "depth" in details
        ),
        default=0,
    )

    metrics = {
        "task_success": expected_success,
        "stale_actions": 0,
        "stale_plans": 0,
        "invalid_plans": invalidated_plans,
        "recovery_success": expected_success,
        "unnecessary_invalidation": len(
            set(instance.expected_preserved) - actual_preserved
        ),
        "propagation_depth": max_depth,
        "recovery_steps": 1,
        "tool_calls": 0,
        "affected_node_count": len(actual_affected),
        "invalidated_node_count": len(actual_invalidated),
        "recomputed_node_count": 0,
        "unnecessary_recomputation": 0,
        "preserved_node_count": len(actual_preserved),
        "preservation_ratio": len(actual_preserved) / len(instance.nodes),
    }

    return SeedResult(
        seed=instance.seed,
        instance_id=instance.instance_id,
        strategy="belief_graph",
        metrics=metrics,
        details={
            "changed_belief": instance.changed_belief,
            "affected_nodes": sorted(actual_affected),
            "invalidated_nodes": sorted(actual_invalidated),
            "reevaluation_nodes": sorted(actual_reevaluation),
            "uncertain_nodes": sorted(actual_uncertain),
            "preserved_nodes": sorted(actual_preserved),
            "expected_invalidated": sorted(instance.expected_invalidated),
            "expected_reevaluation": sorted(instance.expected_reevaluation),
            "expected_uncertain": sorted(instance.expected_uncertain),
            "expected_preserved": sorted(instance.expected_preserved),
            "direct_graph_execution": True,
        },
    )


def seeded_strategy_evaluators():
    return {
        "baseline": run_seeded_baseline,
        "memory": run_seeded_memory,
        "belief_graph": run_seeded_belief_graph,
    }
