from dataclasses import dataclass
from .agent import AgentRuntime
from .models import (
    NodeType,
    DependencyType,
    BeliefNode,
    Evidence,
    NodeStatus,
)


@dataclass
class ContradictoryEvidenceResult:
    scenario_id: str

    changed_belief: str

    weak_evidence_id: str
    weak_evidence_accepted: bool

    strong_evidence_id: str
    strong_evidence_accepted: bool

    selected_evidence_id: str

    invalidated_nodes: list[str]
    reevaluation_nodes: list[str]
    uncertain_nodes: list[str]
    preserved_nodes: list[str]

    affected_nodes: list[str]

    affected_node_count: int
    invalidated_node_count: int
    reevaluation_node_count: int
    uncertain_node_count: int
    preserved_node_count: int

    propagation_depth: int
    preservation_ratio: float

    total_original_nodes: int
    revision_count: int


class ContradictoryEvidenceScenario:
    """
    Scenario 5: Contradictory Evidence.

    Tests whether the system can distinguish between:

    1. weaker contradictory evidence -> reject revision
    2. stronger contradictory evidence -> revise belief

    After the stronger evidence is accepted, only the reasoning
    chain depending on the revised belief should be invalidated.
    """

    def __init__(self):
        self.agent = AgentRuntime()

    def _build_graph(self):
        agent = self.agent

        # ------------------------------------------------------
        # PRIMARY BELIEF
        # ------------------------------------------------------

        agent.create_belief(
            belief_id="B1",
            content="Customer is eligible for premium support",
            value=True,
            confidence=0.85,
            source="initial-policy",
        )

        agent.create_node(
            node_id="C1",
            node_type=NodeType.CONCLUSION,
            content="Premium support can be provided",
        )

        agent.create_node(
            node_id="P1",
            node_type=NodeType.PLAN,
            content="Prepare premium support response",
        )

        agent.create_node(
            node_id="A1",
            node_type=NodeType.ACTION,
            content="Provide premium support",
        )

        agent.add_dependency(
            "B1",
            "C1",
            DependencyType.REQUIRES,
        )

        agent.add_dependency(
            "C1",
            "P1",
            DependencyType.REQUIRES,
        )

        agent.add_dependency(
            "P1",
            "A1",
            DependencyType.REQUIRES,
        )

        # ------------------------------------------------------
        # UNRELATED BRANCH
        # ------------------------------------------------------

        agent.create_belief(
            belief_id="B2",
            content="Customer profile is available",
            value=True,
            confidence=0.90,
            source="customer-record",
        )

        agent.create_node(
            node_id="C2",
            node_type=NodeType.CONCLUSION,
            content="Customer profile can be displayed",
        )

        agent.create_node(
            node_id="P2",
            node_type=NodeType.PLAN,
            content="Display customer profile",
        )

        agent.create_node(
            node_id="A2",
            node_type=NodeType.ACTION,
            content="Display customer profile",
        )

        agent.add_dependency(
            "B2",
            "C2",
            DependencyType.REQUIRES,
        )

        agent.add_dependency(
            "C2",
            "P2",
            DependencyType.REQUIRES,
        )

        agent.add_dependency(
            "P2",
            "A2",
            DependencyType.REQUIRES,
        )

        return {
            "B1",
            "C1",
            "P1",
            "A1",
            "B2",
            "C2",
            "P2",
            "A2",
        }

    def run(self) -> ContradictoryEvidenceResult:
        original_nodes = self._build_graph()

        # ------------------------------------------------------
        # WEAKER CONTRADICTORY EVIDENCE
        # ------------------------------------------------------

        weak_evidence = Evidence(
            id="E1",
            content=(
                "Customer is not eligible for premium support "
                "according to an older support record."
            ),
            source="legacy-support-record",
            confidence=0.70,
        )

        self.agent.graph.add_evidence(weak_evidence)

        weak_conflict = self.agent.graph.detect_conflict(
            evidence_id="E1",
            belief_id="B1",
        )

        weak_resolution = self.agent.graph.resolve_conflict(
            conflict_id=weak_conflict.id,
            new_belief=BeliefNode(
                id="B3",
                node_type=NodeType.BELIEF,
                content="Customer is not eligible for premium support",
                value=False,
                confidence=weak_evidence.confidence,
                source="legacy-support-record",
            ),
        )

        weak_accepted = (
            weak_resolution.get("status") == "revised"
        )

        # ------------------------------------------------------
        # STRONGER CONTRADICTORY EVIDENCE
        # ------------------------------------------------------

        strong_evidence = Evidence(
            id="E2",
            content=(
                "Customer is not eligible for premium support "
                "according to the current entitlement database."
            ),
            source="current-entitlement-database",
            confidence=0.97,
        )

        self.agent.graph.add_evidence(strong_evidence)

        strong_conflict = self.agent.graph.detect_conflict(
            evidence_id="E2",
            belief_id="B1",
        )

        strong_resolution = self.agent.graph.resolve_conflict(
            conflict_id=strong_conflict.id,
            new_belief=BeliefNode(
                id="B4",
                node_type=NodeType.BELIEF,
                content="Customer is not eligible for premium support",
                value=False,
                confidence=strong_evidence.confidence,
                source="current-entitlement-database",
            ),
        )

        strong_accepted = (
            strong_resolution.get("status") == "revised"
        )

        # ------------------------------------------------------
        # DETERMINE FINAL IMPACT
        # ------------------------------------------------------

        invalidated_nodes = []
        reevaluation_nodes = []
        uncertain_nodes = []

        for node_id in original_nodes:
            if node_id not in self.agent.graph.graph:
                continue

            node = self.agent.graph.get_node(node_id)

            if node.status == NodeStatus.INVALID:
                invalidated_nodes.append(node_id)

            elif node.status == NodeStatus.REQUIRES_REEVALUATION:
                reevaluation_nodes.append(node_id)

            elif node.status == NodeStatus.UNCERTAIN:
                uncertain_nodes.append(node_id)

        affected_nodes = (
            set(invalidated_nodes)
            | set(reevaluation_nodes)
            | set(uncertain_nodes)
        )

        preserved_nodes = (
            set(original_nodes) - affected_nodes
        )

        # B1 -> C1 -> P1 -> A1
        propagation_depth = 3

        preservation_ratio = (
            len(preserved_nodes) / len(original_nodes)
            if original_nodes
            else 0.0
        )

        return ContradictoryEvidenceResult(
            scenario_id="contradictory_evidence_v1",
            changed_belief="B1",

            weak_evidence_id="E1",
            weak_evidence_accepted=weak_accepted,

            strong_evidence_id="E2",
            strong_evidence_accepted=strong_accepted,

            selected_evidence_id=(
                "E2" if strong_accepted else "E1"
            ),

            invalidated_nodes=sorted(invalidated_nodes),
            reevaluation_nodes=sorted(reevaluation_nodes),
            uncertain_nodes=sorted(uncertain_nodes),
            preserved_nodes=sorted(preserved_nodes),

            affected_nodes=sorted(affected_nodes),

            affected_node_count=len(affected_nodes),
            invalidated_node_count=len(invalidated_nodes),
            reevaluation_node_count=len(reevaluation_nodes),
            uncertain_node_count=len(uncertain_nodes),
            preserved_node_count=len(preserved_nodes),

            propagation_depth=propagation_depth,
            preservation_ratio=preservation_ratio,

            total_original_nodes=len(original_nodes),
            revision_count=1 if strong_accepted else 0,
        )