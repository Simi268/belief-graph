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