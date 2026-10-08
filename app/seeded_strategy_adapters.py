from typing import Any

from .benchmark import BenchmarkResult
from .benchmark_instances import BenchmarkInstance
from .graph import BeliefGraph
from .models import BeliefNode, NodeStatus, NodeType
from .multiseed_benchmark import SeedResult


def _node_types(instance: BenchmarkInstance) -> dict[str, NodeType]:
    """Return node-type metadata without relying on ID naming conventions."""
    return {
        node.id: node.node_type
        for node in instance.nodes
    }


def _has_evidence(instance: BenchmarkInstance) -> bool:
    return bool(instance.evidence_ids)


def _select_highest_confidence_evidence(
    instance: BenchmarkInstance,
) -> str | None:
    if not instance.evidence_confidences:
        return None

    confidence_map = dict(instance.evidence_confidences)

    return max(
        confidence_map,
        key=confidence_map.get,
    )


def _evidence_metrics(
    instance: BenchmarkInstance,
    *,
    selected_evidence: str | None,
    revision_count: int,
) -> tuple[dict[str, float | int | bool], dict[str, Any]]:
    """
    Produce evidence-specific metrics only for evidence-driven instances.

    Non-evidence scenarios receive no additional metrics, preserving the
    existing experiment schema for Scenarios 1-4, 6, and 7.
    """
    if not _has_evidence(instance):
        return {}, {}

    expected = instance.expected_selected_evidence
    correct = selected_evidence == expected

    confidence_map = dict(instance.evidence_confidences)

    selected_confidence = (
        confidence_map.get(selected_evidence, 0.0)
        if selected_evidence is not None
        else 0.0
    )

    details = {
        "evidence_ids": list(instance.evidence_ids),
        "selected_evidence": selected_evidence,
        "expected_selected_evidence": expected,
        "rejected_evidence": sorted(
            instance.expected_rejected_evidence
        ),
        "selected_evidence_confidence": selected_confidence,
        "expected_revision_count": instance.expected_revision_count,
        "revision_count": revision_count,
    }

    metrics = {
        "evidence_selection_correct": correct,
        "selected_evidence_confidence": selected_confidence,
        "revision_count": revision_count,
    }

    return metrics, details


def run_seeded_baseline(instance: BenchmarkInstance) -> SeedResult:
    """
    Blind strategy: after the changed belief, every reachable task artifact
    remains stale because the strategy has no dependency-aware revision.
    """

    node_types = _node_types(instance)

    stale_nodes = set(instance.affected_nodes) - {
        instance.changed_belief
    }

    stale_actions = len(instance.expected_stale_actions)

    stale_plans = sum(
        1
        for node_id in stale_nodes
        if node_types[node_id] == NodeType.PLAN
    )

    # The blind baseline does not perform impact analysis or selective
    # recovery. Therefore its strategy-detected affected/preserved counts
    # are zero. Ground-truth impact/preservation is kept separately in
    # details so the benchmark does not accidentally credit the baseline
    # with dependency awareness it does not possess.
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
        "affected_node_count": 0,
        "invalidated_node_count": 0,
        "recomputed_node_count": 0,
        "unnecessary_recomputation": 0,
        "preserved_node_count": 0,
        "preservation_ratio": 0.0,
    }

    evidence_metrics, evidence_details = _evidence_metrics(
        instance,
        selected_evidence=None,
        revision_count=0,
    )
    metrics.update(evidence_metrics)

    details = {
        "changed_belief": instance.changed_belief,
        "stale_nodes": sorted(stale_nodes),
        "strategy_detected_affected_nodes": [],
        "ground_truth_affected_nodes": sorted(
            instance.affected_nodes
        ),
        "ground_truth_affected_node_count": len(
            instance.affected_nodes
        ),
        "ground_truth_preserved_nodes": sorted(
            instance.expected_preserved
        ),
        "ground_truth_preserved_node_count": len(
            instance.expected_preserved
        ),
        "dependency_tracking": False,
        "strategy_behavior": "leave_downstream_state_unchanged",
        "metric_note": (
            "Baseline does not perform dependency-aware impact "
            "analysis or selective recovery. Strategy-level affected "
            "and preserved counts therefore remain zero; the formal "
            "ground-truth regions are reported separately."
        ),
    }
    details.update(evidence_details)

    return SeedResult(
        seed=instance.seed,
        instance_id=instance.instance_id,
        strategy="baseline",
        metrics=metrics,
        details=details,
    )


def run_seeded_memory(instance: BenchmarkInstance) -> SeedResult:
    """
    Conventional-memory strategy: it can learn the changed fact but has no
    dependency graph, so recovery conservatively recomputes the whole task.

    For evidence-driven instances, memory resolves the evidence by selecting
    the highest-confidence item but still performs a full restart.
    """
    original_nodes = set(instance.node_ids)
    preserved_nodes = set()
    recomputed_nodes = original_nodes

    unnecessary_recomputation = len(
        recomputed_nodes
        & set(instance.expected_preserved)
    )

    selected_evidence = _select_highest_confidence_evidence(
        instance
    ) if _has_evidence(instance) else None

    evidence_metrics, evidence_details = _evidence_metrics(
        instance,
        selected_evidence=selected_evidence,
        revision_count=(
            1
            if _has_evidence(instance)
            and selected_evidence == instance.expected_selected_evidence
            else 0
        ),
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
    metrics.update(evidence_metrics)

    details = {
        "changed_belief": instance.changed_belief,
        "recomputed_nodes": sorted(recomputed_nodes),
        "preserved_nodes": [],
        "dependency_tracking": False,
        "recovery_policy": "full_restart",
    }
    details.update(evidence_details)

    return SeedResult(
        seed=instance.seed,
        instance_id=instance.instance_id,
        strategy="memory",
        metrics=metrics,
        details=details,
    )


def _build_graph(instance: BenchmarkInstance) -> BeliefGraph:
    graph = BeliefGraph()

    for node in instance.nodes:
        graph.add_node(
            BeliefNode(
                id=node.id,
                node_type=node.node_type,
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
    instance. Evidence-driven instances additionally perform the same
    highest-confidence arbitration before dependency propagation.
    """
    selected_evidence = (
        _select_highest_confidence_evidence(instance)
        if _has_evidence(instance)
        else None
    )

    revision_count = (
        1
        if (
            _has_evidence(instance)
            and selected_evidence
            == instance.expected_selected_evidence
        )
        else 0
    )

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

    actual_preserved = (
        set(instance.node_ids) - actual_affected
    )

    expected_success = (
        actual_invalidated
        == set(instance.expected_invalidated)
        and actual_reevaluation
        == set(instance.expected_reevaluation)
        and actual_uncertain
        == set(instance.expected_uncertain)
        and actual_preserved
        == set(instance.expected_preserved)
        and (
            not _has_evidence(instance)
            or selected_evidence
            == instance.expected_selected_evidence
        )
    )

    node_types = _node_types(instance)

    invalidated_plans = sum(
        1
        for node_id in actual_invalidated
        if node_types[node_id] == NodeType.PLAN
    )

    max_depth = max(
        (
            details["depth"]
            for details in impact.values()
            if isinstance(details, dict)
            and "depth" in details
        ),
        default=0,
    )

    evidence_metrics, evidence_details = _evidence_metrics(
        instance,
        selected_evidence=selected_evidence,
        revision_count=revision_count,
    )

    metrics = {
        "task_success": expected_success,
        "stale_actions": 0,
        "stale_plans": 0,
        "invalid_plans": invalidated_plans,
        "recovery_success": expected_success,
        "unnecessary_invalidation": len(
            set(instance.expected_preserved)
            - actual_preserved
        ),
        "propagation_depth": max_depth,
        "recovery_steps": 1,
        "tool_calls": 0,
        "affected_node_count": len(actual_affected),
        "invalidated_node_count": len(
            actual_invalidated
        ),
        "recomputed_node_count": 0,
        "unnecessary_recomputation": 0,
        "preserved_node_count": len(actual_preserved),
        "preservation_ratio": (
            len(actual_preserved)
            / len(instance.nodes)
        ),
    }
    metrics.update(evidence_metrics)

    details = {
        "changed_belief": instance.changed_belief,
        "affected_nodes": sorted(actual_affected),
        "invalidated_nodes": sorted(actual_invalidated),
        "reevaluation_nodes": sorted(actual_reevaluation),
        "uncertain_nodes": sorted(actual_uncertain),
        "preserved_nodes": sorted(actual_preserved),
        "expected_invalidated": sorted(
            instance.expected_invalidated
        ),
        "expected_reevaluation": sorted(
            instance.expected_reevaluation
        ),
        "expected_uncertain": sorted(
            instance.expected_uncertain
        ),
        "expected_preserved": sorted(
            instance.expected_preserved
        ),
        "direct_graph_execution": True,
    }
    details.update(evidence_details)

    return SeedResult(
        seed=instance.seed,
        instance_id=instance.instance_id,
        strategy="belief_graph",
        metrics=metrics,
        details=details,
    )


def seeded_strategy_evaluators():
    return {
        "baseline": run_seeded_baseline,
        "memory": run_seeded_memory,
        "belief_graph": run_seeded_belief_graph,
    }
