from __future__ import annotations

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


def print_header(title: str) -> None:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


def main() -> None:
    print_header("BELIEF-GRAPH + LANGGRAPH DEMO")

    environment = DynamicAPIEnvironment()
    adapter = LangGraphAdapter()

    # =========================================================
    # BELIEF-GRAPH NODES
    # =========================================================

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

    # =========================================================
    # LANGGRAPH NODES
    # =========================================================

    def retrieve(state: AgentState):
        result = environment.call_api(
            state["api_version"]
        )

        if result["success"]:
            return {
                "api_ok": True,
                "result": "customer data retrieved",
                "last_producer": "retrieve",
            }

        return {
            "api_ok": False,
            "result": (
                "API call failed "
                f"(expected {result['expected']}, "
                f"received {result['received']})"
            ),
            "last_producer": "retrieve",
        }

    def reason(state: AgentState):
        if not state["api_ok"]:
            return {
                "result": (
                    state["result"]
                    + " -> reasoning blocked"
                ),
                "last_producer": "reason",
            }

        return {
            "result": (
                state["result"]
                + " -> reasoned"
            ),
            "last_producer": "reason",
        }

    def plan(state: AgentState):
        if not state["api_ok"]:
            return {
                "result": (
                    state["result"]
                    + " -> stale plan"
                ),
                "last_producer": "plan",
            }

        return {
            "result": (
                state["result"]
                + " -> planned"
            ),
            "last_producer": "plan",
        }

    def act(state: AgentState):
        if not state["api_ok"]:
            return {
                "result": (
                    state["result"]
                    + " -> stale action"
                ),
                "last_producer": "act",
            }

        return {
            "result": (
                state["result"]
                + " -> executed"
            ),
            "last_producer": "act",
        }

    # =========================================================
    # RUNTIME DEPENDENCY RESOLUTION
    # =========================================================

    def dependency_from_previous_node(
        state: AgentState,
    ):
        producer = state["last_producer"]

        if producer is None:
            return []

        return [producer]

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

    # =========================================================
    # BUILD LANGGRAPH
    # =========================================================

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

    print_header("RUN 1 — ORIGINAL ENVIRONMENT")

    print("Environment API version :", environment.api_version)
    print("Agent belief            : v1")
    print("Task                    : Retrieve customer data")

    first_run = graph.invoke(
        {
            "task": "Retrieve customer data",
            "api_version": "v1",
            "result": "",
            "api_ok": False,
            "last_producer": None,
        }
    )

    print()
    print("Result:")
    print(first_run["result"])

    if first_run["api_ok"]:
        print("Status                  : SUCCESS")
    else:
        print("Status                  : FAILURE")

    # =========================================================
    # SHOW RECORDED DEPENDENCIES
    # =========================================================

    print_header("RUNTIME DEPENDENCIES CAPTURED")

    dependencies = [
        ("B1", "C1"),
        ("C1", "P1"),
        ("P1", "A1"),
    ]

    for source, target in dependencies:
        dependency_type = (
            adapter.graph.get_dependency_type(
                source,
                target,
            )
        )

        print(
            f"{source} -> {target} "
            f"[{dependency_type.value}]"
        )

    # =========================================================
    # ENVIRONMENT CHANGE
    # =========================================================

    print_header("ENVIRONMENT CHANGE")

    print("Before :", environment.api_version)

    environment.set_api_version("v2")

    print("After  :", environment.api_version)

    print()
    print(
        "The agent still carries the belief "
        "that the API version is v1."
    )

    # =========================================================
    # RUN 2 — STALE BELIEF
    # =========================================================

    print_header("RUN 2 — STALE BELIEF")

    second_run = graph.invoke(
        {
            "task": "Retrieve customer data",
            "api_version": "v1",
            "result": "",
            "api_ok": False,
            "last_producer": None,
        }
    )

    print("Result:")
    print(second_run["result"])

    print()
    print(
        "Status                  : "
        + (
            "SUCCESS"
            if second_run["api_ok"]
            else "FAILURE"
        )
    )

    # =========================================================
    # BELIEF-GRAPH IMPACT ANALYSIS
    # =========================================================

    print_header("BELIEF-GRAPH IMPACT ANALYSIS")

    impact = adapter.analyze_impact(
        ["retrieve"]
    )

    print("Changed node:")
    print("B1  [BELIEF]  API version v1 is available")

    print()
    print("Affected downstream reasoning:")

    ordered_nodes = [
        ("C1", "CONCLUSION"),
        ("P1", "PLAN"),
        ("A1", "ACTION"),
    ]

    for node_id, node_type in ordered_nodes:
        details = impact[node_id]

        print()
        print(
            f"{node_id}  [{node_type}]"
        )
        print(
            f"  impact     : "
            f"{details['impact'].value}"
        )
        print(
            f"  caused by  : "
            f"{', '.join(details['affected_by'])}"
        )
        print(
            f"  depth      : "
            f"{details['depth']}"
        )

    print()
    print(
        "Affected nodes : "
        f"{len(impact)}"
    )

    print(
        "Propagation depth : "
        f"{max(details['depth'] for details in impact.values())}"
    )

    print()
    print("Selective recovery is the next stage.")
    print(
        "The current demo stops after identifying "
        "the affected reasoning region."
    )

    print_header("DEMO COMPLETE")


if __name__ == "__main__":
    main()