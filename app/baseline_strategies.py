from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StrategyResult:
    strategy: str
    changed_node: str
    affected_nodes: List[str] = field(default_factory=list)
    invalidated_nodes: List[str] = field(default_factory=list)
    preserved_nodes: List[str] = field(default_factory=list)
    recomputed_nodes: List[str] = field(default_factory=list)
    stale_nodes: List[str] = field(default_factory=list)
    operations: int = 0
    success: bool = True
    details: Dict[str, Any] = field(default_factory=dict)
    changed_nodes: List[str] = field(default_factory=list)


def _normalize_changed_nodes(
    graph,
    changed_node: Optional[str] = None,
    changed_nodes: Optional[List[str]] = None,
) -> List[str]:
    """Validate and normalize one or more changed root nodes."""

    if changed_nodes is None:
        if changed_node is None:
            raise ValueError(
                "Provide changed_node or changed_nodes."
            )

        roots = [changed_node]

    else:
        roots = list(dict.fromkeys(changed_nodes))

        if not roots:
            raise ValueError(
                "changed_nodes must contain at least one node."
            )

        if changed_node is not None and changed_node not in roots:
            raise ValueError(
                "changed_node must be included in changed_nodes "
                "when both arguments are provided."
            )

    missing = [
        node
        for node in roots
        if node not in graph.graph
    ]

    if missing:
        raise ValueError(
            f"Node(s) do not exist in the graph: {missing}"
        )

    return roots


class NaiveBaseline:
    """
    Models a strategy that does not propagate changes through
    dependency relationships.

    Downstream nodes may remain stale.
    """

    name = "naive"

    def evaluate(
        self,
        graph,
        changed_node: Optional[str] = None,
        expected_affected=None,
        changed_nodes: Optional[List[str]] = None,
    ) -> StrategyResult:

        roots = _normalize_changed_nodes(
            graph,
            changed_node,
            changed_nodes,
        )

        root_set = set(roots)
        all_nodes = set(graph.graph.nodes)

        expected = set(
            expected_affected
            if expected_affected is not None
            else all_nodes - root_set
        )

        expected.difference_update(root_set)

        stale_nodes = expected & all_nodes

        return StrategyResult(
            strategy=self.name,
            changed_node=roots[0],
            changed_nodes=roots,
            affected_nodes=[],
            invalidated_nodes=[],
            preserved_nodes=sorted(all_nodes - root_set),
            recomputed_nodes=[],
            stale_nodes=sorted(stale_nodes),
            operations=0,
            success=not stale_nodes,
            details={
                "dependency_tracking": False,
                "policy": "leave_downstream_state_unchanged",
                "stale_node_count": len(stale_nodes),
                "note": (
                    "This is a modeled baseline. Stale nodes are "
                    "inferred from the expected impact set; no real "
                    "agent action is executed."
                ),
            },
        )


class FullRecomputationBaseline:
    """
    Models a strategy that recomputes every graph node whenever
    a change occurs.
    """

    name = "full_recomputation"

    def evaluate(
        self,
        graph,
        changed_node: Optional[str] = None,
        expected_affected=None,
        changed_nodes: Optional[List[str]] = None,
    ) -> StrategyResult:

        roots = _normalize_changed_nodes(
            graph,
            changed_node,
            changed_nodes,
        )

        root_set = set(roots)
        all_nodes = set(graph.graph.nodes)

        expected = set(
            expected_affected
            if expected_affected is not None
            else all_nodes
        )

        recomputed_nodes = sorted(all_nodes)
        unnecessary = all_nodes - expected

        return StrategyResult(
            strategy=self.name,
            changed_node=roots[0],
            changed_nodes=roots,
            affected_nodes=sorted(expected),
            invalidated_nodes=[],
            preserved_nodes=[],
            recomputed_nodes=recomputed_nodes,
            stale_nodes=[],
            operations=len(recomputed_nodes),
            success=True,
            details={
                "dependency_tracking": False,
                "policy": "recompute_entire_graph",
                "changed_root_count": len(root_set),
                "unnecessary_recomputation": sorted(
                    unnecessary
                ),
                "unnecessary_recomputation_count": len(
                    unnecessary
                ),
            },
        )


class BeliefGraphStrategy:
    """
    Uses BeliefGraph propagation to predict affected nodes selectively.

    Supports multiple simultaneous changed roots.

    Shared downstream nodes are counted once, and causal attribution
    records the original changed roots whose propagation reaches
    each affected node.

    This strategy predicts impact. It does not mutate the graph or
    execute actual recovery or recomputation.
    """

    name = "belief_graph"

    def evaluate(
        self,
        graph,
        changed_node: Optional[str] = None,
        expected_affected=None,
        changed_nodes: Optional[List[str]] = None,
    ) -> StrategyResult:

        roots = _normalize_changed_nodes(
            graph,
            changed_node,
            changed_nodes,
        )

        root_set = set(roots)
        all_nodes = set(graph.graph.nodes)

        # Combined impact information across all changed roots.
        combined_impact = {}

        # Record which downstream nodes are reachable from each root.
        source_roots = {}

        # Correctly track original changed roots for every impacted node.
        causal_roots_by_node = {}

        # Propagate the impact of each changed root independently.
        for root in roots:

            impact = graph.propagate_state_impact(
                root,
                initial_status="invalid",
            )

            if not isinstance(impact, dict):
                raise TypeError(
                    "Expected propagate_state_impact() to return "
                    f"a dict, received {type(impact).__name__}."
                )

            source_roots[root] = sorted(impact.keys())

            for node_id, details in impact.items():

                # Record the original root responsible for reaching
                # this node. Do not infer root identity from "source",
                # because source may be an intermediate dependency.
                causal_roots_by_node.setdefault(
                    node_id,
                    set(),
                ).add(root)

                if node_id not in combined_impact:

                    # Copy dictionaries to avoid modifying the
                    # graph's original propagation result.
                    if isinstance(details, dict):
                        combined_impact[node_id] = dict(details)
                    else:
                        combined_impact[node_id] = details

                    continue

                existing = combined_impact[node_id]

                # Merge metadata for shared downstream nodes.
                if (
                    isinstance(existing, dict)
                    and isinstance(details, dict)
                ):

                    merged = dict(existing)

                    # Preserve the maximum observed propagation depth.
                    existing_depth = merged.get("depth", 0)
                    incoming_depth = details.get("depth", 0)

                    if (
                        isinstance(existing_depth, (int, float))
                        and isinstance(incoming_depth, (int, float))
                    ):
                        merged["depth"] = max(
                            existing_depth,
                            incoming_depth,
                        )

                    combined_impact[node_id] = merged

        # Apply authoritative causal-root attribution after all roots
        # have been processed. This avoids incorrectly including
        # intermediate nodes such as C1, C2, or P1 as changed roots.
        for node_id, details in combined_impact.items():

            if isinstance(details, dict):
                details["causal_roots"] = sorted(
                    causal_roots_by_node.get(
                        node_id,
                        set(),
                    )
                )

        # Include every changed root in the final affected set.
        downstream_affected = (
            set(combined_impact) - root_set
        )

        affected = downstream_affected | root_set

        # Nodes outside the affected set remain preserved.
        preserved = all_nodes - affected

        expected = set(
            expected_affected
            if expected_affected is not None
            else affected
        )

        # Compare predictions against the supplied ground truth.
        false_positives = affected - expected
        false_negatives = expected - affected

        # Calculate maximum observed propagation depth.
        depths = [
            details.get("depth", 0)
            for details in combined_impact.values()
            if isinstance(details, dict)
        ]

        max_depth = max(depths, default=0)

        return StrategyResult(
            strategy=self.name,
            changed_node=roots[0],
            changed_nodes=roots,
            affected_nodes=sorted(affected),
            invalidated_nodes=sorted(affected),
            preserved_nodes=sorted(preserved),
            recomputed_nodes=[],
            stale_nodes=[],
            operations=len(downstream_affected),
            success=(
                not false_positives
                and not false_negatives
            ),
            details={
                "dependency_tracking": True,
                "policy": "selective_dependency_aware_propagation",
                "changed_root_count": len(roots),
                "changed_roots": roots,
                "downstream_affected_nodes": sorted(
                    downstream_affected
                ),
                "propagation_depth": max_depth,
                "unnecessary_invalidation": sorted(
                    false_positives
                ),
                "missed_affected_nodes": sorted(
                    false_negatives
                ),
                "unnecessary_invalidation_count": len(
                    false_positives
                ),
                "missed_affected_node_count": len(
                    false_negatives
                ),
                "source_roots": source_roots,
                "impact_result": combined_impact,
                "note": (
                    "This evaluates predicted impact without mutating "
                    "the graph. Actual recovery and execution must be "
                    "measured separately."
                ),
            },
        )