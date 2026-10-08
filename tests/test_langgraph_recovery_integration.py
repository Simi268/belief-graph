from langgraph.graph import END, START, StateGraph
from typing import TypedDict

from app.environment import DynamicAPIEnvironment
from app.langgraph_adapter import LangGraphAdapter
from app.models import DependencyType, NodeType, NodeStatus
from app.recovery import RecoveryEngine


class AgentState(TypedDict):
    task: str
    result: str


def test_langgraph_adapter_uses_real_recovery_engine():
    environment = DynamicAPIEnvironment()
    adapter = LangGraphAdapter()

    # =========================================================
    # ORIGINAL REASONING CHAIN
    # =========================================================

    adapter.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        value="v1",
        )

    adapter.register_node(
        langgraph_node="reason",
        belief_node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="Customer data can be retrieved",
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

    # Unrelated branch.
    adapter.register_node(
        langgraph_node="report",
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

    adapter.add_dependencies(
        [
            ("retrieve", "reason", DependencyType.REQUIRES),
            ("reason", "plan", DependencyType.REQUIRES),
            ("plan", "act", DependencyType.REQUIRES),
            ("report", "report_reason", DependencyType.REQUIRES),
            ("report_reason", "report_plan", DependencyType.REQUIRES),
        ]
    )

    # =========================================================
    # REAL LANGGRAPH
    # =========================================================

    def retrieve(state: AgentState):
        return {
            "result": "retrieval attempted",
        }

    def reason(state: AgentState):
        return {
            "result": state["result"] + " -> reasoned",
        }

    def plan(state: AgentState):
        return {
            "result": state["result"] + " -> planned",
        }

    def act(state: AgentState):
        return {
            "result": state["result"] + " -> acted",
        }

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

    result = graph.invoke(
        {
            "task": "retrieve customer data",
            "result": "",
        }
    )

    assert result["result"] == (
        "retrieval attempted -> reasoned -> planned -> acted"
    )

    # =========================================================
    # ENVIRONMENT CHANGES
    # =========================================================

    environment.set_api_version("v2")

    # =========================================================
    # REAL AGENT RUNTIME ACTION FAILURE
    # =========================================================

    runtime = adapter.belief_graph.runtime

    action_result = runtime.execute_api_action(
        environment=environment,
        belief_id="B1",
        action_id="A1",
    )

    assert action_result["environment_result"]["success"] is False

    # =========================================================
    # REAL RECOVERY ENGINE
    # =========================================================

    recovery = RecoveryEngine(runtime)

    recovery_result = (
        recovery.recover_from_action_failure(
            action_result=action_result,
            evidence_id="E1",
            new_belief_id="B2",
            new_action_id="A2",
        )
    )

    assert recovery_result["status"] == "recovered"

    new_action = recovery_result["new_action"]
    event = recovery_result["event"]

    assert new_action is not None
    assert new_action.id == "A2"

    # New belief is active.
    assert adapter.status("B2") == NodeStatus.ACTIVE

    # Old reasoning is invalidated.
    assert adapter.status("B1") == NodeStatus.INVALID
    assert adapter.status("C1") == NodeStatus.INVALID
    assert adapter.status("P1") == NodeStatus.INVALID
    assert adapter.status("A1") == NodeStatus.INVALID

    # Unrelated branch remains untouched.
    assert adapter.status("B3") == NodeStatus.ACTIVE
    assert adapter.status("C3") == NodeStatus.ACTIVE
    assert adapter.status("P3") == NodeStatus.ACTIVE

    # Recovery event records selective impact.
    assert "B1" in event.invalidated_nodes
    assert "A1" in event.invalidated_nodes
    assert "B2" in event.affected_nodes

    # =========================================================
    # EXECUTE THE RECOVERED ACTION
    # =========================================================

    recovered_action_result = runtime.execute_api_action(
        environment=environment,
        belief_id="B2",
        action_id="A2",
    )

    assert (
        recovered_action_result["environment_result"]["success"]
        is True
    )