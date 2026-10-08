from __future__ import annotations

from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, Callable, Iterable

from .models import DependencyType, NodeStatus, NodeType
from .sdk import BeliefGraphSDK


class LangGraphAdapter:
    """
    Adapter between LangGraph execution nodes and Belief-Graph reasoning nodes.

    LangGraph answers:
        "What executes next?"

    Belief-Graph answers:
        "What reasoning depends on what?"

    This adapter connects the two without making the core Belief-Graph
    implementation dependent on LangGraph.
    """

    def __init__(
        self,
        belief_graph: BeliefGraphSDK | None = None,
    ):
        self.belief_graph = belief_graph or BeliefGraphSDK()

        # LangGraph node name -> Belief-Graph node ID
        self._node_map: dict[str, str] = {}

    # ==========================================================
    # NODE REGISTRATION
    # ==========================================================

    def register_node(
        self,
        langgraph_node: str,
        belief_node_id: str,
        node_type: NodeType,
        content: str,
        value: Any = None,
    ) -> str:
        """
        Register an explicit LangGraph -> Belief-Graph mapping.
        """

        if not langgraph_node:
            raise ValueError(
                "langgraph_node must be a non-empty string."
            )

        if not belief_node_id:
            raise ValueError(
                "belief_node_id must be a non-empty string."
            )

        existing = self._node_map.get(langgraph_node)

        if existing is not None:
            if existing != belief_node_id:
                raise ValueError(
                    f"LangGraph node '{langgraph_node}' is already "
                    f"mapped to Belief-Graph node '{existing}', "
                    f"cannot remap it to '{belief_node_id}'."
                )

            return belief_node_id

        runtime = self.belief_graph.runtime
        graph = runtime.graph

        if belief_node_id not in graph.graph.nodes:
            if node_type == NodeType.BELIEF:
                runtime.create_belief(
                    belief_id=belief_node_id,
                    content=content,
                    value=value,
                )
            else:
                runtime.create_node(
                    node_id=belief_node_id,
                    node_type=node_type,
                    content=content,
                    value=value,
                )

        self._node_map[langgraph_node] = belief_node_id

        return belief_node_id

    # ==========================================================
    # NODE RESOLUTION
    # ==========================================================

    def belief_node_id(
        self,
        langgraph_node: str,
    ) -> str:
        """
        Resolve a registered LangGraph node name to its Belief-Graph ID.
        """

        try:
            return self._node_map[langgraph_node]
        except KeyError as exc:
            raise ValueError(
                f"Unknown LangGraph node: {langgraph_node}"
            ) from exc

    def _resolve_node_id(
        self,
        node_name_or_id: str,
    ) -> str:
        """
        Resolve either a LangGraph node name or an existing
        Belief-Graph node ID.
        """

        if node_name_or_id in self._node_map:
            return self._node_map[node_name_or_id]

        if node_name_or_id in self.graph.graph.nodes:
            return node_name_or_id

        raise ValueError(
            f"Unknown LangGraph or Belief-Graph node: "
            f"{node_name_or_id}"
        )

    # ==========================================================
    # DEPENDENCY MANAGEMENT
    # ==========================================================

    def add_dependency(
        self,
        source_langgraph_node: str,
        target_langgraph_node: str,
        dependency_type: DependencyType = DependencyType.REQUIRES,
    ) -> None:
        """
        Add source -> target dependency to Belief-Graph.
        """

        source_id = self._resolve_node_id(
            source_langgraph_node
        )

        target_id = self._resolve_node_id(
            target_langgraph_node
        )

        self.belief_graph.graph.add_dependency(
            source_id=source_id,
            target_id=target_id,
            dependency_type=dependency_type,
        )

    def add_dependencies(
        self,
        dependencies: Iterable[
            tuple[str, str, DependencyType]
        ],
    ) -> None:
        """
        Add multiple dependencies.
        """

        for (
            source,
            target,
            dependency_type,
        ) in dependencies:
            self.add_dependency(
                source_langgraph_node=source,
                target_langgraph_node=target,
                dependency_type=dependency_type,
            )

    # ==========================================================
    # RUNTIME NODE HELPERS
    # ==========================================================

    def _ensure_runtime_node(
        self,
        langgraph_node: str,
    ) -> str:
        """
        Ensure a LangGraph execution node has a corresponding
        Belief-Graph node.

        Auto-created nodes use:
            lg::<langgraph_node>
        """

        if langgraph_node in self._node_map:
            return self._node_map[langgraph_node]

        belief_node_id = f"lg::{langgraph_node}"

        return self.register_node(
            langgraph_node=langgraph_node,
            belief_node_id=belief_node_id,
            node_type=NodeType.CONCLUSION,
            content=(
                f"LangGraph execution node: "
                f"{langgraph_node}"
            ),
        )

    def _resolve_dependency_source(
        self,
        source: str,
        state: Any,
    ) -> str:
        """
        Resolve a dependency source returned by a runtime resolver.

        The resolver may return either:
            - a LangGraph node name, or
            - a Belief-Graph node ID.
        """

        if source in self._node_map:
            return self._node_map[source]

        if source in self.graph.graph.nodes:
            return source

        state_node_map = self._state_node_map(state)

        mapped = state_node_map.get(source)

        if mapped is not None:
            if mapped in self.graph.graph.nodes:
                return mapped

            if mapped in self._node_map:
                return self._node_map[mapped]

        return self._ensure_runtime_node(source)

    # ==========================================================
    # STATE HELPERS
    # ==========================================================

    def _extract_state(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        """
        Extract LangGraph state from a wrapped node call.
        """

        if args:
            return args[0]

        if "state" in kwargs:
            return kwargs["state"]

        return None

    def _state_node_map(
        self,
        state: Any,
    ) -> dict[str, str]:
        """
        Extract optional runtime LangGraph -> Belief-Graph mappings
        from state.

        Supported keys:
            belief_node_ids
            belief_nodes
            node_to_belief
            langgraph_node_map
        """

        if not isinstance(state, dict):
            return {}

        for key in (
            "belief_node_ids",
            "belief_nodes",
            "node_to_belief",
            "langgraph_node_map",
        ):
            value = state.get(key)

            if isinstance(value, dict):
                return {
                    str(k): str(v)
                    for k, v in value.items()
                    if isinstance(k, str)
                    and isinstance(v, str)
                }

        return {}

    # ==========================================================
    # RUNTIME DEPENDENCY RECORDING
    # ==========================================================

    def _record_dependencies_from_resolver(
        self,
        langgraph_node: str,
        state: Any,
        dependency_resolver: Callable[[Any], Iterable[Any]],
        dependency_type: DependencyType,
    ) -> None:
        """
        Run an explicit dependency resolver and record the resulting
        dependency edges.

        Resolver contract:

            resolver(state) -> ["retrieve", "memory"]

        or:

            resolver(state) -> [
                {
                    "node": "retrieve",
                    "dependency_type": "requires",
                }
            ]
        """

        target_id = self._ensure_runtime_node(
            langgraph_node
        )

        resolved_sources = dependency_resolver(
            state
        )

        if resolved_sources is None:
            return

        if isinstance(resolved_sources, str):
            resolved_sources = [resolved_sources]

        for source_item in resolved_sources:
            source = source_item
            edge_type = dependency_type

            if isinstance(source_item, dict):
                source = (
                    source_item.get("node")
                    or source_item.get("source")
                    or source_item.get("langgraph_node")
                    or source_item.get("belief_node_id")
                )

                raw_type = source_item.get(
                    "dependency_type"
                )

                if raw_type is not None:
                    try:
                        edge_type = (
                            raw_type
                            if isinstance(
                                raw_type,
                                DependencyType,
                            )
                            else DependencyType(raw_type)
                        )
                    except ValueError as exc:
                        raise ValueError(
                            f"Unknown dependency type: "
                            f"{raw_type}"
                        ) from exc

            if not isinstance(source, str):
                continue

            source_id = self._resolve_dependency_source(
                source=source,
                state=state,
            )

            self.belief_graph.graph.add_dependency(
                source_id=source_id,
                target_id=target_id,
                dependency_type=edge_type,
            )

    # ==========================================================
    # OPTIONAL STATE-BASED DEPENDENCY DISCOVERY
    # ==========================================================

    def _record_dependencies_from_state(
        self,
        langgraph_node: str,
        state: Any,
    ) -> None:
        """
        Backward-compatible convenience discovery from common state
        dependency fields.

        This is only used when no explicit dependency_resolver is
        supplied to wrap_node().
        """

        if not isinstance(state, dict):
            return

        target_id = self._ensure_runtime_node(
            langgraph_node
        )

        candidates: list[Any] = []

        for key in (
            "dependencies",
            "belief_dependencies",
            "_belief_dependencies",
            "langgraph_dependencies",
            "depends_on",
        ):
            value = state.get(key)

            if isinstance(value, dict):
                if langgraph_node in value:
                    candidates.append(
                        value[langgraph_node]
                    )
            elif key == "depends_on":
                candidates.append(value)

        for key in (
            "upstream_nodes",
            "dependency_nodes",
            "upstream",
        ):
            if key in state:
                candidates.append(
                    state[key]
                )

        for group in candidates:
            if group is None:
                continue

            if isinstance(group, str):
                group = [group]

            if isinstance(group, dict):
                group = [group]

            if not isinstance(group, (list, tuple, set)):
                continue

            for item in group:
                source = item
                edge_type = DependencyType.REQUIRES

                if isinstance(item, dict):
                    source = (
                        item.get("node")
                        or item.get("source")
                        or item.get("langgraph_node")
                        or item.get("belief_node_id")
                    )

                    raw_type = item.get(
                        "dependency_type"
                    )

                    if raw_type is not None:
                        try:
                            edge_type = (
                                raw_type
                                if isinstance(
                                    raw_type,
                                    DependencyType,
                                )
                                else DependencyType(raw_type)
                            )
                        except ValueError as exc:
                            raise ValueError(
                                f"Unknown dependency type: "
                                f"{raw_type}"
                            ) from exc

                if not isinstance(source, str):
                    continue

                source_id = self._resolve_dependency_source(
                    source=source,
                    state=state,
                )

                self.belief_graph.graph.add_dependency(
                    source_id=source_id,
                    target_id=target_id,
                    dependency_type=edge_type,
                )

    # ==========================================================
    # NODE WRAPPING
    # ==========================================================

    def wrap_node(
        self,
        langgraph_node: str,
        fn: Callable[..., Any],
        dependency_resolver: Callable[[Any], Iterable[Any]] | None = None,
        dependency_type: DependencyType = DependencyType.REQUIRES,
    ) -> Callable[..., Any]:
        """
        Wrap a LangGraph node function.

        Explicit runtime dependency mode:

            wrapped = adapter.wrap_node(
                langgraph_node="reason",
                fn=reason,
                dependency_resolver=resolve_dependencies,
                dependency_type=DependencyType.REQUIRES,
            )

        The resolver runs immediately before the actual node function.
        Its returned sources become Belief-Graph dependency edges.
        """

        self._ensure_runtime_node(
            langgraph_node
        )

        if dependency_resolver is not None and not callable(
            dependency_resolver
        ):
            raise TypeError(
                "dependency_resolver must be callable "
                "when provided."
            )

        if iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(
                *args: Any,
                **kwargs: Any,
            ) -> Any:
                state = self._extract_state(
                    args=args,
                    kwargs=kwargs,
                )

                if dependency_resolver is not None:
                    self._record_dependencies_from_resolver(
                        langgraph_node=langgraph_node,
                        state=state,
                        dependency_resolver=dependency_resolver,
                        dependency_type=dependency_type,
                    )
                else:
                    self._record_dependencies_from_state(
                        langgraph_node=langgraph_node,
                        state=state,
                    )

                return await fn(
                    *args,
                    **kwargs,
                )

            return async_wrapper

        @wraps(fn)
        def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            state = self._extract_state(
                args=args,
                kwargs=kwargs,
            )

            if dependency_resolver is not None:
                self._record_dependencies_from_resolver(
                    langgraph_node=langgraph_node,
                    state=state,
                    dependency_resolver=dependency_resolver,
                    dependency_type=dependency_type,
                )
            else:
                self._record_dependencies_from_state(
                    langgraph_node=langgraph_node,
                    state=state,
                )

            return fn(
                *args,
                **kwargs,
            )

        return wrapper

    # ==========================================================
    # IMPACT ANALYSIS
    # ==========================================================

    def analyze_impact(
        self,
        changed_langgraph_nodes: Iterable[str],
    ) -> dict[str, Any]:
        """
        Analyze impact for LangGraph node names or Belief-Graph IDs.
        """

        changed_node_ids = [
            self._resolve_node_id(node)
            for node in changed_langgraph_nodes
        ]

        return self.belief_graph.analyze_impact(
            changed_node_ids
        )

    # ==========================================================
    # STATUS
    # ==========================================================

    def status(
        self,
        langgraph_node: str | None = None,
        node_id: str | None = None,
    ) -> NodeStatus:
        """
        Get status using either a LangGraph node name or a
        Belief-Graph node ID.

        Examples:

            adapter.status("reason")
            adapter.status("B2")
            adapter.status(node_id="B2")
        """

        if (
            langgraph_node is not None
            and node_id is not None
        ):
            raise ValueError(
                "Provide either langgraph_node or node_id, "
                "not both."
            )

        if node_id is not None:
            if node_id not in self.graph.graph.nodes:
                raise ValueError(
                    f"Unknown Belief-Graph node: {node_id}"
                )

            return self.belief_graph.status(
                node_id
            )

        if langgraph_node is None:
            raise ValueError(
                "Provide either langgraph_node or node_id."
            )

        if langgraph_node in self._node_map:
            return self.belief_graph.status(
                self._node_map[langgraph_node]
            )

        # Recovery can create new Belief-Graph nodes (e.g. B2) after
        # adapter initialization. Resolve those directly.
        if langgraph_node in self.graph.graph.nodes:
            return self.belief_graph.status(
                langgraph_node
            )

        raise ValueError(
            "Unknown LangGraph or Belief-Graph node: "
            f"{langgraph_node}"
        )

    # ==========================================================
    # NODE ACCESS
    # ==========================================================

    def get(
        self,
        langgraph_node: str | None = None,
        node_id: str | None = None,
    ):
        """
        Get a Belief-Graph node using either namespace.
        """

        if (
            langgraph_node is not None
            and node_id is not None
        ):
            raise ValueError(
                "Provide either langgraph_node or node_id, "
                "not both."
            )

        if node_id is not None:
            resolved_id = self._resolve_node_id(
                node_id
            )
        elif langgraph_node is not None:
            resolved_id = self._resolve_node_id(
                langgraph_node
            )
        else:
            raise ValueError(
                "Provide either langgraph_node or node_id."
            )

        return self.belief_graph.get(
            resolved_id
        )

    # ==========================================================
    # GRAPH ACCESS
    # ==========================================================

    @property
    def graph(self):
        """
        Return the underlying Belief-Graph.

        This is deliberately not the LangGraph execution graph.
        """

        return self.belief_graph.graph
