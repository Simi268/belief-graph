from dataclasses import dataclass

from .graph import BeliefGraph
from .models import BeliefNode, DependencyType, NodeStatus, NodeType


@dataclass
class PolicyChangeResult:
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


class PolicyChangeScenario:
    """
    Scenario 4: a policy relied upon by an agent changes at runtime.

    The scenario is intentionally different from the database-schema scenario:
    the changed belief represents a policy/rule, and the dependent reasoning
    chain represents a policy-governed decision.
    """

    scenario_id = "policy_change_v1"

    def __init__(self) -> None:
        self.graph = BeliefGraph()

    def _add_node(
        self,
        node_id: str,
        node_type: NodeType,
        content: str,
        value=None,
        source: str = "scenario4",
    ) -> None:
        self.graph.add_node(
            BeliefNode(
                id=node_id,
                node_type=node_type,
                content=content,
                value=value,
                source=source,
            )
        )

    def build_graph(self) -> None:
        # Policy-governed branch.
        self._add_node(
            "B1",
            NodeType.BELIEF,
            "Promotional emails are allowed without explicit consent.",
            value="no_explicit_consent_required",
        )
        self._add_node(
            "C1",
            NodeType.CONCLUSION,
            "A promotional email may be sent to the user.",
        )
        self._add_node(
            "P1",
            NodeType.PLAN,
            "Send the promotional email.",
        )
        self._add_node(
            "A1",
            NodeType.ACTION,
            "Send promotional email.",
        )

        self.graph.add_dependency("B1", "C1", DependencyType.REQUIRES)
        self.graph.add_dependency("C1", "P1", DependencyType.REQUIRES)
        self.graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

        # Independent customer-service branch.
        self._add_node(
            "B2",
            NodeType.BELIEF,
            "The user's support request is eligible for normal processing.",
        )
        self._add_node(
            "C2",
            NodeType.CONCLUSION,
            "The support request can be processed.",
        )
        self._add_node(
            "P2",
            NodeType.PLAN,
            "Process the support request.",
        )
        self._add_node(
            "A2",
            NodeType.ACTION,
            "Process the support request.",
        )

        self.graph.add_dependency("B2", "C2", DependencyType.REQUIRES)
        self.graph.add_dependency("C2", "P2", DependencyType.REQUIRES)
        self.graph.add_dependency("P2", "A2", DependencyType.REQUIRES)

        # Unrelated analytics branch.
        self._add_node(
            "B3",
            NodeType.BELIEF,
            "Daily analytics data is available.",
        )
        self._add_node(
            "C3",
            NodeType.CONCLUSION,
            "The daily analytics report can be generated.",
        )
        self._add_node(
            "P3",
            NodeType.PLAN,
            "Generate the daily analytics report.",
        )
        self._add_node(
            "A3",
            NodeType.ACTION,
            "Generate analytics report.",
        )

        self.graph.add_dependency("B3", "C3", DependencyType.REQUIRES)
        self.graph.add_dependency("C3", "P3", DependencyType.REQUIRES)
        self.graph.add_dependency("P3", "A3", DependencyType.REQUIRES)

    def run(self) -> PolicyChangeResult:
        self.build_graph()

        original_nodes = set(self.graph.graph.nodes)

        # Runtime policy update: explicit consent is now required.
        # BeliefGraph.revise_belief() expects (old_id, new_belief).
        new_policy = BeliefNode(
            id="B4",
            node_type=NodeType.BELIEF,
            content="Promotional emails require explicit user consent.",
            value="explicit_consent_required",
            confidence=1.0,
            source="policy-update",
        )

        impact = self.graph.revise_belief(
            "B1",
            new_policy,
        )

        # revise_belief() returns metadata entries too. Keep only the
        # dependency impact for nodes in the original benchmark state.
        impact = {
            node_id: details
            for node_id, details in impact.items()
            if node_id in original_nodes
            and isinstance(details, dict)
            and "impact" in details
        }

        # revise_belief() marks the changed belief itself INVALID,
        # but its returned dependency-impact map contains downstream
        # nodes. Include B1 explicitly in the benchmark state.
        impact["B1"] = {
            "impact": NodeStatus.INVALID,
            "depth": 0,
        }

        invalidated = sorted(
            node_id
            for node_id, details in impact.items()
            if details["impact"] == NodeStatus.INVALID
            and node_id in original_nodes
        )
        reevaluation = sorted(
            node_id
            for node_id, details in impact.items()
            if details["impact"] == NodeStatus.REQUIRES_REEVALUATION
            and node_id in original_nodes
        )
        uncertain = sorted(
            node_id
            for node_id, details in impact.items()
            if details["impact"] == NodeStatus.UNCERTAIN
            and node_id in original_nodes
        )

        affected = set(invalidated) | set(reevaluation) | set(uncertain)
        preserved = sorted(original_nodes - affected)

        propagation_depth = max(
            (
                details.get("depth", 0)
                for node_id, details in impact.items()
                if node_id in original_nodes
            ),
            default=0,
        )

        return PolicyChangeResult(
            scenario_id=self.scenario_id,
            changed_belief="B1",
            invalidated_nodes=invalidated,
            reevaluation_nodes=reevaluation,
            uncertain_nodes=uncertain,
            preserved_nodes=preserved,
            propagation_depth=propagation_depth,
            affected_node_count=len(affected),
            invalidated_node_count=len(invalidated),
            preserved_node_count=len(preserved),
            preservation_ratio=(
                len(preserved) / len(original_nodes)
                if original_nodes
                else 0.0
            ),
            total_original_nodes=len(original_nodes),
        )


if __name__ == "__main__":
    result = PolicyChangeScenario().run()
    print(result)
