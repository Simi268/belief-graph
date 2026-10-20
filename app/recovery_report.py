"""Human-readable recovery reports for BeliefGraph."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _get_list(data: Mapping[str, Any], *keys: str) -> list:
    """Return the first list found under the supplied keys."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _format_nodes(nodes: list) -> str:
    """Format node identifiers without assuming a particular node type."""
    if not nodes:
        return "None"

    return ", ".join(str(node) for node in nodes)


def _format_duration(value: Any) -> str:
    """Format a duration when it is available."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.3f} ms"

    return "Not available"


def format_recovery_report(result: Mapping[str, Any]) -> str:
    """Format an actual BeliefGraph recovery result for developers.

    The function is read-only: it does not execute recovery, modify graph
    nodes, or infer success from a planned recovery alone.
    """
    if not isinstance(result, Mapping):
        raise TypeError("result must be a mapping.")

    metrics = result.get("recovery_metrics")
    if not isinstance(metrics, Mapping):
        metrics = {}

    plan = result.get("recovery_plan")
    if not isinstance(plan, Mapping):
        plan = {}

    selective = result.get("selective_recovery")
    if not isinstance(selective, Mapping):
        selective = {}

    execution = result.get("execution")
    if not isinstance(execution, Mapping):
        execution = {}

    new_action = result.get("new_action")

    affected_nodes = _get_list(
        plan, "affected_nodes", "replan_nodes", "recovery_nodes"
    )
    invalidated_nodes = _get_list(plan, "invalidated_nodes")
    reevaluation_nodes = _get_list(plan, "reevaluation_nodes")
    uncertain_nodes = _get_list(plan, "uncertain_nodes")
    preserved_nodes = _get_list(plan, "preserved_nodes")

    recomputed_nodes = _get_list(
        selective, "recomputed_node_ids"
    )
    selectively_preserved = _get_list(
        selective, "preserved_node_ids"
    )
    failed_nodes = _get_list(selective, "failed_node_ids")
    skipped_nodes = _get_list(selective, "skipped_node_ids")

    lines = [
        "BELIEFGRAPH RECOVERY REPORT",
        "=" * 28,
        "",
        "RECOVERY",
        f"  Engine status: {result.get('status', 'Not available')}",
        (
            "  Selective recovery status: "
            f"{selective.get('status', 'Not executed')}"
        ),
        (
            "  Selective recovery executed: "
            f"{metrics.get('selective_recovery_executed', False)}"
        ),
        "",
        "IMPACT ANALYSIS",
        f"  Affected nodes: {_format_nodes(affected_nodes)}",
        f"  Invalidated nodes: {_format_nodes(invalidated_nodes)}",
        f"  Reevaluation nodes: {_format_nodes(reevaluation_nodes)}",
        f"  Uncertain nodes: {_format_nodes(uncertain_nodes)}",
        f"  Planned preserved nodes: {_format_nodes(preserved_nodes)}",
        "",
        "SELECTIVE RECOMPUTATION",
        f"  Recomputed nodes: {_format_nodes(recomputed_nodes)}",
        (
            "  Preserved nodes: "
            f"{_format_nodes(selectively_preserved or preserved_nodes)}"
        ),
        f"  Failed nodes: {_format_nodes(failed_nodes)}",
        f"  Skipped nodes: {_format_nodes(skipped_nodes)}",
        "",
        "REPLACEMENT ACTION",
    ]

    if isinstance(new_action, Mapping):
        lines.append(
            f"  New action: {new_action.get('id', new_action.get('action_id', 'Available'))}"
        )
    elif new_action is not None:
        lines.append(f"  New action: {new_action}")
    else:
        lines.append("  New action: Not available")

    if "success" in execution:
        lines.append(f"  Execution success: {execution['success']}")
    else:
        lines.append("  Execution success: Not available")

    lines.extend(
        [
            "",
            "METRICS",
            (
                "  Nodes affected: "
                f"{metrics.get('affected_node_count', 'Not available')}"
            ),
            (
                "  Nodes invalidated: "
                f"{metrics.get('invalidated_node_count', 'Not available')}"
            ),
            (
                "  Nodes requiring reevaluation: "
                f"{metrics.get('reevaluation_node_count', 'Not available')}"
            ),
            (
                "  Successful recomputations: "
                f"{metrics.get('successful_recomputations', 'Not available')}"
            ),
            (
                "  Failed recomputations: "
                f"{metrics.get('failed_recomputations', 'Not available')}"
            ),
            (
                "  Recovery duration: "
                f"{_format_duration(metrics.get('recovery_duration_ms'))}"
            ),
            (
                "  Selective recovery duration: "
                f"{_format_duration(metrics.get('selective_recovery_duration_ms'))}"
            ),
            "",
            "Note: Planned recovery, recomputation success, and replacement "
            "execution success are separate outcomes.",
        ]
    )

    return "\n".join(lines)