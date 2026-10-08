from dataclasses import dataclass
from typing import FrozenSet

from .models import DependencyType, NodeType


@dataclass(frozen=True)
class InstanceNode:
    id: str
    node_type: NodeType


@dataclass(frozen=True)
class InstanceEdge:
    source: str
    target: str
    dependency_type: DependencyType


@dataclass(frozen=True)
class BenchmarkInstance:
    """
    Deterministic, strategy-independent benchmark instance.

    This layer describes the task structure and ground-truth impact
    separately from any strategy implementation.
    """

    instance_id: str
    seed: int
    changed_belief: str
    nodes: tuple[InstanceNode, ...]
    edges: tuple[InstanceEdge, ...]

    expected_invalidated: FrozenSet[str]
    expected_reevaluation: FrozenSet[str]
    expected_uncertain: FrozenSet[str]
    expected_preserved: FrozenSet[str]
    expected_stale_actions: FrozenSet[str]

    @property
    def node_ids(self) -> FrozenSet[str]:
        return frozenset(node.id for node in self.nodes)

    @property
    def action_ids(self) -> FrozenSet[str]:
        return frozenset(
            node.id for node in self.nodes
            if node.node_type == NodeType.ACTION
        )

    @property
    def affected_nodes(self) -> FrozenSet[str]:
        return (
            self.expected_invalidated
            | self.expected_reevaluation
            | self.expected_uncertain
        )

    def validate(self) -> None:
        node_ids = self.node_ids

        partitions = (
            self.expected_invalidated
            | self.expected_reevaluation
            | self.expected_uncertain
            | self.expected_preserved
        )

        if partitions != node_ids:
            raise ValueError(
                f"{self.instance_id}: expected state sets do not partition "
                f"the node set. missing={sorted(node_ids - partitions)}, "
                f"extra={sorted(partitions - node_ids)}"
            )

        if self.changed_belief not in node_ids:
            raise ValueError(
                f"{self.instance_id}: changed belief is not a node."
            )

        if not self.expected_stale_actions.issubset(self.action_ids):
            raise ValueError(
                f"{self.instance_id}: stale-action set contains non-action "
                f"or unknown nodes: "
                f"{sorted(self.expected_stale_actions - self.action_ids)}"
            )

        edge_nodes = {
            node
            for edge in self.edges
            for node in (edge.source, edge.target)
        }

        if not edge_nodes.issubset(node_ids):
            raise ValueError(
                f"{self.instance_id}: edges reference unknown nodes: "
                f"{sorted(edge_nodes - node_ids)}"
            )

        if self.expected_stale_actions & self.expected_preserved == frozenset():
            # Intentionally allowed:
            # an action can be preserved by state-aware propagation while
            # remaining stale for a blind strategy.
            pass


def generate_scenario2_instance(
    seed: int,
    *,
    support_branch: bool = True,
    context_branch: bool = True,
    unrelated_branch: bool = True,
) -> BenchmarkInstance:
    """
    Generate a deterministic Scenario-2 family member.

    The seed creates a stable ID namespace for the instance. Dependency
    semantics and expected state classifications remain explicit.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")

    suffix = f"S{seed:04d}"

    def nid(prefix: str) -> str:
        return f"{prefix}_{suffix}"

    changed_belief = nid("B1")

    nodes: list[InstanceNode] = [
        InstanceNode(changed_belief, NodeType.BELIEF),
    ]
    edges: list[InstanceEdge] = []

    c1, p1, a1 = nid("C1"), nid("P1"), nid("A1")

    nodes.extend(
        [
            InstanceNode(c1, NodeType.CONCLUSION),
            InstanceNode(p1, NodeType.PLAN),
            InstanceNode(a1, NodeType.ACTION),
        ]
    )
    edges.extend(
        [
            InstanceEdge(changed_belief, c1, DependencyType.REQUIRES),
            InstanceEdge(c1, p1, DependencyType.REQUIRES),
            InstanceEdge(p1, a1, DependencyType.REQUIRES),
        ]
    )

    expected_invalidated = {
        changed_belief,
        c1,
        p1,
        a1,
    }
    expected_reevaluation: set[str] = set()
    expected_uncertain: set[str] = set()
    expected_preserved: set[str] = set()

    # Support branch: C1 -> P2 -> A2.
    if support_branch:
        p2, a2 = nid("P2"), nid("A2")
        nodes.extend(
            [
                InstanceNode(p2, NodeType.PLAN),
                InstanceNode(a2, NodeType.ACTION),
            ]
        )
        edges.extend(
            [
                InstanceEdge(c1, p2, DependencyType.SUPPORTS),
                InstanceEdge(p2, a2, DependencyType.REQUIRES),
            ]
        )
        expected_reevaluation.add(p2)
        expected_preserved.add(a2)

    # Context branch: C1 -> P3 -> A3.
    if context_branch:
        p3, a3 = nid("P3"), nid("A3")
        nodes.extend(
            [
                InstanceNode(p3, NodeType.PLAN),
                InstanceNode(a3, NodeType.ACTION),
            ]
        )
        edges.extend(
            [
                InstanceEdge(c1, p3, DependencyType.CONTEXT),
                InstanceEdge(p3, a3, DependencyType.REQUIRES),
            ]
        )
        expected_uncertain.add(p3)
        expected_preserved.add(a3)

    # Completely unrelated branch.
    if unrelated_branch:
        b4, c4, p4, a4 = (
            nid("B4"),
            nid("C4"),
            nid("P4"),
            nid("A4"),
        )
        nodes.extend(
            [
                InstanceNode(b4, NodeType.BELIEF),
                InstanceNode(c4, NodeType.CONCLUSION),
                InstanceNode(p4, NodeType.PLAN),
                InstanceNode(a4, NodeType.ACTION),
            ]
        )
        edges.extend(
            [
                InstanceEdge(b4, c4, DependencyType.REQUIRES),
                InstanceEdge(c4, p4, DependencyType.REQUIRES),
                InstanceEdge(p4, a4, DependencyType.REQUIRES),
            ]
        )
        expected_preserved.update({b4, c4, p4, a4})

    # Blind-baseline stale actions are intentionally separate from the
    # formal impact-state partition.
    expected_stale_actions = {a1}
    if support_branch:
        expected_stale_actions.add(nid("A2"))
    if context_branch:
        expected_stale_actions.add(nid("A3"))

    instance = BenchmarkInstance(
        instance_id=f"scenario2_{suffix}",
        seed=seed,
        changed_belief=changed_belief,
        nodes=tuple(nodes),
        edges=tuple(edges),
        expected_invalidated=frozenset(expected_invalidated),
        expected_reevaluation=frozenset(expected_reevaluation),
        expected_uncertain=frozenset(expected_uncertain),
        expected_preserved=frozenset(expected_preserved),
        expected_stale_actions=frozenset(expected_stale_actions),
    )

    instance.validate()
    return instance
