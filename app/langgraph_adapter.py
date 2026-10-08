from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .models import DependencyType, NodeType
from .sdk import BeliefGraphSDK


class LangGraphAdapter:
    """
    Bridge between LangGraph execution and Belief-Graph reasoning.

    LangGraph remains responsible for execution flow.

    Belief-Graph remains responsible for:
        belief -> conclusion -> plan -> action
        dependency tracking
        impact analysis
        revision

    The adapter connects the two without making the core engine
    dependent on LangGraph.
    """

    def __init__(
        self,
        belief_graph: BeliefGraphSDK | None = None,
    ):
        self.belief_graph = belief_graph or BeliefGraphSDK()

        # Maps LangGraph node names to Belief-Graph node IDs.
        self._node_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # NODE REGISTRATION
    # ------------------------------------------------------------------

    def register_node(
        self,
        *,
        langgraph_node: str,
        belief_node_id: str,
        node_type: NodeType,
        content: str,
        value: Any = None,
    ):
        """
        Register a LangGraph execution node as a Belief-Graph node.
        """

        if langgraph_node in self._node_map:
            existing = self._node_map[langgraph_node]

            if existing != belief_node_id:
                raise ValueError(
                    f"LangGraph node '{langgraph_node}' is already "
                    f"mapped to '{existing}'."
                )

        self.belief_graph.node(
            node_id=belief_node_id,
            node_type=node_type,
            content=content,
            value=value,
        )

        self._node_map[langgraph_node] = belief_node_id

        return self.belief_graph.get(belief_node_id)

    # ------------------------------------------------------------------
    # DEPENDENCY REGISTRATION
    # ------------------------------------------------------------------

    def add_dependency(
        self,
        *,
        source_langgraph_node: str,
        target_langgraph_node: str,
        dependency_type: DependencyType = DependencyType.REQUIRES,
    ):
        """
        Connect two LangGraph nodes using Belief-Graph semantics.

        The LangGraph edge itself is NOT modified.
        """

        try:
            source_id = self._node_map[source_langgraph_node]
        except KeyError as exc:
            raise ValueError(
                f"Unknown LangGraph node: {source_langgraph_node}"
            ) from exc

        try:
            target_id = self._node_map[target_langgraph_node]
        except KeyError as exc:
            raise ValueError(
                f"Unknown LangGraph node: {target_langgraph_node}"
            ) from exc

        return self.belief_graph.depends_on(
            source_id,
            target_id,
            dependency_type,
        )

    # ------------------------------------------------------------------
    # BULK DEPENDENCY REGISTRATION
    # ------------------------------------------------------------------

    def add_dependencies(
        self,
        dependencies: Iterable[
            tuple[str, str, DependencyType]
        ],
    ):
        """
        Register multiple reasoning dependencies.

        Each item is:

            (
                source_langgraph_node,
                target_langgraph_node,
                dependency_type,
            )
        """

        registered = []

        for (
            source_langgraph_node,
            target_langgraph_node,
            dependency_type,
        ) in dependencies:
            registered.append(
                self.add_dependency(
                    source_langgraph_node=source_langgraph_node,
                    target_langgraph_node=target_langgraph_node,
                    dependency_type=dependency_type,
                )
            )

        return registered

    # ------------------------------------------------------------------
    # NODE WRAPPING
    # ------------------------------------------------------------------

    def wrap_node(
        self,
        *,
        langgraph_node: str,
        fn: Callable[..., Any],
        belief_node_id: str | None = None,
        node_type: NodeType = NodeType.CONCLUSION,
        content: str | None = None,
        dependency_resolver: Callable[
            [Any], Iterable[str]
        ] | None = None,
        dependency_type: DependencyType = DependencyType.REQUIRES,
    ):
        """
        Wrap a LangGraph node function.

        The wrapped function:

        1. optionally discovers dependencies from runtime state
        2. records those dependencies in Belief-Graph
        3. executes the original LangGraph node
        4. returns the original result unchanged

        If the LangGraph node is already mapped to a
        Belief-Graph node, that existing mapping is reused.
        """

        # --------------------------------------------------------------
        # Resolve existing Belief-Graph mapping
        # --------------------------------------------------------------

        existing_belief_node_id = self._node_map.get(
            langgraph_node
        )

        if existing_belief_node_id is not None:

            # If a caller explicitly supplies another ID,
            # do not silently remap an existing node.
            if (
                belief_node_id is not None
                and belief_node_id != existing_belief_node_id
            ):
                raise ValueError(
                    f"LangGraph node '{langgraph_node}' is already "
                    f"mapped to '{existing_belief_node_id}'."
                )

            resolved_belief_node_id = existing_belief_node_id

        else:
            resolved_belief_node_id = (
                belief_node_id
                or f"lg::{langgraph_node}"
            )

            self.register_node(
                langgraph_node=langgraph_node,
                belief_node_id=resolved_belief_node_id,
                node_type=node_type,
                content=(
                    content
                    or f"LangGraph node: {langgraph_node}"
                ),
            )

        # --------------------------------------------------------------
        # Wrapped runtime function
        # --------------------------------------------------------------

        def wrapped(*args, **kwargs):
            if dependency_resolver is not None:
                state = (
                    args[0]
                    if args
                    else kwargs.get("state")
                )

                dependencies = dependency_resolver(
                    state
                )

                for source_langgraph_node in dependencies:
                    self.add_dependency(
                        source_langgraph_node=source_langgraph_node,
                        target_langgraph_node=langgraph_node,
                        dependency_type=dependency_type,
                    )

            return fn(*args, **kwargs)

        return wrapped

    # ------------------------------------------------------------------
    # IMPACT ANALYSIS
    # ------------------------------------------------------------------

    def analyze_impact(
        self,
        changed_langgraph_nodes: Iterable[str],
    ):
        """
        Run Belief-Graph impact analysis using LangGraph node names.
        """

        changed_belief_ids = []

        for langgraph_node in changed_langgraph_nodes:
            try:
                changed_belief_ids.append(
                    self._node_map[langgraph_node]
                )
            except KeyError as exc:
                raise ValueError(
                    f"Unknown LangGraph node: {langgraph_node}"
                ) from exc

        return self.belief_graph.analyze_impact(
            changed_belief_ids
        )
    
    # ------------------------------------------------------------------
    # RAW GRAPH ACCESS
    # ------------------------------------------------------------------

    @property
    def graph(self):
        """
        Access the underlying Belief-Graph.

        This is an escape hatch for advanced integrations and tests.
        Normal callers should prefer the adapter methods.
        """
        return self.belief_graph.graph

    # ------------------------------------------------------------------
    # LOOKUP
    # ------------------------------------------------------------------

    def belief_node_id(
        self,
        langgraph_node: str,
    ) -> str:
        try:
            return self._node_map[langgraph_node]
        except KeyError as exc:
            raise ValueError(
                f"Unknown LangGraph node: {langgraph_node}"
            ) from exc