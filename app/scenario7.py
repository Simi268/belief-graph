from dataclasses import dataclass

from .agent import AgentRuntime
from .models import DependencyType, NodeStatus, NodeType


@dataclass
class StaleInformationResult:
    scenario_id: str
    changed_belief: str

    information_source: str
    information_was_fresh: bool
    information_is_stale: bool

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


class StaleInformationScenario:
    """
    Scenario 7:
    An agent discovers that information used by one reasoning branch
    has become stale.

    The scenario tests whether Belief-Graph can selectively invalidate
    the dependent reasoning chain while preserving an independent branch.
    """

    scenario_id = "stale_information_v1"

    def __init__(self):
        self.agent = AgentRuntime()

        self.information_source = "documentation-v1"

        self._build_graph()

    def _build_graph(self):
        # ==========================================================
        # BRANCH 1 — DEPENDS ON STALE INFORMATION
        # ==========================================================

        self.agent.create_belief(
            belief_id="B1",
            content="Customer API documentation says /users is valid",
            value="/users",
            confidence=0.90,
            source=self.information_source,
        )

        self.agent.create_node(
            node_id="C1",
            node_type=NodeType.CONCLUSION,
            content="Customer data can be retrieved using /users",
        )

        self.agent.create_node(
            node_id="P1",
            node_type=NodeType.PLAN,
            content="Retrieve customer data using /users",
        )

        self.agent.create_node(
            node_id="A1",
            node_type=NodeType.ACTION,
            content="GET /users",
            value="/users",
        )

        self.agent.add_dependency(
            "B1",
            "C1",
            DependencyType.REQUIRES,
        )

        self.agent.add_dependency(
            "C1",
            "P1",
            DependencyType.REQUIRES,
        )

        self.agent.add_dependency(
            "P1",
            "A1",
            DependencyType.REQUIRES,
        )

        # ==========================================================
        # BRANCH 2 — INDEPENDENT REASONING
        # ==========================================================

        self.agent.create_belief(
            belief_id="B2",
            content="Customer records are available in the local cache",
            value=True,
            confidence=0.90,
            source="local-cache",
        )

        self.agent.create_node(
            node_id="C2",
            node_type=NodeType.CONCLUSION,
            content="Customer records can be read from the cache",
        )

        self.agent.create_node(
            node_id="P2",
            node_type=NodeType.PLAN,
            content="Read customer records from the cache",
        )

        self.agent.create_node(
            node_id="A2",
            node_type=NodeType.ACTION,
            content="Read local customer cache",
        )

        self.agent.add_dependency(
            "B2",
            "C2",
            DependencyType.REQUIRES,
        )

        self.agent.add_dependency(
            "C2",
            "P2",
            DependencyType.REQUIRES,
        )

        self.agent.add_dependency(
            "P2",
            "A2",
            DependencyType.REQUIRES,
        )

    def mark_information_stale(self):
        """
        The original information source has been superseded.
        """

        return {
            "source": self.information_source,
            "fresh_before": True,
            "stale_after": True,
            "reason": (
                "documentation-v1 has been superseded by newer "
                "customer API documentation"
            ),
        }

    def revise_stale_belief(self):
        """
        Convert the stale-information discovery into a belief revision.
        """

        new_belief = self.agent.create_belief(
            belief_id="B3",
            content="Customer API documentation has moved from /users to /customers",
            value="/customers",
            confidence=0.95,
            source="documentation-v2",
        )

        return self.agent.graph.revise_belief(
            "B1",
            new_belief,
        )

    def run(self) -> StaleInformationResult:
        initial_node_ids = set(self.agent.graph.graph.nodes)

        freshness = self.mark_information_stale()

        impact = self.revise_stale_belief()

        invalidated_nodes = sorted(
            node_id
            for node_id in initial_node_ids
            if self.agent.graph.get_node(node_id).status
            == NodeStatus.INVALID
        )

        reevaluation_nodes = sorted(
            node_id
            for node_id in initial_node_ids
            if self.agent.graph.get_node(node_id).status
            == NodeStatus.REQUIRES_REEVALUATION
        )

        uncertain_nodes = sorted(
            node_id
            for node_id in initial_node_ids
            if self.agent.graph.get_node(node_id).status
            == NodeStatus.UNCERTAIN
        )

        preserved_nodes = sorted(
            node_id
            for node_id in initial_node_ids
            if self.agent.graph.get_node(node_id).status
            == NodeStatus.ACTIVE
        )

        affected_nodes = sorted(
            set(invalidated_nodes)
            | set(reevaluation_nodes)
            | set(uncertain_nodes)
        )

        propagation_depth = max(
            impact.get(node_id, {}).get("depth", 0)
            for node_id in affected_nodes
            if node_id != "B1"
        ) if affected_nodes else 0

        return StaleInformationResult(
            scenario_id=self.scenario_id,
            changed_belief="B1",

            information_source=freshness["source"],
            information_was_fresh=freshness["fresh_before"],
            information_is_stale=freshness["stale_after"],

            invalidated_nodes=invalidated_nodes,
            reevaluation_nodes=reevaluation_nodes,
            uncertain_nodes=uncertain_nodes,
            preserved_nodes=preserved_nodes,
            affected_nodes=affected_nodes,

            affected_node_count=len(affected_nodes),
            invalidated_node_count=len(invalidated_nodes),
            reevaluation_node_count=len(reevaluation_nodes),
            uncertain_node_count=len(uncertain_nodes),
            preserved_node_count=len(preserved_nodes),

            propagation_depth=propagation_depth,
            preservation_ratio=(
                len(preserved_nodes) / len(initial_node_ids)
                if initial_node_ids
                else 0.0
            ),
            total_original_nodes=len(initial_node_ids),
            revision_count=1,
        )