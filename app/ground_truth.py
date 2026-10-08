from dataclasses import dataclass
from typing import FrozenSet, Mapping

from .models import DependencyType, NodeStatus, NodeType


@dataclass(frozen=True)
class GroundTruthNode:
    id: str
    node_type: NodeType


@dataclass(frozen=True)
class GroundTruthEdge:
    source: str
    target: str
    dependency_type: DependencyType


@dataclass(frozen=True)
class BenchmarkGroundTruth:
    scenario_id: str
    changed_node: str
    original_nodes: tuple[GroundTruthNode, ...]
    edges: tuple[GroundTruthEdge, ...]
    expected_invalidated: FrozenSet[str]
    expected_reevaluation: FrozenSet[str]
    expected_uncertain: FrozenSet[str]
    expected_preserved: FrozenSet[str]
    expected_stale_actions: FrozenSet[str] = frozenset()

    @property
    def original_node_ids(self) -> FrozenSet[str]:
        return frozenset(node.id for node in self.original_nodes)

    @property
    def unrelated_nodes(self) -> FrozenSet[str]:
        return self.expected_preserved

    @property
    def expected_impact(self) -> Mapping[str, NodeStatus]:
        return {
            **{node_id: NodeStatus.INVALID for node_id in self.expected_invalidated},
            **{node_id: NodeStatus.REQUIRES_REEVALUATION for node_id in self.expected_reevaluation},
            **{node_id: NodeStatus.UNCERTAIN for node_id in self.expected_uncertain},
        }

    def validate(self) -> None:
        original = self.original_node_ids
        expected = (
            self.expected_invalidated
            | self.expected_reevaluation
            | self.expected_uncertain
            | self.expected_preserved
        )
        if expected != original:
            raise ValueError(
                f"Ground truth for {self.scenario_id} does not partition "
                f"the original nodes: expected={sorted(expected)}, "
                f"original={sorted(original)}"
            )
        if self.changed_node not in original:
            raise ValueError(
                f"Changed node {self.changed_node!r} is not in the original node set."
            )
        if not self.expected_stale_actions.issubset(original):
            raise ValueError(
                f"Expected stale actions reference nodes outside the original "
                f"node set: {sorted(self.expected_stale_actions - original)}"
            )
        stale_action_ids = {
            node.id
            for node in self.original_nodes
            if node.node_type == NodeType.ACTION
        }
        if not self.expected_stale_actions.issubset(stale_action_ids):
            raise ValueError(
                f"Expected stale actions must be ACTION nodes: "
                f"{sorted(self.expected_stale_actions - stale_action_ids)}"
            )
        edge_nodes = {edge.source for edge in self.edges} | {edge.target for edge in self.edges}
        if not edge_nodes.issubset(original):
            raise ValueError(
                f"Ground-truth edges reference nodes outside the original node set: "
                f"{sorted(edge_nodes - original)}"
            )


SCENARIO_1_GROUND_TRUTH = BenchmarkGroundTruth(
    scenario_id="api_version_change_v1",
    changed_node="B1",
    original_nodes=(
        GroundTruthNode("B1", NodeType.BELIEF),
        GroundTruthNode("C1", NodeType.CONCLUSION),
        GroundTruthNode("P1", NodeType.PLAN),
        GroundTruthNode("A1", NodeType.ACTION),
        GroundTruthNode("C2", NodeType.CONCLUSION),
        GroundTruthNode("P2", NodeType.PLAN),
        GroundTruthNode("A2", NodeType.ACTION),
        GroundTruthNode("B3", NodeType.BELIEF),
        GroundTruthNode("C3", NodeType.CONCLUSION),
        GroundTruthNode("P3", NodeType.PLAN),
    ),
    edges=(
        GroundTruthEdge("B1", "C1", DependencyType.REQUIRES),
        GroundTruthEdge("C1", "P1", DependencyType.REQUIRES),
        GroundTruthEdge("P1", "A1", DependencyType.REQUIRES),
        GroundTruthEdge("C1", "C2", DependencyType.SUPPORTS),
        GroundTruthEdge("C2", "P2", DependencyType.REQUIRES),
        GroundTruthEdge("P2", "A2", DependencyType.REQUIRES),
        GroundTruthEdge("B3", "C3", DependencyType.REQUIRES),
        GroundTruthEdge("C3", "P3", DependencyType.REQUIRES),
    ),
    expected_invalidated=frozenset({"B1", "C1", "P1", "A1"}),
    expected_reevaluation=frozenset({"C2"}),
    expected_uncertain=frozenset(),
    expected_preserved=frozenset({"P2", "A2", "B3", "C3", "P3"}),
    expected_stale_actions=frozenset({"A1"}),
)


SCENARIO_2_GROUND_TRUTH = BenchmarkGroundTruth(
    scenario_id="multi_branch_belief_revision_v1",
    changed_node="B1",
    original_nodes=(
        GroundTruthNode("B1", NodeType.BELIEF),
        GroundTruthNode("C1", NodeType.CONCLUSION),
        GroundTruthNode("P1", NodeType.PLAN),
        GroundTruthNode("A1", NodeType.ACTION),
        GroundTruthNode("P2", NodeType.PLAN),
        GroundTruthNode("A2", NodeType.ACTION),
        GroundTruthNode("P3", NodeType.PLAN),
        GroundTruthNode("A3", NodeType.ACTION),
        GroundTruthNode("B4", NodeType.BELIEF),
        GroundTruthNode("C4", NodeType.CONCLUSION),
        GroundTruthNode("P4", NodeType.PLAN),
        GroundTruthNode("A4", NodeType.ACTION),
    ),
    edges=(
        GroundTruthEdge("B1", "C1", DependencyType.REQUIRES),
        GroundTruthEdge("C1", "P1", DependencyType.REQUIRES),
        GroundTruthEdge("P1", "A1", DependencyType.REQUIRES),
        GroundTruthEdge("C1", "P2", DependencyType.SUPPORTS),
        GroundTruthEdge("P2", "A2", DependencyType.REQUIRES),
        GroundTruthEdge("C1", "P3", DependencyType.CONTEXT),
        GroundTruthEdge("P3", "A3", DependencyType.REQUIRES),
        GroundTruthEdge("B4", "C4", DependencyType.REQUIRES),
        GroundTruthEdge("C4", "P4", DependencyType.REQUIRES),
        GroundTruthEdge("P4", "A4", DependencyType.REQUIRES),
    ),
    expected_invalidated=frozenset({"B1", "C1", "P1", "A1"}),
    expected_reevaluation=frozenset({"P2"}),
    expected_uncertain=frozenset({"P3"}),
    expected_preserved=frozenset({"A2", "A3", "B4", "C4", "P4", "A4"}),
    # Baseline has no dependency-aware state revision, so all three
    # actions downstream of the changed belief remain executable with
    # stale assumptions. This is distinct from the formal impact state:
    # A2/A3 are preserved by the selective-revision semantics but stale
    # for a blind baseline that does not revise downstream actions.
    expected_stale_actions=frozenset({"A1", "A2", "A3"}),
)


SCENARIO_1_GROUND_TRUTH.validate()
SCENARIO_2_GROUND_TRUTH.validate()

SCENARIO_3_GROUND_TRUTH = BenchmarkGroundTruth(
    scenario_id="database_schema_change_v1",
    changed_node="B1",
    original_nodes=(
        GroundTruthNode("B1", NodeType.BELIEF),
        GroundTruthNode("C1", NodeType.CONCLUSION),
        GroundTruthNode("P1", NodeType.PLAN),
        GroundTruthNode("A1", NodeType.ACTION),

        GroundTruthNode("B2", NodeType.BELIEF),
        GroundTruthNode("C2", NodeType.CONCLUSION),
        GroundTruthNode("P2", NodeType.PLAN),
        GroundTruthNode("A2", NodeType.ACTION),

        GroundTruthNode("B3", NodeType.BELIEF),
        GroundTruthNode("C3", NodeType.CONCLUSION),
        GroundTruthNode("P3", NodeType.PLAN),
        GroundTruthNode("A3", NodeType.ACTION),
    ),
    edges=(
        # Schema-dependent branch
        GroundTruthEdge("B1", "C1", DependencyType.REQUIRES),
        GroundTruthEdge("C1", "P1", DependencyType.REQUIRES),
        GroundTruthEdge("P1", "A1", DependencyType.REQUIRES),

        # Independent database branch
        GroundTruthEdge("B2", "C2", DependencyType.REQUIRES),
        GroundTruthEdge("C2", "P2", DependencyType.REQUIRES),
        GroundTruthEdge("P2", "A2", DependencyType.REQUIRES),

        # Unrelated authentication branch
        GroundTruthEdge("B3", "C3", DependencyType.REQUIRES),
        GroundTruthEdge("C3", "P3", DependencyType.REQUIRES),
        GroundTruthEdge("P3", "A3", DependencyType.REQUIRES),
    ),
    expected_invalidated=frozenset({
        "B1",
        "C1",
        "P1",
        "A1",
    }),
    expected_reevaluation=frozenset(),
    expected_uncertain=frozenset(),
    expected_preserved=frozenset({
        "B2",
        "C2",
        "P2",
        "A2",
        "B3",
        "C3",
        "P3",
        "A3",
    }),
    expected_stale_actions=frozenset({
        "A1",
    }),
)

SCENARIO_3_GROUND_TRUTH.validate()

SCENARIO_4_GROUND_TRUTH = BenchmarkGroundTruth(
    scenario_id="policy_change_v1",
    changed_node="B1",
    original_nodes=(
        GroundTruthNode("B1", NodeType.BELIEF),
        GroundTruthNode("C1", NodeType.CONCLUSION),
        GroundTruthNode("P1", NodeType.PLAN),
        GroundTruthNode("A1", NodeType.ACTION),
        GroundTruthNode("B2", NodeType.BELIEF),
        GroundTruthNode("C2", NodeType.CONCLUSION),
        GroundTruthNode("P2", NodeType.PLAN),
        GroundTruthNode("A2", NodeType.ACTION),
        GroundTruthNode("B3", NodeType.BELIEF),
        GroundTruthNode("C3", NodeType.CONCLUSION),
        GroundTruthNode("P3", NodeType.PLAN),
        GroundTruthNode("A3", NodeType.ACTION),
    ),
    edges=(
        GroundTruthEdge("B1", "C1", DependencyType.REQUIRES),
        GroundTruthEdge("C1", "P1", DependencyType.REQUIRES),
        GroundTruthEdge("P1", "A1", DependencyType.REQUIRES),
        GroundTruthEdge("B2", "C2", DependencyType.REQUIRES),
        GroundTruthEdge("C2", "P2", DependencyType.REQUIRES),
        GroundTruthEdge("P2", "A2", DependencyType.REQUIRES),
        GroundTruthEdge("B3", "C3", DependencyType.REQUIRES),
        GroundTruthEdge("C3", "P3", DependencyType.REQUIRES),
        GroundTruthEdge("P3", "A3", DependencyType.REQUIRES),
    ),
    expected_invalidated=frozenset({"B1", "C1", "P1", "A1"}),
    expected_reevaluation=frozenset(),
    expected_uncertain=frozenset(),
    expected_preserved=frozenset({
        "B2", "C2", "P2", "A2",
        "B3", "C3", "P3", "A3",
    }),
    expected_stale_actions=frozenset({"A1"}),
)
SCENARIO_4_GROUND_TRUTH.validate()
