from dataclasses import dataclass

from .graph import BeliefGraph
from .models import BeliefNode, DependencyType, NodeStatus, NodeType


@dataclass(frozen=True)
class DatabaseSchemaChangeResult:
    scenario_id: str
    changed_belief: str

    invalidated_nodes: list[str]
    reevaluation_nodes: list[str]
    uncertain_nodes: list[str]
    preserved_nodes: list[str]

    propagation_depth: int
    affected_node_count: int
    invalidated_node_count: int
    preserved_node_count: int
    preservation_ratio: float

    total_original_nodes: int


class DatabaseSchemaChangeScenario:
    """
    Scenario 3: Database Schema Change

    The agent initially believes that the `customers` table contains
    an `email` column.

    A later schema change removes `email` and introduces
    `contact_email`.

    Only the reasoning branch that depends on the old `email`
    belief should become invalid.
    """

    scenario_id = "database_schema_change_v1"

    def __init__(self) -> None:
        self.graph = BeliefGraph()

    def build_initial_graph(self) -> None:
        """Build the reasoning graph before the schema changes."""

        nodes = [
            # Schema-dependent branch
            BeliefNode(
                id="B1",
                node_type=NodeType.BELIEF,
                content="Customer table contains an email column.",
                value="email",
                source="database_schema",
            ),
            BeliefNode(
                id="C1",
                node_type=NodeType.CONCLUSION,
                content="Customer email can be queried.",
            ),
            BeliefNode(
                id="P1",
                node_type=NodeType.PLAN,
                content="Retrieve customer email.",
            ),
            BeliefNode(
                id="A1",
                node_type=NodeType.ACTION,
                content="SELECT email FROM customers.",
            ),

            # Independent database branch
            BeliefNode(
                id="B2",
                node_type=NodeType.BELIEF,
                content="Customer table still exists.",
                value="customers",
                source="database_schema",
            ),
            BeliefNode(
                id="C2",
                node_type=NodeType.CONCLUSION,
                content="Customer records can still be queried.",
            ),
            BeliefNode(
                id="P2",
                node_type=NodeType.PLAN,
                content="Retrieve customer ID.",
            ),
            BeliefNode(
                id="A2",
                node_type=NodeType.ACTION,
                content="SELECT id FROM customers.",
            ),

            # Completely unrelated branch
            BeliefNode(
                id="B3",
                node_type=NodeType.BELIEF,
                content="Authentication service is available.",
                source="authentication_service",
            ),
            BeliefNode(
                id="C3",
                node_type=NodeType.CONCLUSION,
                content="User authentication can proceed.",
            ),
            BeliefNode(
                id="P3",
                node_type=NodeType.PLAN,
                content="Authenticate the user.",
            ),
            BeliefNode(
                id="A3",
                node_type=NodeType.ACTION,
                content="Call authentication service.",
            ),
        ]

        for node in nodes:
            self.graph.add_node(node)

        # Schema-dependent branch
        self.graph.add_dependency(
            "B1", "C1", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "C1", "P1", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "P1", "A1", DependencyType.REQUIRES
        )

        # Independent database branch
        self.graph.add_dependency(
            "B2", "C2", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "C2", "P2", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "P2", "A2", DependencyType.REQUIRES
        )

        # Unrelated branch
        self.graph.add_dependency(
            "B3", "C3", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "C3", "P3", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "P3", "A3", DependencyType.REQUIRES
        )

    def apply_schema_change(self) -> dict:
        """
        Simulate the database schema changing.

        Old:
            customers(id, name, email)

        New:
            customers(id, name, contact_email)

        Therefore B1 is no longer valid.
        """

        impact = self.graph.propagate_state_impact(
            "B1",
            initial_status=NodeStatus.INVALID,
        )

        self.graph.apply_state_impact(impact)

        return impact

    def run(self) -> DatabaseSchemaChangeResult:
        """Run the complete scenario."""

        self.build_initial_graph()

        original_node_ids = set(self.graph.graph.nodes)

        impact = self.apply_schema_change()

        invalidated_nodes = {
            node_id
            for node_id, details in impact.items()
            if details["impact"] == NodeStatus.INVALID.value
        }

        # The changed belief itself is part of the invalidated region.
        invalidated_nodes.add("B1")

        reevaluation_nodes = {
            node_id
            for node_id, details in impact.items()
            if details["impact"]
            == NodeStatus.REQUIRES_REEVALUATION.value
        }

        uncertain_nodes = {
            node_id
            for node_id, details in impact.items()
            if details["impact"] == NodeStatus.UNCERTAIN.value
        }

        affected_nodes = (
            invalidated_nodes
            | reevaluation_nodes
            | uncertain_nodes
        )

        preserved_nodes = original_node_ids - affected_nodes

        propagation_depth = max(
            (
                details["depth"]
                for details in impact.values()
                if details["impact"] != NodeStatus.ACTIVE.value
            ),
            default=0,
        )

        preservation_ratio = (
            len(preserved_nodes) / len(original_node_ids)
            if original_node_ids
            else 0.0
        )

        return DatabaseSchemaChangeResult(
            scenario_id=self.scenario_id,
            changed_belief="B1",
            invalidated_nodes=sorted(invalidated_nodes),
            reevaluation_nodes=sorted(reevaluation_nodes),
            uncertain_nodes=sorted(uncertain_nodes),
            preserved_nodes=sorted(preserved_nodes),
            propagation_depth=propagation_depth,
            affected_node_count=len(affected_nodes),
            invalidated_node_count=len(invalidated_nodes),
            preserved_node_count=len(preserved_nodes),
            preservation_ratio=preservation_ratio,
            total_original_nodes=len(original_node_ids),
        )