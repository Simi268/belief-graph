from dataclasses import dataclass
from typing import Any, Callable, Mapping

import networkx as nx

from .agent import AgentRuntime
from .models import (
    ActionExecutionStatus,
    BeliefNode,
    DependencyType,
    NodeStatus,
    NodeType,
)


Evaluator = Callable[[BeliefNode, Mapping[str, Any]], Any]


@dataclass(frozen=True)
class Dependency:
    source_id: str
    target_id: str
    dependency_type: DependencyType


class BeliefGraphSDK:
    """Thin public interface for instrumenting an agent with BeliefGraph.

    ``source_id`` is always the prerequisite and ``target_id`` is the dependent
    node. Semantic evaluators receive ``(node, predecessor_values)`` and return
    the node's new value. Belief nodes are source facts and cannot have evaluators.
    """

    def __init__(self, runtime: AgentRuntime | None = None):
        self.runtime = runtime or AgentRuntime()
        self._evaluators: dict[str, Evaluator] = {}

    def new_run(self):
        """Create a new, isolated execution session."""
        from .runs import RunSession

        return RunSession()

    # ---------------------------------------------------------
    # BELIEFS AND DERIVED NODES
    # ---------------------------------------------------------

    def belief(
        self,
        belief_id: str,
        content: str,
        value: Any = None,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> BeliefNode:
        """Declare a source belief for the agent."""
        return self.runtime.create_belief(
            belief_id=belief_id,
            content=content,
            value=value,
            confidence=confidence,
            source=source,
        )

    def node(
        self,
        node_id: str,
        node_type: NodeType,
        content: str,
        value: Any = None,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> BeliefNode:
        """Declare a typed conclusion, plan, or action node."""
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
    # DEPENDENCIES AND SEMANTIC EVALUATORS
    # ---------------------------------------------------------

    def depends_on(
        self,
        source_id: str,
        target_id: str,
        dependency_type: DependencyType = DependencyType.REQUIRES,
    ) -> Dependency:
        """Add an edge from prerequisite ``source_id`` to dependent ``target_id``."""
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

    def register_evaluator(
        self,
        node_id: str,
        evaluator: Evaluator | None = None,
    ):
        """Register a semantic evaluator, directly or as a decorator.

        Direct form::

            sdk.register_evaluator("C1", evaluate_conclusion)

        Decorator form::

            @sdk.register_evaluator("C1")
            def evaluate_conclusion(node, predecessor_values):
                ...

        The node must already exist and must not be a source BELIEF node.
        Re-registering an evaluator for the same node replaces the prior one.
        """

        def attach(function: Evaluator) -> Evaluator:
            if not callable(function):
                raise TypeError("evaluator must be callable.")

            node = self.runtime.graph.get_node(node_id)
            if node.node_type == NodeType.BELIEF:
                raise ValueError(
                    f"Cannot register an evaluator for source belief {node_id!r}."
                )

            self._evaluators[node_id] = function
            return function

        if evaluator is None:
            return attach
        return attach(evaluator)

    # ---------------------------------------------------------
    # ACTION EXECUTION AND RECOVERY
    # ---------------------------------------------------------

    def execute_action(
        self,
        *,
        action_id: str,
        belief_id: str,
        environment,
    ) -> dict[str, Any]:
        """Execute an API action using a belief and return its environment result."""
        graph = self.runtime.graph.graph
        action = self.runtime.graph.get_node(action_id)
        belief = self.runtime.graph.get_node(belief_id)
        if action.node_type != NodeType.ACTION:
            raise ValueError(f"Node {action_id!r} is not an action.")
        if belief.node_type != NodeType.BELIEF:
            raise ValueError(f"Node {belief_id!r} is not a source belief.")
        if not nx.has_path(graph, source=belief_id, target=action_id):
            raise ValueError(
                f"Action {action_id!r} does not depend on belief {belief_id!r}."
            )

        result = self.runtime.execute_api_action(
            environment=environment,
            belief_id=belief_id,
            action_id=action_id,
        )
        environment_result = result.get("environment_result", {})
        succeeded = bool(environment_result.get("success", False))
        action.execution_status = (
            ActionExecutionStatus.SUCCEEDED
            if succeeded
            else ActionExecutionStatus.FAILED
        )
        action.execution_result = {
            "success": succeeded,
            "belief_id": belief_id,
            "action_id": action_id,
            "assumed_version": result.get("assumed_version"),
            "environment_result": environment_result,
        }
        return result

    def recover_from_action_failure(
        self,
        *,
        action_result: dict[str, Any],
        evidence_id: str,
        new_belief_id: str,
        new_action_id: str,
        environment=None,
    ) -> dict[str, Any]:
        """Revise a failed action's belief and run recovery.

        If evaluators have been registered, they are passed to the existing
        selective-recovery path. If no evaluators are registered, the established
        revision/replanning path still runs, but semantic recomputation is not
        attempted.
        """
        from .recovery import RecoveryEngine
        from .semantic_recomputation import SemanticRecomputer

        recompute_node = (
            SemanticRecomputer(self.runtime, self._evaluators)
            if self._evaluators
            else None
        )
        return RecoveryEngine(self.runtime).recover_from_action_failure(
            action_result=action_result,
            evidence_id=evidence_id,
            new_belief_id=new_belief_id,
            new_action_id=new_action_id,
            environment=environment,
            recompute_node=recompute_node,
        )

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
    # STATE AND IMPACT ANALYSIS
    # ---------------------------------------------------------

    def status(self, node_id: str) -> NodeStatus:
        return self.runtime.graph.get_node(node_id).status

    def get(self, node_id: str) -> BeliefNode:
        return self.runtime.graph.get_node(node_id)

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
        """Escape hatch for advanced integrations; normal callers can use the SDK."""
        return self.runtime.graph
