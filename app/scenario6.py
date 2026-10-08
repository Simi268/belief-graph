from dataclasses import dataclass, field

from app.graph import BeliefGraph
from app.models import (
    BeliefNode,
    DependencyType,
    NodeStatus,
    NodeType,
)


@dataclass
class ToolUnavailableResult:
    scenario_id: str
    changed_belief: str

    tool_id: str
    tool_available_before: bool
    tool_available_after: bool

    invalidated_nodes: list[str] = field(default_factory=list)
    reevaluation_nodes: list[str] = field(default_factory=list)
    uncertain_nodes: list[str] = field(default_factory=list)
    preserved_nodes: list[str] = field(default_factory=list)
    affected_nodes: list[str] = field(default_factory=list)

    affected_node_count: int = 0
    invalidated_node_count: int = 0
    reevaluation_node_count: int = 0
    uncertain_node_count: int = 0
    preserved_node_count: int = 0

    propagation_depth: int = 0
    preservation_ratio: float = 0.0
    total_original_nodes: int = 0

    revision_count: int = 0


class ToolUnavailableScenario:
    """
    Scenario 6: Tool Unavailability

    Research question:
        When a tool becomes unavailable, can Belief-Graph identify
        the dependent reasoning chain and preserve unrelated work?

    Graph:

        B1 -> C1 -> P1 -> A1
        B2 -> C2 -> P2 -> A2

    B1 represents the belief that Tool T1 is available.

    When T1 becomes unavailable, the B1 branch should be invalidated
    while the independent B2 branch remains active.
    """

    SCENARIO_ID = "tool_unavailable_v1"

    def __init__(self):
        self.graph = BeliefGraph()

        self.tool_id = "T1"
        self.tool_available = True

        self._build_graph()

    def _build_graph(self):
        nodes = [
            BeliefNode(
                id="B1",
                node_type=NodeType.BELIEF,
                content="Tool T1 is available.",
                value=True,
                source="tool_registry",
                confidence=1.0,
            ),
            BeliefNode(
                id="C1",
                node_type=NodeType.CONCLUSION,
                content="The task can be completed using Tool T1.",
                source="agent_reasoning",
            ),
            BeliefNode(
                id="P1",
                node_type=NodeType.PLAN,
                content="Use Tool T1 to complete the task.",
                source="planner",
            ),
            BeliefNode(
                id="A1",
                node_type=NodeType.ACTION,
                content="Call Tool T1.",
                source="tool_executor",
            ),
            BeliefNode(
                id="B2",
                node_type=NodeType.BELIEF,
                content="The independent task capability is available.",
                value=True,
                source="tool_registry",
                confidence=1.0,
            ),
            BeliefNode(
                id="C2",
                node_type=NodeType.CONCLUSION,
                content="The independent task can be completed.",
                source="agent_reasoning",
            ),
            BeliefNode(
                id="P2",
                node_type=NodeType.PLAN,
                content="Execute the independent task.",
                source="planner",
            ),
            BeliefNode(
                id="A2",
                node_type=NodeType.ACTION,
                content="Execute the independent action.",
                source="tool_executor",
            ),
        ]

        for node in nodes:
            self.graph.add_node(node)

        # Main tool-dependent branch.
        self.graph.add_dependency(
            "B1", "C1", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "C1", "P1", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "P1", "A1", DependencyType.REQUIRES
        )

        # Independent branch.
        self.graph.add_dependency(
            "B2", "C2", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "C2", "P2", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "P2", "A2", DependencyType.REQUIRES
        )

    def make_tool_unavailable(self):
        """
        Simulate the runtime environment making Tool T1 unavailable.
        """
        self.tool_available = False

    def execute_tool(self):
        """
        Attempt to execute Tool T1.
        """
        if not self.tool_available:
            return {
                "success": False,
                "error": "TOOL_UNAVAILABLE",
                "tool_id": self.tool_id,
            }

        return {
            "success": True,
            "tool_id": self.tool_id,
        }

    def run(self) -> ToolUnavailableResult:
        initial_node_ids = {
            node_id
            for node_id in self.graph.graph.nodes
            if node_id.startswith(("B", "C", "P", "A"))
        }

        tool_available_before = self.tool_available

        # Tool becomes unavailable.
        self.make_tool_unavailable()

        tool_result = self.execute_tool()

        if tool_result["success"]:
            raise RuntimeError(
                "Scenario 6 expected Tool T1 to be unavailable."
            )

        # The belief that the tool is available is now invalid.
        old_belief = self.graph.get_node("B1")
        old_belief.status = NodeStatus.INVALID
        old_belief.value = False

        impact = self.graph.propagate_state_impact(
            "B1",
            initial_status=NodeStatus.INVALID,
        )

        self.graph.apply_state_impact(impact)

        invalidated = sorted(
            node_id
            for node_id in initial_node_ids
            if (
                node_id == "B1"
                or self.graph.get_node(node_id).status
                == NodeStatus.INVALID
            )
        )

        reevaluation = sorted(
            node_id
            for node_id in initial_node_ids
            if self.graph.get_node(node_id).status
            == NodeStatus.REQUIRES_REEVALUATION
        )

        uncertain = sorted(
            node_id
            for node_id in initial_node_ids
            if self.graph.get_node(node_id).status
            == NodeStatus.UNCERTAIN
        )

        preserved = sorted(
            node_id
            for node_id in initial_node_ids
            if self.graph.get_node(node_id).status
            == NodeStatus.ACTIVE
        )

        affected = sorted(
            set(invalidated)
            | set(reevaluation)
            | set(uncertain)
        )

        propagation_depth = max(
            (
                impact[node_id]["depth"]
                for node_id in impact
                if node_id in initial_node_ids
            ),
            default=0,
        )

        total_original_nodes = len(initial_node_ids)
        affected_node_count = len(affected)
        preserved_node_count = len(preserved)

        preservation_ratio = (
            preserved_node_count / total_original_nodes
            if total_original_nodes
            else 0.0
        )

        return ToolUnavailableResult(
            scenario_id=self.SCENARIO_ID,
            changed_belief="B1",
            tool_id=self.tool_id,
            tool_available_before=tool_available_before,
            tool_available_after=self.tool_available,
            invalidated_nodes=invalidated,
            reevaluation_nodes=reevaluation,
            uncertain_nodes=uncertain,
            preserved_nodes=preserved,
            affected_nodes=affected,
            affected_node_count=affected_node_count,
            invalidated_node_count=len(invalidated),
            reevaluation_node_count=len(reevaluation),
            uncertain_node_count=len(uncertain),
            preserved_node_count=preserved_node_count,
            propagation_depth=propagation_depth,
            preservation_ratio=preservation_ratio,
            total_original_nodes=total_original_nodes,
            revision_count=1,
        )


if __name__ == "__main__":
    result = ToolUnavailableScenario().run()
    print(result)