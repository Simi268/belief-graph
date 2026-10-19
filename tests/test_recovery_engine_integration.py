from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment
from app.models import DependencyType, NodeType
from app.recovery import RecoveryEngine
from app.semantic_recomputation import SemanticRecomputer


def _build_recovery_runtime():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief(
        "B1",
        "Customer API version is v1",
        value="v1",
    )
    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "Customer data can be retrieved",
    )
    agent.create_node(
        "P1",
        NodeType.PLAN,
        "Retrieve customer data",
    )
    agent.create_node(
        "A1",
        NodeType.ACTION,
        "Call customer API using v1",
    )

    agent.add_dependency("B1", "C1", DependencyType.REQUIRES)
    agent.add_dependency("C1", "P1", DependencyType.REQUIRES)
    agent.add_dependency("P1", "A1", DependencyType.REQUIRES)

    agent.create_belief(
        "B3",
        "Reporting database is available",
        value=True,
    )
    agent.create_node(
        "C3",
        NodeType.CONCLUSION,
        "Reporting data can be generated",
    )
    agent.create_node(
        "P3",
        NodeType.PLAN,
        "Generate reporting data",
    )
    agent.add_dependency("B3", "C3", DependencyType.REQUIRES)
    agent.add_dependency("C3", "P3", DependencyType.REQUIRES)

    environment.set_api_version("v2")
    failed_action_result = agent.execute_api_action(
        environment=environment,
        belief_id="B1",
        action_id="A1",
    )
    assert failed_action_result["environment_result"]["success"] is False

    return agent, environment, failed_action_result


def test_recovery_engine_runs_selective_callback_and_executes_replacement():
    agent, environment, failed_action_result = _build_recovery_runtime()
    recomputed = []

    def recompute_node(node):
        recomputed.append(node.id)
        return {"node_id": node.id, "recomputed": True}

    result = RecoveryEngine(agent).recover_from_action_failure(
        action_result=failed_action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
        environment=environment,
        recompute_node=recompute_node,
    )

    assert result["selective_recovery"] is not None
    assert result["recovery_metrics"]["selective_recovery_executed"] is True
    assert result["selective_recovery"]["status"] == "completed"
    assert recomputed == result["selective_recovery"]["recomputed_node_ids"]
    assert recomputed  # The real RecoveryEngine invoked the supplied callback.

    assert result["new_action"].id == "A2"
    assert result["execution"]["success"] is True
    assert agent.graph.get_node("A2").execution_result["success"] is True

    # The independent branch remains untouched by recovery.
    assert agent.graph.get_node("B3").status.value == "active"
    assert agent.graph.get_node("C3").status.value == "active"
    assert agent.graph.get_node("P3").status.value == "active"


def test_recovery_engine_reports_callback_failure_separately_from_action_execution():
    agent, environment, failed_action_result = _build_recovery_runtime()

    def failing_recompute(node):
        raise RuntimeError(f"cannot recompute {node.id}")

    result = RecoveryEngine(agent).recover_from_action_failure(
        action_result=failed_action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
        environment=environment,
        recompute_node=failing_recompute,
    )

    selective = result["selective_recovery"]
    assert selective is not None
    assert selective["status"] == "partial_failure"
    assert selective["metrics"]["failed_recomputations"] >= 1

    # Replacement API execution and generic recomputation are separate outcomes.
    assert result["execution"]["success"] is True
    assert result["recovery_metrics"]["replacement_succeeded"] is True
    assert result["recovery_metrics"]["failed_recomputations"] >= 1


def test_semantic_recomputer_refreshes_conclusion_and_plan_during_real_recovery():
    agent, environment, failed_action_result = _build_recovery_runtime()

    # Model stale cached values from the pre-revision belief version.
    agent.graph.get_node("C1").value = {"available": True, "api_version": "v1"}
    agent.graph.get_node("P1").value = {"action": "retrieve_customer_data", "api_version": "v1"}

    def evaluate_conclusion(node, predecessor_values):
        current_version = predecessor_values["B2"]
        return {
            "available": current_version == "v2",
            "api_version": current_version,
        }

    def evaluate_plan(node, predecessor_values):
        conclusion = predecessor_values["C1"]
        return {
            "action": "retrieve_customer_data",
            "api_version": conclusion["api_version"],
            "enabled": conclusion["available"],
        }

    recomputer = SemanticRecomputer(
        agent,
        {
            "C1": evaluate_conclusion,
            "P1": evaluate_plan,
        },
    )

    result = RecoveryEngine(agent).recover_from_action_failure(
        action_result=failed_action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
        environment=environment,
        recompute_node=recomputer,
    )

    selective = result["selective_recovery"]
    assert selective is not None
    assert selective["status"] == "completed"
    assert selective["execution_order"].index("C1") < selective["execution_order"].index("P1")
    assert agent.graph.get_node("C1").value == {
        "available": True,
        "api_version": "v2",
    }
    assert agent.graph.get_node("P1").value == {
        "action": "retrieve_customer_data",
        "api_version": "v2",
        "enabled": True,
    }

    # Replacement action handling stays on its existing path.
    assert result["execution"]["success"] is True
    assert result["new_action"].id == "A2"

    # The independent branch keeps its original values and active status.
    assert agent.graph.get_node("C3").value is None
    assert agent.graph.get_node("P3").value is None
    assert agent.graph.get_node("C3").status.value == "active"
    assert agent.graph.get_node("P3").status.value == "active"

