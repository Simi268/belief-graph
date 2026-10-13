from dataclasses import dataclass, field

from .graph import BeliefGraph
from .models import BeliefNode, DependencyType, NodeStatus, NodeType


@dataclass(frozen=True)
class MultiFailureRecoveryResult:
    """Results from the multi-failure recovery experiment."""

    scenario_id: str
    changed_beliefs: list[str]

    affected_nodes: list[str]
    invalidated_nodes: list[str]
    reevaluation_nodes: list[str]
    uncertain_nodes: list[str]
    preserved_nodes: list[str]

    shared_affected_nodes: dict[str, list[str]]

    propagation_depth: int
    affected_node_count: int
    invalidated_node_count: int
    preserved_node_count: int
    preservation_ratio: float

    total_original_nodes: int

    impact_details: dict = field(default_factory=dict)


class MultiFailureRecoveryScenario:
    """
    Scenario 8: Multi-Failure Recovery.

    Two independent beliefs fail simultaneously.

    Their dependency branches converge on a shared conclusion.
    The graph must identify the combined impact while preserving
    an unrelated reasoning branch.

    This scenario evaluates impact analysis and selective
    invalidation. It does not execute external recovery actions.
    """

    scenario_id = "multi_failure_recovery_v1"

    def __init__(self) -> None:
        self.graph = BeliefGraph()

    def build_initial_graph(self) -> None:
        """Construct the graph before either failure occurs."""

        nodes = [
            # Failure source 1: Customer API
            BeliefNode(
                id="B1",
                node_type=NodeType.BELIEF,
                content="Customer API is using version v1.",
                value="v1",
                confidence=0.95,
                source="customer_api",
            ),
            BeliefNode(
                id="C1",
                node_type=NodeType.CONCLUSION,
                content="Customer information can be retrieved.",
            ),
            BeliefNode(
                id="P1",
                node_type=NodeType.PLAN,
                content="Retrieve customer information.",
            ),
            BeliefNode(
                id="A1",
                node_type=NodeType.ACTION,
                content="Execute customer API request.",
            ),

            # Failure source 2: Database schema
            BeliefNode(
                id="B2",
                node_type=NodeType.BELIEF,
                content="The customer table contains the email column.",
                value="email",
                confidence=0.90,
                source="database_schema",
            ),
            BeliefNode(
                id="C2",
                node_type=NodeType.CONCLUSION,
                content="Customer email can be retrieved.",
            ),
            BeliefNode(
                id="P2",
                node_type=NodeType.PLAN,
                content="Query the customer email.",
            ),
            BeliefNode(
                id="A2",
                node_type=NodeType.ACTION,
                content="Execute customer email query.",
            ),

            # Shared downstream reasoning
            BeliefNode(
                id="S1",
                node_type=NodeType.CONCLUSION,
                content="The customer request can be completed.",
            ),
            BeliefNode(
                id="A4",
                node_type=NodeType.ACTION,
                content="Finalize the customer request.",
            ),

            # Independent branch
            BeliefNode(
                id="B3",
                node_type=NodeType.BELIEF,
                content="Authentication service is operational.",
                value=True,
                confidence=0.98,
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

        # Customer API dependency chain
        self.graph.add_dependency(
            "B1", "C1", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "C1", "P1", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "P1", "A1", DependencyType.REQUIRES
        )

        # Database dependency chain
        self.graph.add_dependency(
            "B2", "C2", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "C2", "P2", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "P2", "A2", DependencyType.REQUIRES
        )

        # Both failure branches converge on the same conclusion.
        self.graph.add_dependency(
            "A1", "S1", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "A2", "S1", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "S1", "A4", DependencyType.REQUIRES
        )

        # Completely independent authentication branch
        self.graph.add_dependency(
            "B3", "C3", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "C3", "P3", DependencyType.REQUIRES
        )
        self.graph.add_dependency(
            "P3", "A3", DependencyType.REQUIRES
        )

    def simulate_simultaneous_failures(self) -> list[str]:
        """
        Mark both source beliefs invalid.

        The invalidation sources are returned so the caller can
        perform a single combined impact analysis.
        """

        changed_beliefs = ["B1", "B2"]

        for belief_id in changed_beliefs:
            belief = self.graph.get_node(belief_id)
            belief.status = NodeStatus.INVALID

        return changed_beliefs

    def run(self) -> MultiFailureRecoveryResult:
        """Execute the multi-failure experiment."""

        self.build_initial_graph()

        original_node_ids = set(self.graph.graph.nodes)

        # Introduce both failures before analyzing their impact.
        changed_beliefs = self.simulate_simultaneous_failures()

        # Analyze both sources together, preserving causal attribution.
        impact_details = self.graph.analyze_multi_belief_impact(
            changed_nodes=changed_beliefs,
            initial_status=NodeStatus.INVALID,
        )

        # Apply the calculated impact to the graph.
        self.graph.apply_state_impact(impact_details)

        # Classify affected nodes using the resulting graph states.
        invalidated_nodes = {
            node_id
            for node_id, details in impact_details.items()
            if details["impact"] == NodeStatus.INVALID
        }

        reevaluation_nodes = {
            node_id
            for node_id, details in impact_details.items()
            if details["impact"] == NodeStatus.REQUIRES_REEVALUATION
        }

        uncertain_nodes = {
            node_id
            for node_id, details in impact_details.items()
            if details["impact"] == NodeStatus.UNCERTAIN
        }

        # Include the failed beliefs themselves.
        invalidated_nodes.update(changed_beliefs)

        affected_nodes = (
            invalidated_nodes
            | reevaluation_nodes
            | uncertain_nodes
        )

        # Find nodes whose impact has multiple causal sources.
        shared_affected_nodes = {
            node_id: sorted(details.get("affected_by", []))
            for node_id, details in impact_details.items()
            if len(details.get("affected_by", [])) > 1
        }

        # Anything outside the affected region must remain active
        # to count as preserved.
        preserved_nodes = {
            node_id
            for node_id in original_node_ids
            if node_id not in affected_nodes
            and self.graph.get_node(node_id).status == NodeStatus.ACTIVE
        }

        propagation_depth = max(
            (
                details["depth"]
                for details in impact_details.values()
            ),
            default=0,
        )

        preservation_ratio = (
            len(preserved_nodes) / len(original_node_ids)
            if original_node_ids
            else 0.0
        )

        return MultiFailureRecoveryResult(
            scenario_id=self.scenario_id,
            changed_beliefs=changed_beliefs,
            affected_nodes=sorted(affected_nodes),
            invalidated_nodes=sorted(invalidated_nodes),
            reevaluation_nodes=sorted(reevaluation_nodes),
            uncertain_nodes=sorted(uncertain_nodes),
            preserved_nodes=sorted(preserved_nodes),
            shared_affected_nodes=shared_affected_nodes,
            propagation_depth=propagation_depth,
            affected_node_count=len(affected_nodes),
            invalidated_node_count=len(invalidated_nodes),
            preserved_node_count=len(preserved_nodes),
            preservation_ratio=preservation_ratio,
            total_original_nodes=len(original_node_ids),
            impact_details=impact_details,
        )