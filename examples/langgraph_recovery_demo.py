from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.environment import DynamicAPIEnvironment
from app.langgraph_adapter import LangGraphAdapter
from app.models import DependencyType, NodeStatus, NodeType
from app.recovery import RecoveryEngine


class AgentState(TypedDict):
    task: str
    api_version: str
    result: str
    api_ok: bool
    last_producer: str | None


def print_header(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_status(
    adapter: LangGraphAdapter,
    node_id: str,
    label: str,
) -> None:
    status = adapter.status(node_id)

    print(
        f"{node_id:<4} "
        f"{label:<12} "
        f"{status.value}"
    )


def main() -> None:
    print_header("BELIEF-GRAPH + LANGGRAPH")
    print("Dependency-aware belief revision and selective recovery")

    # =========================================================
    # ENVIRONMENT + ADAPTER
    # =========================================================

    environment = DynamicAPIEnvironment()
    adapter = LangGraphAdapter()

    # The LangGraph adapter owns the real AgentRuntime.
    runtime = adapter.belief_graph.runtime

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
        value="v1",
    )

    # ---------------------------------------------------------
    # UNRELATED BRANCH
    # ---------------------------------------------------------

    adapter.register_node(
        langgraph_node="report_belief",
        belief_node_id="B3",
        node_type=NodeType.BELIEF,
        content="Reporting database is available",
        value=True,
    )

    adapter.register_node(
        langgraph_node="report_reason",
        belief_node_id="C3",
        node_type=NodeType.CONCLUSION,
        content="Reporting data can be generated",
    )

    adapter.register_node(
        langgraph_node="report_plan",
        belief_node_id="P3",
        node_type=NodeType.PLAN,
        content="Generate reporting data",
    )

    adapter.add_dependency(
    "report_belief",
    "report_reason",
    DependencyType.REQUIRES,
    )
    adapter.add_dependency(
    "report_reason",
    "report_plan",
    DependencyType.REQUIRES,
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
        # Execute the real AgentRuntime action.
        #
        # This means the demo is not merely simulating failure:
        # A1 actually consults belief B1 and calls the environment.
        action_result = runtime.execute_api_action(
            environment=environment,
            belief_id="B1",
            action_id="A1",
        )

        environment_result = action_result[
            "environment_result"
        ]

        if not environment_result["success"]:
            return {
                "api_ok": False,
                "result": (
                    state["result"]
                    + " -> stale action"
                ),
                "last_producer": "act",
            }

        return {
            "api_ok": True,
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
    # ORIGINAL GRAPH
    # =========================================================

    print_header("INITIAL BELIEF GRAPH")

    print("B1 -> C1 -> P1 -> A1")
    print(" ")
    print("B3 -> C3 -> P3")
    print(" ")
    print("B3/C3/P3 form an unrelated branch.")

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

    print()
    print(
        "Status                  : "
        + (
            "SUCCESS"
            if first_run["api_ok"]
            else "FAILURE"
        )
    )

    assert first_run["api_ok"] is True

    # =========================================================
    # RUNTIME DEPENDENCIES
    # =========================================================

    print_header("RUNTIME DEPENDENCIES CAPTURED")

    dependencies = [
        ("B1", "C1"),
        ("C1", "P1"),
        ("P1", "A1"),
        ("B3", "C3"),
        ("C3", "P3"),
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
        "Reality changed from v1 to v2,"
        " but the agent still believes v1."
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

    assert second_run["api_ok"] is False

    # =========================================================
    # BELIEF-GRAPH IMPACT ANALYSIS
    # =========================================================

    print_header("BELIEF-GRAPH IMPACT ANALYSIS")

    impact = adapter.analyze_impact(
        ["retrieve"]
    )

    print("Changed belief:")
    print("B1  [BELIEF]  API version v1 is available")

    print()
    print("Propagation through the dependency graph:")

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

    max_depth = max(
        details["depth"]
        for details in impact.values()
    )

    print()
    print(
        "Affected nodes      : "
        f"{len(impact)}"
    )

    print(
        "Propagation depth    : "
        f"{max_depth}"
    )

    # =========================================================
    # REAL RECOVERY ENGINE
    # =========================================================

    print_header("RECOVERY ENGINE")

    print("Failure detected in : A1")
    print("Observed reality    : API version v2")
    print("Stale belief        : B1 = v1")
    print()
    print("Starting recovery...")

    recovery = RecoveryEngine(runtime)

    action_result = runtime.execute_api_action(
        environment=environment,
        belief_id="B1",
        action_id="A1",
    )

    assert (
        action_result["environment_result"]["success"]
        is False
    )

    recovery_result = (
        recovery.recover_from_action_failure(
            action_result=action_result,
            evidence_id="E1",
            new_belief_id="B2",
            new_action_id="A2",
        )
    )

    # =========================================================
    # REVISION
    # =========================================================

    print_header("BELIEF REVISION")

    revision = recovery_result["revision"]

    print(
        f"Old belief : "
        f"{revision['old_belief']}"
    )

    print(
        f"New belief : "
        f"{revision['new_belief']}"
    )

    print(
        "New belief value : "
        f"{runtime.graph.get_node('B2').value}"
    )

    print()
    print(
        "B1 is now superseded by B2."
    )

    # =========================================================
    # REVISION EVENT
    # =========================================================

    event = recovery_result["event"]

    print_header("REVISION EVENT")

    print("Event ID       :", event.event_id)
    print("Conflict       :", event.conflict_id)
    print("Old belief     :", event.old_belief_id)
    print("New belief     :", event.new_belief_id)
    print("Old action     :", event.old_action_id)
    print("New action     :", event.new_action_id)

    print()
    print(
        "Affected nodes : "
        + ", ".join(event.affected_nodes)
    )

    print(
        "Invalidated    : "
        + ", ".join(event.invalidated_nodes)
    )

    if event.reevaluation_nodes:
        print(
            "Re-evaluation  : "
            + ", ".join(event.reevaluation_nodes)
        )

    if event.uncertain_nodes:
        print(
            "Uncertain      : "
            + ", ".join(event.uncertain_nodes)
        )

    # =========================================================
    # RECOVERY PLAN
    # =========================================================

    recovery_plan = recovery_result[
        "recovery_plan"
    ]

    print_header("SELECTIVE RECOVERY PLAN")

    print(
        "Affected nodes:"
    )

    for node_id in recovery_plan[
        "affected_nodes"
    ]:
        print(f"  - {node_id}")

    print()
    print("Nodes requiring replanning:")

    for node_id in recovery_plan[
        "replan_nodes"
    ]:
        print(f"  - {node_id}")

    print()
    print("Preserved nodes:")

    for node_id in recovery_plan[
        "preserved_nodes"
    ]:
        print(f"  - {node_id}")

    # =========================================================
    # RECOVERED ACTION
    # =========================================================

    new_action = recovery_result.get(
        "new_action"
    )

    print_header("RECOVERED ACTION")

    if new_action is None:
        raise RuntimeError(
            "Recovery did not create a replacement action."
        )

    print("Created action :", new_action.id)
    print("Content        :", new_action.content)
    print("Status         :", new_action.status.value)

    assert new_action.id == "A2"

    # =========================================================
    # EXECUTE RECOVERED ACTION
    # =========================================================

    print_header("EXECUTING RECOVERED ACTION")

    second_action_result = (
        runtime.execute_api_action(
            environment=environment,
            belief_id="B2",
            action_id=new_action.id,
        )
    )

    recovered_environment_result = (
        second_action_result["environment_result"]
    )

    print(
    "Environment API version : "
    f"{environment.get_api_version()}"
    )

    print(
    "Recovered belief value : "
    f"{runtime.graph.get_node('B2').value}"
    )

    print(
    "Recovered action value : "
    f"{runtime.graph.get_node('A2').value}"
    )

    print(
        "Execution success     : "
        + (
            "YES"
            if recovered_environment_result["success"]
            else "NO"
        )
    )

    assert (
        recovered_environment_result["success"]
        is True
    )

    # =========================================================
    # FINAL STATE
    # =========================================================

    print_header("FINAL BELIEF-GRAPH STATE")

    print_status(
        adapter,
        "B1",
        "old belief",
    )

    print_status(
        adapter,
        "C1",
        "conclusion",
    )

    print_status(
        adapter,
        "P1",
        "old plan",
    )

    print_status(
        adapter,
        "A1",
        "old action",
    )

    print_status(
        adapter,
        "B2",
        "new belief",
    )

    print_status(
        adapter,
        "A2",
        "new action",
    )

    print()
    print("Unrelated branch:")

    print_status(
        adapter,
        "B3",
        "unrelated belief",
    )

    print_status(
        adapter,
        "C3",
        "unrelated conclusion",
    )

    print_status(
        adapter,
        "P3",
        "unrelated plan",
    )

    # =========================================================
    # SELECTIVE RECOVERY VERIFICATION
    # =========================================================

    print_header("SELECTIVE RECOVERY VERIFICATION")

    original_branch = {
        "B1",
        "C1",
        "P1",
        "A1",
    }

    unrelated_branch = {
        "B3",
        "C3",
        "P3",
    }

    preserved_nodes = set(
        recovery_plan.get(
            "preserved_nodes",
            [],
        )
    )

    preserved_original_nodes = (
        preserved_nodes & original_branch
    )

    unnecessary_invalidations = (
        set(event.invalidated_nodes)
        & unrelated_branch
    )

    print(
        "Original affected branch : "
        + " -> ".join(
            ["B1", "C1", "P1", "A1"]
        )
    )

    print(
        "Preserved unrelated     : "
        + ", ".join(
            sorted(
                preserved_original_nodes
                if preserved_original_nodes
                else unrelated_branch
            )
        )
    )

    print(
        "Unrelated invalidations : "
        + (
            "0"
            if not unnecessary_invalidations
            else ", ".join(
                sorted(
                    unnecessary_invalidations
                )
            )
        )
    )

    assert adapter.status("B1") == NodeStatus.INVALID
    assert adapter.status("C1") == NodeStatus.INVALID
    assert adapter.status("P1") == NodeStatus.INVALID
    assert adapter.status("A1") == NodeStatus.INVALID

    assert adapter.status("B2") == NodeStatus.ACTIVE
    assert adapter.status("A2") == NodeStatus.ACTIVE

    assert adapter.status("B3") == NodeStatus.ACTIVE
    assert adapter.status("C3") == NodeStatus.ACTIVE
    assert adapter.status("P3") == NodeStatus.ACTIVE

    assert not unnecessary_invalidations

    # =========================================================
    # FINAL RESULT
    # =========================================================

    print_header("END-TO-END RECOVERY RESULT")

    print("Initial world       : API v1")
    print("Changed reality     : API v2")
    print("Initial action      : A1")
    print("Initial action      : FAILED")
    print("Belief revision     : B1 -> B2")
    print("Selective impact    : COMPLETED")
    print("Recovery action     : A2")
    print("Recovered execution : SUCCESS")
    print("Unrelated branch    : PRESERVED")

    print()
    print(
        "The agent did not restart the entire reasoning graph."
    )
    print(
        "It identified the dependency region affected by "
        "the changed belief and replaced only the stale action path."
    )

    print_header("DEMO COMPLETE")


if __name__ == "__main__":
    main()