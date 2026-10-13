"""Resolve external commitments affected by belief-graph changes."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.commitments import CommitmentRegistry


@dataclass
class CommitmentDependencyReport:
    changed_node_ids: set[str]
    affected_node_ids: set[str] = field(default_factory=set)
    affected_commitment_ids: list[str] = field(default_factory=list)
    unaffected_commitment_ids: list[str] = field(default_factory=list)
    matched_origin_nodes: dict[str, list[str]] = field(default_factory=dict)


class CommitmentDependencyResolver:
    """Trace changed beliefs to commitments through graph dependencies."""

    def __init__(self, graph, registry: CommitmentRegistry):
        self.graph = graph
        self.registry = registry

    def resolve(
        self,
        changed_node_ids: set[str],
        *,
        include_changed_nodes: bool = True,
    ) -> CommitmentDependencyReport:
        if not changed_node_ids:
            raise ValueError("At least one changed node ID is required.")

        for node_id in changed_node_ids:
            if node_id not in self.graph.graph:
                raise ValueError(f"Unknown graph node: {node_id}")

        # Include all downstream nodes, regardless of dependency type.
        # This finds potentially affected commitments; it does not itself
        # decide whether a commitment should be invalidated.
        affected_nodes = set()

        for node_id in changed_node_ids:
            affected_nodes.update(
                self.graph.graph.nodes
            )

            affected_nodes.intersection_update(
                {node_id} | set(
                    __import__("networkx").descendants(
                        self.graph.graph,
                        node_id,
                    )
                )
            )

        if not include_changed_nodes:
            affected_nodes.difference_update(changed_node_ids)

        affected_commitments = []
        unaffected_commitments = []
        matched_origins = {}

        for commitment in self.registry.all():
            matching_origins = (
                commitment.originating_belief_ids & affected_nodes
            )

            if matching_origins:
                affected_commitments.append(
                    commitment.commitment_id
                )
                matched_origins[commitment.commitment_id] = sorted(
                    matching_origins
                )
            else:
                unaffected_commitments.append(
                    commitment.commitment_id
                )

        return CommitmentDependencyReport(
            changed_node_ids=set(changed_node_ids),
            affected_node_ids=affected_nodes,
            affected_commitment_ids=sorted(affected_commitments),
            unaffected_commitment_ids=sorted(unaffected_commitments),
            matched_origin_nodes=matched_origins,
        )