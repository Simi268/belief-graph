from dataclasses import dataclass
from typing import Any

from .agent import AgentRuntime
from .models import (
    BeliefNode,
    DependencyType,
    NodeStatus,
    NodeType,
)


@dataclass(frozen=True)
class Dependency:
    source_id: str
    target_id: str
    dependency_type: DependencyType


class BeliefGraphSDK:
    """
    Public developer-facing interface for Belief-Graph.

    The SDK intentionally sits above AgentRuntime so that:
    - the core reasoning engine remains independent
    - callers do not need to manipulate the underlying NetworkX graph
    - LangGraph / FastAPI / CLI integrations can share one interface
    """

    def __init__(self, runtime: AgentRuntime | None = None):
        self.runtime = runtime or AgentRuntime()

    # ---------------------------------------------------------
    # BELIEFS
    # ---------------------------------------------------------

    def belief(
        self,
        belief_id: str,
        content: str,
        value: Any = None,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> BeliefNode:
        return self.runtime.create_belief(
            belief_id=belief_id,
            content=content,
            value=value,
            confidence=confidence,
            source=source,
        )

    # ---------------------------------------------------------
    # REASONING NODES
    # ---------------------------------------------------------

    def node(
        self,
        node_id: str,
        node_type: NodeType,
        content: str,
        value: Any = None,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> BeliefNode:
        return self.runtime.create_node(
            node_id=node_id,
            node_type=node_type,
            content=content,
            value=value,
            confidence=confidence,
            source=source,
        )

    def conclusion(
        self,
        node_id: str,
        content: str,
        value: Any = None,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> BeliefNode:
        return self.node(
            node_id=node_id,
            node_type=NodeType.CONCLUSION,
            content=content,
            value=value,
            confidence=confidence,
            source=source,
        )

    def plan(
        self,
        node_id: str,
        content: str,
        value: Any = None,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> BeliefNode:
        return self.node(
            node_id=node_id,
            node_type=NodeType.PLAN,
            content=content,
            value=value,
            confidence=confidence,
            source=source,
        )

    def action(
        self,
        node_id: str,
        content: str,
        value: Any = None,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> BeliefNode:
        return self.node(
            node_id=node_id,
            node_type=NodeType.ACTION,
            content=content,
            value=value,
            confidence=confidence,
            source=source,
        )

    # ---------------------------------------------------------
    # DEPENDENCIES
    # ---------------------------------------------------------

    def depends_on(
        self,
        source_id: str,
        target_id: str,
        dependency_type: DependencyType = DependencyType.REQUIRES,
    ) -> Dependency:
        dependency = Dependency(
            source_id=source_id,
            target_id=target_id,
            dependency_type=dependency_type,
        )

        self.runtime.add_dependency(
            source_id,
            target_id,
            dependency_type,
        )

        return dependency

    # ---------------------------------------------------------
    # EVIDENCE
    # ---------------------------------------------------------

    def observe(
        self,
        evidence_id: str,
        content: str,
        source: str,
        confidence: float = 1.0,
    ):
        return self.runtime.observe(
            evidence_id=evidence_id,
            content=content,
            source=source,
            confidence=confidence,
        )

    def support(
        self,
        evidence_id: str,
        belief_id: str,
    ):
        return self.runtime.support_belief(
            evidence_id,
            belief_id,
        )

    def contradict(
        self,
        evidence_id: str,
        belief_id: str,
    ):
        return self.runtime.detect_contradiction(
            evidence_id,
            belief_id,
        )

    # ---------------------------------------------------------
    # STATE
    # ---------------------------------------------------------

    def status(self, node_id: str) -> NodeStatus:
        return self.runtime.graph.get_node(node_id).status

    def get(self, node_id: str) -> BeliefNode:
        return self.runtime.graph.get_node(node_id)

    # ---------------------------------------------------------
    # IMPACT ANALYSIS
    # ---------------------------------------------------------

    def analyze_impact(
        self,
        changed_node_ids: list[str],
    ) -> dict:
        return self.runtime.graph.analyze_multi_belief_impact(
            changed_nodes=changed_node_ids
        )

    # ---------------------------------------------------------
    # REVISION
    # ---------------------------------------------------------

    def revise_from_conflict(
        self,
        conflict_id: str,
        new_belief_id: str,
    ):
        return self.runtime.revise_from_action_failure(
            conflict_id=conflict_id,
            new_belief_id=new_belief_id,
        )

    # ---------------------------------------------------------
    # RAW ACCESS
    # ---------------------------------------------------------

    @property
    def graph(self):
        """
        Escape hatch for advanced integrations.

        Normal users should prefer the SDK methods above.
        """
        return self.runtime.graph

    