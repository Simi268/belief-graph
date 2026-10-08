from dataclasses import dataclass
from typing import Any, FrozenSet

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

    # Optional evidence metadata for evidence-driven benchmark families
    # such as Scenario 5. Existing scenarios keep these at their defaults.
    evidence_ids: tuple[str, ...] = ()
    evidence_confidences: tuple[tuple[str, float], ...] = ()
    expected_selected_evidence: str | None = None
    expected_rejected_evidence: FrozenSet[str] = frozenset()
    expected_revision_count: int = 0
    metadata: dict[str, Any] | None = None

    @property
    def node_ids(self) -> FrozenSet[str]:
        return frozenset(node.id for node in self.nodes)

    @property
    def action_ids(self) -> FrozenSet[str]:
        return frozenset(
            node.id
            for node in self.nodes
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

        # Intentionally allowed:
        # an action can be preserved by state-aware propagation while
        # remaining stale for a blind strategy.
        #
        # No additional validation is required here because the stale-action
        # partition is deliberately separate from the formal impact-state
        # partition.

        # Evidence metadata is optional. When present, validate it as a
        # strategy-independent part of the benchmark instance.
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError(
                f"{self.instance_id}: evidence IDs must be unique."
            )

        confidence_map = dict(self.evidence_confidences)

        if set(confidence_map) != set(self.evidence_ids):
            raise ValueError(
                f"{self.instance_id}: evidence confidence metadata must "
                "cover exactly the declared evidence IDs."
            )

        for evidence_id, confidence in confidence_map.items():
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(
                    f"{self.instance_id}: evidence confidence for "
                    f"{evidence_id!r} must be between 0 and 1."
                )

        if self.expected_selected_evidence is not None:
            if self.expected_selected_evidence not in self.evidence_ids:
                raise ValueError(
                    f"{self.instance_id}: expected selected evidence "
                    "is not a declared evidence ID."
                )

        if not self.expected_rejected_evidence.issubset(
            set(self.evidence_ids)
        ):
            raise ValueError(
                f"{self.instance_id}: rejected evidence contains unknown "
                f"IDs: {sorted(self.expected_rejected_evidence - set(self.evidence_ids))}"
            )

        if (
            self.expected_selected_evidence is not None
            and self.expected_selected_evidence
            in self.expected_rejected_evidence
        ):
            raise ValueError(
                f"{self.instance_id}: selected evidence cannot also be "
                "marked rejected."
            )

        if self.expected_revision_count < 0:
            raise ValueError(
                f"{self.instance_id}: expected_revision_count must "
                "be non-negative."
            )


def generate_scenario1_instance(
    seed: int,
    *,
    unrelated_branch_count: int | None = None,
) -> BenchmarkInstance:
    """
    Generate a deterministic Scenario-1 family member.

    Core hypothesis:
        B1 -> C1 -> P1 -> A1

    The changed belief represents an API-version assumption. The dependent
    chain is the true affected region. Independent branches are preserved.

    Seed variation changes only the amount of unrelated work, not the causal
    structure of the changed branch. This gives the experiment controlled
    variation without changing the benchmark hypothesis.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")

    if unrelated_branch_count is None:
        # Controlled topology variation across seeds:
        # 1, 2, or 3 independent branches.
        unrelated_branch_count = 1 + (seed % 3)

    if unrelated_branch_count < 0:
        raise ValueError(
            "unrelated_branch_count must be non-negative"
        )

    suffix = f"S{seed:04d}"

    def nid(prefix: str) -> str:
        return f"{prefix}_{suffix}"

    changed_belief = nid("B1")
    c1, p1, a1 = nid("C1"), nid("P1"), nid("A1")

    nodes: list[InstanceNode] = [
        InstanceNode(changed_belief, NodeType.BELIEF),
        InstanceNode(c1, NodeType.CONCLUSION),
        InstanceNode(p1, NodeType.PLAN),
        InstanceNode(a1, NodeType.ACTION),
    ]

    edges: list[InstanceEdge] = [
        InstanceEdge(
            changed_belief,
            c1,
            DependencyType.REQUIRES,
        ),
        InstanceEdge(
            c1,
            p1,
            DependencyType.REQUIRES,
        ),
        InstanceEdge(
            p1,
            a1,
            DependencyType.REQUIRES,
        ),
    ]

    expected_invalidated = {
        changed_belief,
        c1,
        p1,
        a1,
    }

    expected_reevaluation: set[str] = set()
    expected_uncertain: set[str] = set()
    expected_preserved: set[str] = set()

    # Independent work is deliberately structurally identical but
    # disconnected from the changed belief. The number of branches varies
    # by seed so multi-seed experiments do not merely rename node IDs.
    for branch_index in range(1, unrelated_branch_count + 1):
        b_id = nid(f"B{branch_index + 1}_U")
        c_id = nid(f"C{branch_index + 1}_U")
        p_id = nid(f"P{branch_index + 1}_U")
        a_id = nid(f"A{branch_index + 1}_U")

        nodes.extend(
            [
                InstanceNode(b_id, NodeType.BELIEF),
                InstanceNode(c_id, NodeType.CONCLUSION),
                InstanceNode(p_id, NodeType.PLAN),
                InstanceNode(a_id, NodeType.ACTION),
            ]
        )

        edges.extend(
            [
                InstanceEdge(
                    b_id,
                    c_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    c_id,
                    p_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    p_id,
                    a_id,
                    DependencyType.REQUIRES,
                ),
            ]
        )

        expected_preserved.update(
            {
                b_id,
                c_id,
                p_id,
                a_id,
            }
        )

    instance = BenchmarkInstance(
        instance_id=f"scenario1_{suffix}",
        seed=seed,
        changed_belief=changed_belief,
        nodes=tuple(nodes),
        edges=tuple(edges),
        expected_invalidated=frozenset(
            expected_invalidated
        ),
        expected_reevaluation=frozenset(
            expected_reevaluation
        ),
        expected_uncertain=frozenset(
            expected_uncertain
        ),
        expected_preserved=frozenset(
            expected_preserved
        ),
        expected_stale_actions=frozenset({a1}),
    )

    instance.validate()
    return instance


def generate_scenario3_instance(
    seed: int,
    *,
    extra_unrelated_branches: int | None = None,
) -> BenchmarkInstance:
    """
    Generate a deterministic Scenario-3 family member.

    Core hypothesis:
        A schema-dependent database reasoning chain becomes invalid when
        its assumed schema changes, while independent database work and
        unrelated work remain valid.

    Fixed branches:
        B1 -> C1 -> P1 -> A1   (schema-dependent; affected)
        B2 -> C2 -> P2 -> A2   (independent DB branch; preserved)
        B3 -> C3 -> P3 -> A3   (unrelated/auth branch; preserved)

    Seed variation adds extra unrelated branches. The changed branch and
    its semantics remain fixed so the experiment still tests the same
    causal question across instances.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")

    if extra_unrelated_branches is None:
        extra_unrelated_branches = seed % 3

    if extra_unrelated_branches < 0:
        raise ValueError(
            "extra_unrelated_branches must be non-negative"
        )

    suffix = f"S{seed:04d}"

    def nid(prefix: str) -> str:
        return f"{prefix}_{suffix}"

    nodes: list[InstanceNode] = []
    edges: list[InstanceEdge] = []

    expected_invalidated: set[str] = set()
    expected_reevaluation: set[str] = set()
    expected_uncertain: set[str] = set()
    expected_preserved: set[str] = set()

    def add_requires_chain(
        belief_id: str,
        conclusion_id: str,
        plan_id: str,
        action_id: str,
    ) -> None:
        nodes.extend(
            [
                InstanceNode(belief_id, NodeType.BELIEF),
                InstanceNode(conclusion_id, NodeType.CONCLUSION),
                InstanceNode(plan_id, NodeType.PLAN),
                InstanceNode(action_id, NodeType.ACTION),
            ]
        )
        edges.extend(
            [
                InstanceEdge(
                    belief_id,
                    conclusion_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    conclusion_id,
                    plan_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    plan_id,
                    action_id,
                    DependencyType.REQUIRES,
                ),
            ]
        )

    # ---------------------------------------------------------
    # Affected schema-dependent branch
    # ---------------------------------------------------------

    b1, c1, p1, a1 = (
        nid("B1"),
        nid("C1"),
        nid("P1"),
        nid("A1"),
    )

    add_requires_chain(b1, c1, p1, a1)

    expected_invalidated.update(
        {
            b1,
            c1,
            p1,
            a1,
        }
    )

    # ---------------------------------------------------------
    # Independent database branch
    # ---------------------------------------------------------

    b2, c2, p2, a2 = (
        nid("B2"),
        nid("C2"),
        nid("P2"),
        nid("A2"),
    )

    add_requires_chain(b2, c2, p2, a2)

    expected_preserved.update(
        {
            b2,
            c2,
            p2,
            a2,
        }
    )

    # ---------------------------------------------------------
    # Unrelated/authentication branch
    # ---------------------------------------------------------

    b3, c3, p3, a3 = (
        nid("B3"),
        nid("C3"),
        nid("P3"),
        nid("A3"),
    )

    add_requires_chain(b3, c3, p3, a3)

    expected_preserved.update(
        {
            b3,
            c3,
            p3,
            a3,
        }
    )

    # ---------------------------------------------------------
    # Controlled seed variation: extra unrelated work
    # ---------------------------------------------------------

    for branch_index in range(
        1,
        extra_unrelated_branches + 1,
    ):
        branch_number = branch_index + 3

        b_id = nid(f"B{branch_number}_U")
        c_id = nid(f"C{branch_number}_U")
        p_id = nid(f"P{branch_number}_U")
        a_id = nid(f"A{branch_number}_U")

        add_requires_chain(
            b_id,
            c_id,
            p_id,
            a_id,
        )

        expected_preserved.update(
            {
                b_id,
                c_id,
                p_id,
                a_id,
            }
        )

    instance = BenchmarkInstance(
        instance_id=f"scenario3_{suffix}",
        seed=seed,
        changed_belief=b1,
        nodes=tuple(nodes),
        edges=tuple(edges),
        expected_invalidated=frozenset(
            expected_invalidated
        ),
        expected_reevaluation=frozenset(
            expected_reevaluation
        ),
        expected_uncertain=frozenset(
            expected_uncertain
        ),
        expected_preserved=frozenset(
            expected_preserved
        ),
        expected_stale_actions=frozenset({a1}),
    )

    instance.validate()
    return instance


def generate_scenario4_instance(
    seed: int,
    *,
    extra_unrelated_branches: int | None = None,
) -> BenchmarkInstance:
    """
    Generate a deterministic Scenario-4 family member.

    Core hypothesis:
        A policy belief changes, invalidating the reasoning chain that
        depended on the old policy while preserving independent work.

    Fixed affected branch:
        B1 -> C1 -> P1 -> A1

    Fixed preserved branches:
        B2 -> C2 -> P2 -> A2
        B3 -> C3 -> P3 -> A3

    The experiment varies only the amount of disconnected work. This keeps
    the policy-change hypothesis constant while testing whether selective
    invalidation remains precise as unrelated state grows.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")

    if extra_unrelated_branches is None:
        # Different deterministic variation from Scenario 3 so that the
        # scenario families do not all use the same topology schedule.
        extra_unrelated_branches = (seed + 1) % 3

    if extra_unrelated_branches < 0:
        raise ValueError(
            "extra_unrelated_branches must be non-negative"
        )

    suffix = f"S{seed:04d}"

    def nid(prefix: str) -> str:
        return f"{prefix}_{suffix}"

    nodes: list[InstanceNode] = []
    edges: list[InstanceEdge] = []

    expected_invalidated: set[str] = set()
    expected_reevaluation: set[str] = set()
    expected_uncertain: set[str] = set()
    expected_preserved: set[str] = set()

    def add_requires_chain(
        belief_id: str,
        conclusion_id: str,
        plan_id: str,
        action_id: str,
    ) -> None:
        nodes.extend(
            [
                InstanceNode(
                    belief_id,
                    NodeType.BELIEF,
                ),
                InstanceNode(
                    conclusion_id,
                    NodeType.CONCLUSION,
                ),
                InstanceNode(
                    plan_id,
                    NodeType.PLAN,
                ),
                InstanceNode(
                    action_id,
                    NodeType.ACTION,
                ),
            ]
        )

        edges.extend(
            [
                InstanceEdge(
                    belief_id,
                    conclusion_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    conclusion_id,
                    plan_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    plan_id,
                    action_id,
                    DependencyType.REQUIRES,
                ),
            ]
        )

    # ---------------------------------------------------------
    # Affected policy-dependent branch
    # ---------------------------------------------------------

    b1, c1, p1, a1 = (
        nid("B1"),
        nid("C1"),
        nid("P1"),
        nid("A1"),
    )

    add_requires_chain(
        b1,
        c1,
        p1,
        a1,
    )

    expected_invalidated.update(
        {
            b1,
            c1,
            p1,
            a1,
        }
    )

    # ---------------------------------------------------------
    # Independent supporting work
    # ---------------------------------------------------------

    b2, c2, p2, a2 = (
        nid("B2"),
        nid("C2"),
        nid("P2"),
        nid("A2"),
    )

    add_requires_chain(
        b2,
        c2,
        p2,
        a2,
    )

    expected_preserved.update(
        {
            b2,
            c2,
            p2,
            a2,
        }
    )

    # ---------------------------------------------------------
    # Unrelated analytics work
    # ---------------------------------------------------------

    b3, c3, p3, a3 = (
        nid("B3"),
        nid("C3"),
        nid("P3"),
        nid("A3"),
    )

    add_requires_chain(
        b3,
        c3,
        p3,
        a3,
    )

    expected_preserved.update(
        {
            b3,
            c3,
            p3,
            a3,
        }
    )

    # ---------------------------------------------------------
    # Controlled seed variation: additional unrelated policy
    # consumers
    # ---------------------------------------------------------

    for branch_index in range(
        1,
        extra_unrelated_branches + 1,
    ):
        branch_number = branch_index + 3

        b_id = nid(f"B{branch_number}_U")
        c_id = nid(f"C{branch_number}_U")
        p_id = nid(f"P{branch_number}_U")
        a_id = nid(f"A{branch_number}_U")

        add_requires_chain(
            b_id,
            c_id,
            p_id,
            a_id,
        )

        expected_preserved.update(
            {
                b_id,
                c_id,
                p_id,
                a_id,
            }
        )

    instance = BenchmarkInstance(
        instance_id=f"scenario4_{suffix}",
        seed=seed,
        changed_belief=b1,
        nodes=tuple(nodes),
        edges=tuple(edges),
        expected_invalidated=frozenset(
            expected_invalidated
        ),
        expected_reevaluation=frozenset(
            expected_reevaluation
        ),
        expected_uncertain=frozenset(
            expected_uncertain
        ),
        expected_preserved=frozenset(
            expected_preserved
        ),
        expected_stale_actions=frozenset({a1}),
    )

    instance.validate()
    return instance


def generate_scenario5_instance(
    seed: int,
) -> BenchmarkInstance:
    """
    Generate a deterministic Scenario-5 contradictory-evidence instance.

    Two pieces of evidence concern the same belief:
        E1 = weaker / rejected evidence
        E2 = stronger / selected evidence

    The dependency graph remains:

        B1 -> C1 -> P1 -> A1
        B2 -> C2 -> P2 -> A2

    Only the B1 branch is affected after the stronger evidence is selected.
    Seed variation changes confidence values while preserving the ordering
    E2 > E1, so the evidence-arbitration hypothesis remains constant.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")

    suffix = f"S{seed:04d}"

    def nid(prefix: str) -> str:
        return f"{prefix}_{suffix}"

    changed_belief = nid("B1")

    b2, c2, p2, a2 = (
        nid("B2"),
        nid("C2"),
        nid("P2"),
        nid("A2"),
    )

    c1, p1, a1 = nid("C1"), nid("P1"), nid("A1")

    nodes = (
        InstanceNode(changed_belief, NodeType.BELIEF),
        InstanceNode(c1, NodeType.CONCLUSION),
        InstanceNode(p1, NodeType.PLAN),
        InstanceNode(a1, NodeType.ACTION),
        InstanceNode(b2, NodeType.BELIEF),
        InstanceNode(c2, NodeType.CONCLUSION),
        InstanceNode(p2, NodeType.PLAN),
        InstanceNode(a2, NodeType.ACTION),
    )

    edges = (
        InstanceEdge(
            changed_belief,
            c1,
            DependencyType.REQUIRES,
        ),
        InstanceEdge(
            c1,
            p1,
            DependencyType.REQUIRES,
        ),
        InstanceEdge(
            p1,
            a1,
            DependencyType.REQUIRES,
        ),
        InstanceEdge(
            b2,
            c2,
            DependencyType.REQUIRES,
        ),
        InstanceEdge(
            c2,
            p2,
            DependencyType.REQUIRES,
        ),
        InstanceEdge(
            p2,
            a2,
            DependencyType.REQUIRES,
        ),
    )

    # Deterministic confidence variation, preserving the ordering:
    # weak evidence < initial belief confidence < strong evidence.
    weak_confidence = 0.60 + 0.03 * (seed % 5)
    strong_confidence = 0.90 + 0.01 * (seed % 5)

    weak_evidence_id = nid("E1")
    strong_evidence_id = nid("E2")

    instance = BenchmarkInstance(
        instance_id=f"scenario5_{suffix}",
        seed=seed,
        changed_belief=changed_belief,
        nodes=nodes,
        edges=edges,
        expected_invalidated=frozenset(
            {
                changed_belief,
                c1,
                p1,
                a1,
            }
        ),
        expected_reevaluation=frozenset(),
        expected_uncertain=frozenset(),
        expected_preserved=frozenset(
            {
                b2,
                c2,
                p2,
                a2,
            }
        ),
        expected_stale_actions=frozenset({a1}),
        evidence_ids=(
            weak_evidence_id,
            strong_evidence_id,
        ),
        evidence_confidences=(
            (
                weak_evidence_id,
                weak_confidence,
            ),
            (
                strong_evidence_id,
                strong_confidence,
            ),
        ),
        expected_selected_evidence=strong_evidence_id,
        expected_rejected_evidence=frozenset(
            {weak_evidence_id}
        ),
        expected_revision_count=1,
        metadata={
            "scenario_type": "contradictory_evidence_v1",
            "belief_confidence": 0.85,
            "weak_evidence_id": weak_evidence_id,
            "strong_evidence_id": strong_evidence_id,
            "evidence_arbitration_policy": "highest_confidence",
        },
    )

    instance.validate()
    return instance


def generate_scenario6_instance(
    seed: int,
    *,
    extra_independent_branches: int | None = None,
) -> BenchmarkInstance:
    """
    Generate a deterministic Scenario-6 family member.

    Core hypothesis:
        A required tool becomes unavailable. Belief-Graph should invalidate
        only the reasoning chain that depends on that tool while preserving
        independent work.

    Fixed affected branch:
        B1 -> C1 -> P1 -> A1

    Fixed preserved branch:
        B2 -> C2 -> P2 -> A2

    Seed variation adds disconnected independent work without changing the
    tool-failure dependency chain.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")

    if extra_independent_branches is None:
        extra_independent_branches = seed % 3

    if extra_independent_branches < 0:
        raise ValueError(
            "extra_independent_branches must be non-negative"
        )

    suffix = f"S{seed:04d}"

    def nid(prefix: str) -> str:
        return f"{prefix}_{suffix}"

    nodes: list[InstanceNode] = []
    edges: list[InstanceEdge] = []

    expected_invalidated: set[str] = set()
    expected_reevaluation: set[str] = set()
    expected_uncertain: set[str] = set()
    expected_preserved: set[str] = set()

    def add_requires_chain(
        belief_id: str,
        conclusion_id: str,
        plan_id: str,
        action_id: str,
    ) -> None:
        nodes.extend(
            [
                InstanceNode(
                    belief_id,
                    NodeType.BELIEF,
                ),
                InstanceNode(
                    conclusion_id,
                    NodeType.CONCLUSION,
                ),
                InstanceNode(
                    plan_id,
                    NodeType.PLAN,
                ),
                InstanceNode(
                    action_id,
                    NodeType.ACTION,
                ),
            ]
        )

        edges.extend(
            [
                InstanceEdge(
                    belief_id,
                    conclusion_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    conclusion_id,
                    plan_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    plan_id,
                    action_id,
                    DependencyType.REQUIRES,
                ),
            ]
        )

    # ---------------------------------------------------------
    # Affected tool-dependent branch
    # ---------------------------------------------------------

    b1, c1, p1, a1 = (
        nid("B1"),
        nid("C1"),
        nid("P1"),
        nid("A1"),
    )

    add_requires_chain(
        b1,
        c1,
        p1,
        a1,
    )

    expected_invalidated.update(
        {
            b1,
            c1,
            p1,
            a1,
        }
    )

    # ---------------------------------------------------------
    # Fixed independent branch
    # ---------------------------------------------------------

    b2, c2, p2, a2 = (
        nid("B2"),
        nid("C2"),
        nid("P2"),
        nid("A2"),
    )

    add_requires_chain(
        b2,
        c2,
        p2,
        a2,
    )

    expected_preserved.update(
        {
            b2,
            c2,
            p2,
            a2,
        }
    )

    # ---------------------------------------------------------
    # Controlled seed variation: more independent work
    # ---------------------------------------------------------

    for branch_index in range(
        1,
        extra_independent_branches + 1,
    ):
        branch_number = branch_index + 2

        b_id = nid(f"B{branch_number}_U")
        c_id = nid(f"C{branch_number}_U")
        p_id = nid(f"P{branch_number}_U")
        a_id = nid(f"A{branch_number}_U")

        add_requires_chain(
            b_id,
            c_id,
            p_id,
            a_id,
        )

        expected_preserved.update(
            {
                b_id,
                c_id,
                p_id,
                a_id,
            }
        )

    instance = BenchmarkInstance(
        instance_id=f"scenario6_{suffix}",
        seed=seed,
        changed_belief=b1,
        nodes=tuple(nodes),
        edges=tuple(edges),
        expected_invalidated=frozenset(
            expected_invalidated
        ),
        expected_reevaluation=frozenset(
            expected_reevaluation
        ),
        expected_uncertain=frozenset(
            expected_uncertain
        ),
        expected_preserved=frozenset(
            expected_preserved
        ),
        expected_stale_actions=frozenset({a1}),
        metadata={
            "scenario_type": "tool_unavailable_v1",
            "tool_id": "T1",
            "tool_available_before": True,
            "tool_available_after": False,
            "failure_mode": "required_tool_unavailable",
        },
    )

    instance.validate()
    return instance


def generate_scenario7_instance(
    seed: int,
    *,
    extra_unrelated_branches: int | None = None,
) -> BenchmarkInstance:
    """
    Generate a deterministic Scenario-7 family member.

    Core hypothesis:
        Information used by an agent becomes stale. Belief-Graph should
        invalidate the reasoning chain that depended on the stale belief
        while preserving unrelated work.

    Fixed affected branch:
        B1 -> C1 -> P1 -> A1

    Fixed preserved branch:
        B2 -> C2 -> P2 -> A2

    Seed variation adds disconnected unrelated work. The stale-information
    condition itself remains fixed across seeds.
    """

    if seed < 0:
        raise ValueError("seed must be non-negative")

    if extra_unrelated_branches is None:
        extra_unrelated_branches = (seed + 2) % 3

    if extra_unrelated_branches < 0:
        raise ValueError(
            "extra_unrelated_branches must be non-negative"
        )

    suffix = f"S{seed:04d}"

    def nid(prefix: str) -> str:
        return f"{prefix}_{suffix}"

    nodes: list[InstanceNode] = []
    edges: list[InstanceEdge] = []

    expected_invalidated: set[str] = set()
    expected_reevaluation: set[str] = set()
    expected_uncertain: set[str] = set()
    expected_preserved: set[str] = set()

    def add_requires_chain(
        belief_id: str,
        conclusion_id: str,
        plan_id: str,
        action_id: str,
    ) -> None:
        nodes.extend(
            [
                InstanceNode(
                    belief_id,
                    NodeType.BELIEF,
                ),
                InstanceNode(
                    conclusion_id,
                    NodeType.CONCLUSION,
                ),
                InstanceNode(
                    plan_id,
                    NodeType.PLAN,
                ),
                InstanceNode(
                    action_id,
                    NodeType.ACTION,
                ),
            ]
        )

        edges.extend(
            [
                InstanceEdge(
                    belief_id,
                    conclusion_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    conclusion_id,
                    plan_id,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    plan_id,
                    action_id,
                    DependencyType.REQUIRES,
                ),
            ]
        )

    # ---------------------------------------------------------
    # Affected stale-information branch
    # ---------------------------------------------------------

    b1, c1, p1, a1 = (
        nid("B1"),
        nid("C1"),
        nid("P1"),
        nid("A1"),
    )

    add_requires_chain(
        b1,
        c1,
        p1,
        a1,
    )

    expected_invalidated.update(
        {
            b1,
            c1,
            p1,
            a1,
        }
    )

    # ---------------------------------------------------------
    # Fixed independent branch
    # ---------------------------------------------------------

    b2, c2, p2, a2 = (
        nid("B2"),
        nid("C2"),
        nid("P2"),
        nid("A2"),
    )

    add_requires_chain(
        b2,
        c2,
        p2,
        a2,
    )

    expected_preserved.update(
        {
            b2,
            c2,
            p2,
            a2,
        }
    )

    # ---------------------------------------------------------
    # Controlled seed variation: extra unrelated work
    # ---------------------------------------------------------

    for branch_index in range(
        1,
        extra_unrelated_branches + 1,
    ):
        branch_number = branch_index + 2

        b_id = nid(f"B{branch_number}_U")
        c_id = nid(f"C{branch_number}_U")
        p_id = nid(f"P{branch_number}_U")
        a_id = nid(f"A{branch_number}_U")

        add_requires_chain(
            b_id,
            c_id,
            p_id,
            a_id,
        )

        expected_preserved.update(
            {
                b_id,
                c_id,
                p_id,
                a_id,
            }
        )

    instance = BenchmarkInstance(
        instance_id=f"scenario7_{suffix}",
        seed=seed,
        changed_belief=b1,
        nodes=tuple(nodes),
        edges=tuple(edges),
        expected_invalidated=frozenset(
            expected_invalidated
        ),
        expected_reevaluation=frozenset(
            expected_reevaluation
        ),
        expected_uncertain=frozenset(
            expected_uncertain
        ),
        expected_preserved=frozenset(
            expected_preserved
        ),
        expected_stale_actions=frozenset({a1}),
        metadata={
            "scenario_type": "stale_information_v1",
            "information_source": "documentation-v1",
            "information_was_fresh": True,
            "information_is_stale": True,
            "replacement_source": "documentation-v2",
            "failure_mode": "superseded_information",
        },
    )

    instance.validate()
    return instance


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
            InstanceEdge(
                changed_belief,
                c1,
                DependencyType.REQUIRES,
            ),
            InstanceEdge(
                c1,
                p1,
                DependencyType.REQUIRES,
            ),
            InstanceEdge(
                p1,
                a1,
                DependencyType.REQUIRES,
            ),
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
                InstanceEdge(
                    c1,
                    p2,
                    DependencyType.SUPPORTS,
                ),
                InstanceEdge(
                    p2,
                    a2,
                    DependencyType.REQUIRES,
                ),
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
                InstanceEdge(
                    c1,
                    p3,
                    DependencyType.CONTEXT,
                ),
                InstanceEdge(
                    p3,
                    a3,
                    DependencyType.REQUIRES,
                ),
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
                InstanceEdge(
                    b4,
                    c4,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    c4,
                    p4,
                    DependencyType.REQUIRES,
                ),
                InstanceEdge(
                    p4,
                    a4,
                    DependencyType.REQUIRES,
                ),
            ]
        )
        expected_preserved.update(
            {
                b4,
                c4,
                p4,
                a4,
            }
        )

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
        expected_invalidated=frozenset(
            expected_invalidated
        ),
        expected_reevaluation=frozenset(
            expected_reevaluation
        ),
        expected_uncertain=frozenset(
            expected_uncertain
        ),
        expected_preserved=frozenset(
            expected_preserved
        ),
        expected_stale_actions=frozenset(
            expected_stale_actions
        ),
    )

    instance.validate()
    return instance
