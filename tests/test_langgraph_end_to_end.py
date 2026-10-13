from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.environment import DynamicAPIEnvironment
from app.langgraph_adapter import LangGraphAdapter
from app.models import DependencyType, NodeType


class AgentState(TypedDict):
    task: str
    api_version: str
    result: str
    api_ok: bool
    last_producer: str | None


def test_langgraph_agent_and_belief_graph_end_to_end():
    environment = DynamicAPIEnvironment()
    adapter = LangGraphAdapter()

    # ---------------------------------------------------------
    # Belief-Graph reasoning nodes
    # ---------------------------------------------------------

    adapter.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="API version v1 is available",
        value="v1",
    )

    adapter.register_node(
        langgraph_node="reason",
        belief_node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="Customer data can be retrieved using the API",
    )

    adapter.register_node(
        langgraph_node="plan",
        belief_node_id="P1",
        node_type=NodeType.PLAN,
        content="Retrieve customer data",
    )

    adapter.register_node(
        langgraph_node="act",
        belief_node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1",
    )

    # ---------------------------------------------------------
    # LangGraph runtime functions
    # ---------------------------------------------------------

    def retrieve(state: AgentState):
        result = environment.call_api(
            state["api_version"]
        )

        return {
            "api_ok": result["success"],
            "result": (
                "customer data retrieved"
                if result["success"]
                else "API call failed"
            ),
            "last_producer": "retrieve",
        }

    def reason(state: AgentState):
        if not state["api_ok"]:
            return {
                "result": "reasoning blocked by failed retrieval",
                "last_producer": "reason",
            }

        return {
            "result": state["result"] + " -> reasoned",
            "last_producer": "reason",
        }

    def plan(state: AgentState):
        return {
            "result": state["result"] + " -> planned",
            "last_producer": "plan",
        }

    def act(state: AgentState):
        return {
            "result": state["result"] + " -> executed",
            "last_producer": "act",
        }

    # ---------------------------------------------------------
    # Runtime dependency resolvers
    # ---------------------------------------------------------

    def dependency_from_previous_node(
        state: AgentState,
    ):
        producer = state["last_producer"]

        if producer is None:
            return []

        return [producer]

    # ---------------------------------------------------------
    # Wrap reasoning nodes
    # ---------------------------------------------------------

    wrapped_reason = adapter.wrap_node(
        langgraph_node="reason",
        fn=reason,
        dependency_resolver=dependency_from_previous_node,
        dependency_type=DependencyType.REQUIRES,
    )

    wrapped_plan = adapter.wrap_node(
        langgraph_node="plan",
        fn=plan,
        dependency_resolver=dependency_from_previous_node,
        dependency_type=DependencyType.REQUIRES,
    )

    wrapped_act = adapter.wrap_node(
        langgraph_node="act",
        fn=act,
        dependency_resolver=dependency_from_previous_node,
        dependency_type=DependencyType.REQUIRES,
    )

    # ---------------------------------------------------------
    # Build REAL LangGraph
    # ---------------------------------------------------------

    builder = StateGraph(AgentState)

    builder.add_node("retrieve", retrieve)
    builder.add_node("reason", wrapped_reason)
    builder.add_node("plan", wrapped_plan)
    builder.add_node("act", wrapped_act)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "reason")
    builder.add_edge("reason", "plan")
    builder.add_edge("plan", "act")
    builder.add_edge("act", END)

    graph = builder.compile()

    # =========================================================
    # RUN 1 — ORIGINAL WORLD
    # =========================================================

    first_run = graph.invoke(
        {
            "task": "retrieve customer data",
            "api_version": "v1",
            "result": "",
            "api_ok": False,
            "last_producer": None,
        }
    )

    assert first_run["api_ok"] is True
    assert first_run["result"] == (
        "customer data retrieved -> reasoned -> planned -> executed"
    )

    # Runtime dependencies should now exist.
    assert (
        adapter.graph.get_dependency_type(
            "B1",
            "C1",
        )
        == DependencyType.REQUIRES
    )

    assert (
        adapter.graph.get_dependency_type(
            "C1",
            "P1",
        )
        == DependencyType.REQUIRES
    )

    assert (
        adapter.graph.get_dependency_type(
            "P1",
            "A1",
        )
        == DependencyType.REQUIRES
    )

    # =========================================================
    # ENVIRONMENT CHANGES
    # =========================================================

    environment.set_api_version("v2")

    # =========================================================
    # RUN 2 — OLD BELIEF IS NOW STALE
    # =========================================================

    second_run = graph.invoke(
        {
            "task": "retrieve customer data",
            "api_version": "v1",
            "result": "",
            "api_ok": False,
            "last_producer": None,
        }
    )

    assert second_run["api_ok"] is False
    assert second_run["result"] == (
        "reasoning blocked by failed retrieval"
        " -> planned -> executed"
    )

    # =========================================================
    # BELIEF-GRAPH IMPACT ANALYSIS
    # =========================================================

    impact = adapter.analyze_impact(
        ["retrieve"]
    )

    # The changed belief itself is not part of the
    # downstream impact map.
    assert "B1" not in impact

    # The complete dependent reasoning chain is affected.
    assert set(impact) == {
        "C1",
        "P1",
        "A1",
    }

    assert impact["C1"]["affected_by"] == ["B1"]
    assert impact["P1"]["affected_by"] == ["B1"]
    assert impact["A1"]["affected_by"] == ["B1"]

def test_end_to_end_langgraph_runs_are_isolated():
    from app.runs import RunSession

    run_a = RunSession()
    run_b = RunSession()

    adapter_a = run_a.langgraph_adapter()
    adapter_b = run_b.langgraph_adapter()

    class RunState(TypedDict):
        result: str
        last_producer: str | None

    def retrieve_v1(state: RunState):
        return {
            "result": "Run A retrieved v1 data",
            "last_producer": "retrieve",
        }

    def retrieve_v2(state: RunState):
        return {
            "result": "Run B retrieved v2 data",
            "last_producer": "retrieve",
        }

    def reason(state: RunState):
        return {
            "result": state["result"] + " -> reasoned",
            "last_producer": "reason",
        }

    def dependency_from_previous_node(state: RunState):
        producer = state["last_producer"]
        return [producer] if producer else []

    wrapped_reason_a = adapter_a.wrap_node(
        langgraph_node="reason",
        fn=reason,
        dependency_resolver=dependency_from_previous_node,
        dependency_type=DependencyType.REQUIRES,
    )

    wrapped_reason_b = adapter_b.wrap_node(
        langgraph_node="reason",
        fn=reason,
        dependency_resolver=dependency_from_previous_node,
        dependency_type=DependencyType.REQUIRES,
    )

    builder_a = StateGraph(RunState)
    builder_a.add_node("retrieve", retrieve_v1)
    builder_a.add_node("reason", wrapped_reason_a)
    builder_a.add_edge(START, "retrieve")
    builder_a.add_edge("retrieve", "reason")
    builder_a.add_edge("reason", END)
    graph_a = builder_a.compile()

    builder_b = StateGraph(RunState)
    builder_b.add_node("retrieve", retrieve_v2)
    builder_b.add_node("reason", wrapped_reason_b)
    builder_b.add_edge(START, "retrieve")
    builder_b.add_edge("retrieve", "reason")
    builder_b.add_edge("reason", END)
    graph_b = builder_b.compile()

    result_a = graph_a.invoke(
        {"result": "", "last_producer": None}
    )
    result_b = graph_b.invoke(
        {"result": "", "last_producer": None}
    )

    assert result_a["result"] == (
        "Run A retrieved v1 data -> reasoned"
    )
    assert result_b["result"] == (
        "Run B retrieved v2 data -> reasoned"
    )

    # Each execution records its own dependency.
    assert adapter_a.graph.get_dependency_type(
        "lg::retrieve",
        "lg::reason",
    ) == DependencyType.REQUIRES

    assert adapter_b.graph.get_dependency_type(
        "lg::retrieve",
        "lg::reason",
    ) == DependencyType.REQUIRES

    # The graphs must be independent objects.
    assert adapter_a.graph is not adapter_b.graph

         # Each run has its own independently registered node.
    node_a = adapter_a.graph.get_node("lg::retrieve")
    node_b = adapter_b.graph.get_node("lg::retrieve")

    assert node_a is not node_b
    assert node_a.id == node_b.id == "lg::retrieve"

# The actual execution outputs remain specific to each run.
    assert result_a["result"] == (
        "Run A retrieved v1 data -> reasoned"
        )
    assert result_b["result"] == (
        "Run B retrieved v2 data -> reasoned"
        )

# Running either workflow must not overwrite the other run's graph.
    assert adapter_a.graph is not adapter_b.graph
    assert adapter_a.graph.get_dependency_type(
        "lg::retrieve", "lg::reason"
        ) == DependencyType.REQUIRES
    assert adapter_b.graph.get_dependency_type(
        "lg::retrieve", "lg::reason"
        ) == DependencyType.REQUIRES