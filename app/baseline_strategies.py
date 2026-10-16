from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


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


class NaiveBaseline:
    """
    Models a naive strategy that does not propagate changes
    through dependency relationships.

    Downstream nodes may therefore remain stale.
    """

    name = "naive"

    def evaluate(
        self,
        graph,
        changed_node: str,
        expected_affected=None,
    ) -> StrategyResult:

        if changed_node not in graph.graph:
            raise ValueError(
                f"Node '{changed_node}' does not exist in the graph."
            )

        all_nodes = set(graph.graph.nodes)

        expected = set(
            expected_affected
            if expected_affected is not None
            else all_nodes - {changed_node}
        )

        expected.discard(changed_node)

        # The naive strategy does not propagate invalidation.
        stale_nodes = expected & all_nodes

        return StrategyResult(
            strategy=self.name,
            changed_node=changed_node,
            affected_nodes=[],
            invalidated_nodes=[],
            preserved_nodes=sorted(all_nodes - {changed_node}),
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
        changed_node: str,
        expected_affected=None,
    ) -> StrategyResult:

        if changed_node not in graph.graph:
            raise ValueError(
                f"Node '{changed_node}' does not exist in the graph."
            )

        all_nodes = set(graph.graph.nodes)

        expected = set(
            expected_affected
            if expected_affected is not None
            else all_nodes
        )

        # Model a complete recomputation of the graph.
        recomputed_nodes = sorted(all_nodes)

        # Nodes outside the expected impact set represent
        # unnecessary recomputation for this scenario.
        unnecessary = all_nodes - expected

        return StrategyResult(
            strategy=self.name,
            changed_node=changed_node,
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
                "unnecessary_recomputation": sorted(unnecessary),
                "unnecessary_recomputation_count": len(unnecessary),
            },
        )


class BeliefGraphStrategy:
    """
    Uses the existing BeliefGraph propagation implementation
    to identify affected nodes selectively.
    """

    name = "belief_graph"

    def evaluate(
        self,
        graph,
        changed_node: str,
        expected_affected=None,
    ) -> StrategyResult:

        if changed_node not in graph.graph:
            raise ValueError(
                f"Node '{changed_node}' does not exist in the graph."
            )

        all_nodes = set(graph.graph.nodes)

        # IMPORTANT:
        # propagate_state_impact returns a dictionary:
        # {
        #     "C1": {
        #         "impact": NodeStatus.INVALID,
        #         "dependency_type": ...,
        #         "depth": 1,
        #         "source": "B1",
        #         "source_status": ...
        #     },
        #     ...
        # }
        #
        # It calculates impact but does not apply the changes.

        impact = graph.propagate_state_impact(
            changed_node,
            initial_status="invalid",
        )

        if not isinstance(impact, dict):
            raise TypeError(
                "Expected propagate_state_impact() to return a dict, "
                f"received {type(impact).__name__}."
            )

        # The dictionary keys are the affected downstream node IDs.
        downstream_affected = set(impact.keys())

        # Include the changed node in the complete impact set.
        affected = downstream_affected | {changed_node}

        # Preserve nodes outside the impact set.
        preserved = all_nodes - affected

        # Compare the calculated result against scenario ground truth.
        expected = set(
            expected_affected
            if expected_affected is not None
            else affected
        )

        false_positives = affected - expected
        false_negatives = expected - affected

        # The propagation result identifies predicted invalidations.
        # We do not apply them to the graph during this evaluation.
        invalidated = sorted(affected)

        # Extract the maximum propagation depth from the impact data.
        depths = [
            details.get("depth", 0)
            for details in impact.values()
            if isinstance(details, dict)
        ]

        max_depth = max(depths, default=0)

        return StrategyResult(
            strategy=self.name,
            changed_node=changed_node,
            affected_nodes=sorted(affected),
            invalidated_nodes=invalidated,
            preserved_nodes=sorted(preserved),
            recomputed_nodes=[],
            stale_nodes=[],
            operations=len(downstream_affected),
            success=not false_positives and not false_negatives,
            details={
                "dependency_tracking": True,
                "policy": "selective_dependency_aware_propagation",
                "downstream_affected_nodes": sorted(
                    downstream_affected
                ),
                "propagation_depth": max_depth,
                "unnecessary_invalidation": sorted(false_positives),
                "missed_affected_nodes": sorted(false_negatives),
                "unnecessary_invalidation_count": len(false_positives),
                "missed_affected_node_count": len(false_negatives),
                "impact_result": impact,
                "note": (
                    "This evaluates predicted impact without mutating "
                    "the graph. Actual recovery and execution must be "
                    "measured separately."
                ),
            },
        )