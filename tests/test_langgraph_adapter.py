from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.langgraph_adapter import LangGraphAdapter
from app.models import DependencyType, NodeType


class AgentState(TypedDict):
    task: str
    result: str


def test_langgraph_adapter_tracks_reasoning_dependencies():
    adapter = LangGraphAdapter()

    # ---------------------------------------------------------
    # Register reasoning nodes
    # ---------------------------------------------------------

    adapter.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="Relevant information is available",
    )

    adapter.register_node(
        langgraph_node="reason",
        belief_node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="The retrieved information supports the task",
    )

    adapter.register_node(
        langgraph_node="plan",
        belief_node_id="P1",
        node_type=NodeType.PLAN,
        content="Use the retrieved information",
    )

    adapter.register_node(
        langgraph_node="act",
        belief_node_id="A1",
        node_type=NodeType.ACTION,
        content="Execute the task",
    )

    # ---------------------------------------------------------
    # Register Belief-Graph dependencies
    # ---------------------------------------------------------

    adapter.add_dependencies(
        [
            ("retrieve", "reason", DependencyType.REQUIRES),
            ("reason", "plan", DependencyType.REQUIRES),
            ("plan", "act", DependencyType.REQUIRES),
        ]
    )

    # ---------------------------------------------------------
    # LangGraph execution nodes
    # ---------------------------------------------------------

    def retrieve(state: AgentState):
        return {"result": "information"}

    def reason(state: AgentState):
        return {"result": state["result"] + " -> reasoned"}

    def plan(state: AgentState):
        return {"result": state["result"] + " -> planned"}

    def act(state: AgentState):
        return {"result": state["result"] + " -> executed"}

    # ---------------------------------------------------------
    # Build REAL LangGraph
    # ---------------------------------------------------------

    builder = StateGraph(AgentState)

    builder.add_node("retrieve", retrieve)
    builder.add_node("reason", reason)
    builder.add_node("plan", plan)
    builder.add_node("act", act)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "reason")
    builder.add_edge("reason", "plan")
    builder.add_edge("plan", "act")
    builder.add_edge("act", END)

    graph = builder.compile()

    # ---------------------------------------------------------
    # Execute
    # ---------------------------------------------------------

    result = graph.invoke(
        {
            "task": "test task",
            "result": "",
        }
    )

    assert result["result"] == (
        "information -> reasoned -> planned -> executed"
    )

    # ---------------------------------------------------------
    # Verify Belief-Graph separately
    # ---------------------------------------------------------

    assert adapter.belief_graph.get("B1").content == (
        "Relevant information is available"
    )

    assert adapter.belief_graph.get("C1").content == (
        "The retrieved information supports the task"
    )

    impact = adapter.analyze_impact(["retrieve"])

    # The changed/root node itself is not part of
    # the downstream impact map.
    assert "B1" not in impact

    # All downstream reasoning nodes are impacted.
    assert "C1" in impact
    assert "P1" in impact
    assert "A1" in impact

    # The original belief is recorded as the cause.
    assert impact["C1"]["affected_by"] == ["B1"]
    assert impact["P1"]["affected_by"] == ["B1"]
    assert impact["A1"]["affected_by"] == ["B1"]


def test_runtime_wrapper_captures_dependency_from_state():
    adapter = LangGraphAdapter()

    # ---------------------------------------------------------
    # Belief-Graph nodes
    # ---------------------------------------------------------

    adapter.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="Relevant information was retrieved",
    )

    adapter.register_node(
        langgraph_node="reason",
        belief_node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="The retrieved information supports the task",
    )

    # ---------------------------------------------------------
    # Actual LangGraph node
    # ---------------------------------------------------------

    def reason(state: AgentState):
        return {
            "result": state["result"] + " -> reasoned"
        }

    # ---------------------------------------------------------
    # Runtime dependency resolver
    # ---------------------------------------------------------

    def resolve_dependencies(state: AgentState):
        if state["result"] == "information":
            return ["retrieve"]

        return []

    wrapped_reason = adapter.wrap_node(
        langgraph_node="reason",
        fn=reason,
        dependency_resolver=resolve_dependencies,
        dependency_type=DependencyType.REQUIRES,
    )

    # ---------------------------------------------------------
    # Build REAL LangGraph
    # ---------------------------------------------------------

    def retrieve(state: AgentState):
        return {
            "result": "information"
        }

    builder = StateGraph(AgentState)

    builder.add_node("retrieve", retrieve)
    builder.add_node("reason", wrapped_reason)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "reason")
    builder.add_edge("reason", END)

    graph = builder.compile()

    # ---------------------------------------------------------
    # Execute
    # ---------------------------------------------------------

    result = graph.invoke(
        {
            "task": "runtime dependency test",
            "result": "",
        }
    )

    assert result["result"] == (
        "information -> reasoned"
    )

    # ---------------------------------------------------------
    # Verify runtime dependency was captured
    # ---------------------------------------------------------

    assert (
        adapter.graph.get_dependency_type(
            "B1",
            "C1",
        )
        == DependencyType.REQUIRES
    )

    # ---------------------------------------------------------
    # Verify impact analysis sees the captured dependency
    # ---------------------------------------------------------

    impact = adapter.analyze_impact(["retrieve"])

    assert "C1" in impact
    assert impact["C1"]["affected_by"] == ["B1"]

    def test_langgraph_adapters_isolate_dependencies_between_runs():
        from app.runs import RunSession

        run_a = RunSession()
        run_b = RunSession()

        adapter_a = LangGraphAdapter(belief_graph=run_a.sdk)
        adapter_b = LangGraphAdapter(belief_graph=run_b.sdk)
        # Register identical node IDs in separate runs.
        for adapter in (adapter_a, adapter_b):
            adapter.register_node(
                langgraph_node="retrieve",
                belief_node_id="B1",
                node_type=NodeType.BELIEF,
                content="Retrieved information",
                )
            adapter.register_node(
                langgraph_node="reason",
                belief_node_id="C1",
                node_type=NodeType.CONCLUSION,
                content="Reasoning based on retrieved information",
                )

    # Add a dependency only to Run A.
            adapter_a.add_dependency(
                "retrieve",
                "reason",
                DependencyType.REQUIRES,
                )

    # Run A contains the dependency.
            assert (
                adapter_a.graph.get_dependency_type("B1", "C1")
                == DependencyType.REQUIRES
                )

    # Run B must not inherit Run A's dependency.
            assert (
                adapter_b.graph.get_dependency_type("B1", "C1")
                is None
                )


def test_langgraph_adapters_isolate_dependencies_between_runs():
    from app.runs import RunSession

    run_a = RunSession()
    run_b = RunSession()

    adapter_a = LangGraphAdapter(belief_graph=run_a.sdk)
    adapter_b = LangGraphAdapter(belief_graph=run_b.sdk)

    # Register identical nodes in both runs.
    for adapter in (adapter_a, adapter_b):
        adapter.register_node(
            langgraph_node="retrieve",
            belief_node_id="B1",
            node_type=NodeType.BELIEF,
            content="Retrieved information",
        )

        adapter.register_node(
            langgraph_node="reason",
            belief_node_id="C1",
            node_type=NodeType.CONCLUSION,
            content="Reasoning based on retrieved information",
        )

    # Add a dependency only to Run A.
    adapter_a.add_dependency(
        "retrieve",
        "reason",
        DependencyType.REQUIRES,
    )

    # Run A must contain the dependency.
    assert (
        adapter_a.graph.get_dependency_type("B1", "C1")
        == DependencyType.REQUIRES
    )

    # Run B must not inherit Run A's dependency.
    # Run B must not inherit Run A's dependency.
    assert not adapter_b.graph.graph.has_edge("B1", "C1")


def test_missing_dependency_is_not_detected_by_impact_analysis():
    adapter = LangGraphAdapter()
    adapter.register_node(langgraph_node="retrieve", belief_node_id="B1", node_type=NodeType.BELIEF, content="Deployment environment is staging")
    adapter.register_node(langgraph_node="plan", belief_node_id="P1", node_type=NodeType.PLAN, content="Deploy to staging")
    impact = adapter.analyze_impact(["retrieve"])
    assert "P1" not in impact
