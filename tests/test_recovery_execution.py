from app.agent import AgentRuntime
from app.models import NodeType, DependencyType
from app.environment import DynamicAPIEnvironment
from app.replanner import Replanner


def test_recovery_execution_replaces_only_affected_action():

    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    # ==================================================
    # ORIGINAL BRANCH
    # ==================================================

    agent.create_belief(
        "B1",
        "API version is v1",
        value="v1"
    )

    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "Customer data can be retrieved"
    )

    agent.create_node(
        "P1",
        NodeType.PLAN,
        "Retrieve customer data"
    )

    agent.create_node(
        "A1",
        NodeType.ACTION,
        "Call customer API using v1"
    )

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "C1",
        "P1",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "P1",
        "A1",
        DependencyType.REQUIRES
    )

    # ==================================================
    # UNRELATED BRANCH
    # ==================================================

    agent.create_belief(
        "B3",
        "Reporting database is available",
        value=True
    )

    agent.create_node(
        "C3",
        NodeType.CONCLUSION,
        "Reporting data can be generated"
    )

    agent.create_node(
        "P3",
        NodeType.PLAN,
        "Generate reporting data"
    )

    agent.add_dependency(
        "B3",
        "C3",
        DependencyType.REQUIRES
    )

    agent.add_dependency(
        "C3",
        "P3",
        DependencyType.REQUIRES
    )

    # ==================================================
    # ENVIRONMENT CHANGES
    # ==================================================

    environment.set_api_version("v2")

    # Original action fails because it still assumes v1.
    result = agent.execute_api_action(
        environment=environment,
        belief_id="B1",
        action_id="A1"
    )

    assert result["environment_result"]["success"] is False

    # ==================================================
    # DETECT CHANGE
    # ==================================================

    evidence_result = agent.create_evidence_from_action_result(
        evidence_id="E1",
        action_result=result
    )

    conflict = evidence_result["conflict"]

    revision = agent.revise_from_action_failure(
        conflict_id=conflict.id,
        new_belief_id="B2"
    )

    # ==================================================
    # BUILD RECOVERY PLAN
    # ==================================================

    impact = agent.graph.analyze_multi_belief_impact(
        changed_nodes=["B1"]
    )

    recovery_plan = agent.create_recovery_plan(
        impact=impact,
        changed_nodes=["B1"]
    )

    assert set(recovery_plan["replan_nodes"]) == {
        "P1",
        "A1"
    }

    assert set(recovery_plan["preserved_nodes"]) == {
        "B3",
        "C3",
        "P3"
    }

    # ==================================================
    # EXECUTE RECOVERY
    # ==================================================

    replanner = Replanner(agent.graph)

    new_action = replanner.replan_api_action(
        old_belief_id="B1",
        new_belief_id="B2",
        old_action_id="A1",
        new_action_id="A2"
    )

    assert new_action.id == "A2"
    assert new_action.value == "v2"

    # ==================================================
    # EXECUTE NEW ACTION
    # ==================================================

    recovered_result = agent.execute_api_action(
        environment=environment,
        belief_id="B2",
        action_id="A2"
    )

    assert recovered_result["environment_result"]["success"] is True

    # ==================================================
    # UNRELATED BRANCH MUST REMAIN
    # ==================================================

    assert agent.graph.get_node("B3").status.value == "active"
    assert agent.graph.get_node("C3").status.value == "active"
    assert agent.graph.get_node("P3").status.value == "active"