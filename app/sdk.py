from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
import json
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
        # Automatic sync is opt-in and is enabled by publish(auto_sync=True).
        self._published_graph_id: str | None = None
        self._sync_base_url: str | None = None
        self._sync_timeout: float = 10.0

    def _post_sync(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST one incremental graph change to the published backend session."""
        if not self._published_graph_id or not self._sync_base_url:
            return {}
        body = json.dumps(payload, default=self._json_default).encode("utf-8")
        request = Request(
            f"{self._sync_base_url.rstrip('/')}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._sync_timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"BeliefGraph automatic sync failed for {path} "
                f"(HTTP {exc.code}): {detail}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"Could not reach BeliefGraph API at {self._sync_base_url}: {exc}"
            ) from exc

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        if hasattr(value, "__dict__"):
            return vars(value)
        return str(value)

    def _sync_node(self, node: BeliefNode) -> None:
        if not self._published_graph_id or not self._sync_base_url:
            return
        self._post_sync(
            f"/graphs/{self._published_graph_id}/nodes",
            {
                "node_id": node.id,
                "node_type": node.node_type.value,
                "content": node.content,
                "value": node.value,
                "confidence": node.confidence,
                "source": node.source,
            },
        )

    def enable_auto_sync(self, graph_id: str, base_url: str, *, timeout: float = 10.0) -> None:
        """Send subsequent new nodes/dependencies to an existing published graph."""
        if not isinstance(graph_id, str) or not graph_id.strip():
            raise ValueError("graph_id must be a non-empty string.")
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty URL.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")
        self._published_graph_id = graph_id
        self._sync_base_url = base_url.rstrip("/")
        self._sync_timeout = timeout

    def publish(
        self,
        base_url: str,
        *,
        name: str = "BeliefGraph SDK graph",
        timeout: float = 10.0,
        auto_sync: bool = False,
    ) -> dict[str, Any]:
        """Publish this in-process graph to a running BeliefGraph API.

        The API creates a persisted dashboard session and receives all nodes
        before their prerequisite-to-dependent edges. Python evaluator functions
        remain local and are deliberately not serialized or transferred. Set
        ``auto_sync=True`` to send later node/dependency additions to this session.

        Example::

            result = sdk.publish("http://127.0.0.1:8000", name="Order agent")
            print(result["graph_id"])

        This publishes a snapshot as a new backend graph. Call it after the
        graph structure is declared; it does not continuously stream later
        mutations or transfer evaluator functions.
        """
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty URL.")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string.")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        root = base_url.rstrip("/")

        def json_default(value: Any) -> Any:
            return self._json_default(value)

        def post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
            body = json.dumps(payload, default=json_default).encode("utf-8")
            request = Request(
                f"{root}{path}",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"BeliefGraph API rejected {path} (HTTP {exc.code}): {detail}"
                ) from exc
            except (URLError, TimeoutError) as exc:
                raise RuntimeError(
                    f"Could not reach BeliefGraph API at {root}: {exc}"
                ) from exc

        created = post("/graphs", {"name": name})
        graph_id = created.get("graph_id")
        if not isinstance(graph_id, str) or not graph_id:
            raise RuntimeError("BeliefGraph API did not return a graph_id.")

        graph = self.runtime.graph.graph
        node_count = 0
        dependency_count = 0

        for node_id, attributes in graph.nodes(data=True):
            node = attributes.get("data")
            if node is None:
                node = attributes

            node_type = getattr(node, "node_type", None)
            if node_type is None and isinstance(node, dict):
                node_type = node.get("node_type")
            if isinstance(node_type, Enum):
                node_type = node_type.value
            if not node_type:
                raise RuntimeError(
                    f"Cannot publish node {node_id!r}: node_type is missing. "
                    f"The backend graph {graph_id!r} was created but may be incomplete."
                )

            def field(key: str, default: Any = None) -> Any:
                if isinstance(node, dict):
                    return node.get(key, default)
                return getattr(node, key, default)

            post(
                f"/graphs/{graph_id}/nodes",
                {
                    "node_id": str(node_id),
                    "node_type": node_type,
                    "content": field("content", str(node_id)),
                    "value": field("value"),
                    "confidence": field("confidence", 1.0),
                    "source": field("source"),
                },
            )
            node_count += 1

        for source_id, target_id, attributes in graph.edges(data=True):
            dependency_type = attributes.get(
                "dependency_type", DependencyType.REQUIRES
            )
            if isinstance(dependency_type, Enum):
                dependency_type = dependency_type.value
            post(
                f"/graphs/{graph_id}/dependencies",
                {
                    "source_id": str(source_id),
                    "target_id": str(target_id),
                    "dependency_type": dependency_type,
                },
            )
            dependency_count += 1

        if auto_sync:
            self.enable_auto_sync(graph_id, root, timeout=timeout)

        return {
            "graph_id": graph_id,
            "name": name,
            "node_count": node_count,
            "dependency_count": dependency_count,
            "api_graph_url": f"{root}/graphs/{graph_id}",
            "evaluators_transferred": False,
            "message": (
                "Graph snapshot published. Evaluator functions remain local; "
                "this call does not stream later graph changes automatically."
            ),
        }

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
        node = self.runtime.create_belief(
            belief_id=belief_id,
            content=content,
            value=value,
            confidence=confidence,
            source=source,
        )
        self._sync_node(node)
        return node

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
        node = self.runtime.create_node(
            node_id=node_id,
            node_type=node_type,
            content=content,
            value=value,
            confidence=confidence,
            source=source,
        )
        self._sync_node(node)
        return node

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
    def depends_on_many(
        self,
        dependencies: dict[str, list[str]],
        dependency_type: DependencyType = DependencyType.REQUIRES,
    ) -> list[Dependency]:
        """Register multiple prerequisite-to-dependent relationships.

        ``dependencies`` maps each dependent node ID to its prerequisites.

        Example::

            sdk.depends_on_many({
                "C1": ["B1", "B2"],
                "P1": ["C1"],
            })

        This creates B1 -> C1, B2 -> C1, and C1 -> P1. Each edge is
        registered through ``depends_on`` so existing dependency semantics
        remain unchanged.

        Registration is sequential, not atomic: if a later edge fails,
        earlier edges in the batch may already have been added.
        """
        if not isinstance(dependencies, dict):
            raise TypeError("dependencies must be a dictionary.")

        created: list[Dependency] = []

        for target_id, source_ids in dependencies.items():
            if not isinstance(target_id, str) or not target_id:
                raise ValueError(
                    "Each dependent node ID must be a non-empty string."
                )

            if not isinstance(source_ids, list):
                raise TypeError(
                    f"Prerequisites for {target_id!r} must be a list."
                )

            for source_id in source_ids:
                if not isinstance(source_id, str) or not source_id:
                    raise ValueError(
                        "Each prerequisite node ID must be a non-empty string."
                    )

                created.append(
                    self.depends_on(
                        source_id=source_id,
                        target_id=target_id,
                        dependency_type=dependency_type,
                    )
                )

        return created

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
        if self._published_graph_id and self._sync_base_url:
            self._post_sync(
                f"/graphs/{self._published_graph_id}/dependencies",
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "dependency_type": dependency_type.value,
                },
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
