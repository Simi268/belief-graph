"""Deterministic semantic recomputation for BeliefGraph nodes.

This module deliberately requires explicit evaluators for conclusions/plans.
It never guesses domain meaning from a node's natural-language content.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Mapping

from .models import NodeType

Evaluator = Callable[[Any, Mapping[str, Any]], Any]


@dataclass
class RecomputeRecord:
    node_id: str
    previous_value: Any
    new_value: Any
    succeeded: bool
    duration_ms: float
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "succeeded": self.succeeded,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class SemanticRecomputer:
    """Compute registered graph nodes using their current predecessor values.

    Evaluator signature:
        evaluator(node, predecessor_values) -> computed value

    The evaluator is responsible for domain-specific semantics. The engine
    supplies predecessor values, records outcomes, and writes successful values
    back to node.value. BELIEF nodes are treated as source facts and are not
    recomputed.
    """

    def __init__(self, agent, evaluators: Mapping[str, Evaluator]):
        self.agent = agent
        self.evaluators = dict(evaluators)

    def __call__(self, node) -> dict[str, Any]:
        started = perf_counter()
        previous_value = node.value
        if node.node_type == NodeType.BELIEF:
            raise ValueError(f"Belief node {node.id!r} is a source fact, not a derived node.")
        evaluator = self.evaluators.get(node.id)
        if evaluator is None:
            raise KeyError(f"No semantic evaluator registered for node {node.id!r}.")

        predecessor_values: dict[str, Any] = {}
        for parent_id in self.agent.graph.graph.predecessors(node.id):
            attributes = self.agent.graph.graph.nodes[parent_id]
            parent = attributes.get("data")
            if parent is None:
                # Evidence/conflict identifiers may be graph entries but are
                # not typed BeliefNode instances.
                continue

            # Revision preserves historical graph edges. If an edge points to
            # a superseded belief, expose the latest belief version to the
            # evaluator instead of feeding it the stale value. The predecessor
            # key is the current belief ID, making the substitution explicit.
            seen_belief_ids = {parent.id}
            while parent.node_type == NodeType.BELIEF and parent.superseded_by:
                replacement_id = parent.superseded_by
                if replacement_id in seen_belief_ids:
                    raise ValueError(
                        f"Belief supersession cycle encountered at {replacement_id!r}."
                    )
                try:
                    replacement = self.agent.graph.get_node(replacement_id)
                except Exception as exc:
                    raise ValueError(
                        f"Superseded belief {parent.id!r} references missing replacement "
                        f"{replacement_id!r}."
                    ) from exc
                if replacement.node_type != NodeType.BELIEF:
                    raise ValueError(
                        f"Replacement {replacement_id!r} for belief {parent.id!r} "
                        "is not a belief node."
                    )
                seen_belief_ids.add(replacement_id)
                parent = replacement

            predecessor_values[parent.id] = parent.value

        try:
            new_value = evaluator(node, predecessor_values)
            node.value = new_value
            return {
                "node_id": node.id,
                "previous_value": previous_value,
                "new_value": new_value,
                "predecessor_values": predecessor_values,
                "succeeded": True,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            }
        except Exception as exc:
            raise RuntimeError(
                f"Semantic recomputation failed for node {node.id!r}: {exc}"
            ) from exc

    def recompute_nodes(self, node_ids: list[str]) -> dict[str, Any]:
        """Recompute an explicitly selected list in the supplied order."""
        records: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for node_id in node_ids:
            try:
                node = self.agent.graph.get_node(node_id)
                records.append(self(node))
            except Exception as exc:
                failures.append({"node_id": node_id, "error": str(exc)})
        return {
            "selected_node_ids": list(node_ids),
            "recomputed_node_ids": [item["node_id"] for item in records],
            "records": records,
            "failures": failures,
            "success": not failures,
        }
