from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)
from app.recovery import RecoveryEngine


def test_full_recovery_workflow():

    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    # -------------------------
    # Initial belief
    # -------------------------

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge"
    )

    # -------------------------
    # Initial action
    # -------------------------

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1",
        value="v1"
    )

    agent.add_dependency(
        "B1",
        "A1",
        DependencyType.REQUIRES
    )

    # -------------------------
    # Environment changes
    # -------------------------

    environment.set_api_version("v2")

    # -------------------------
    # Execute stale action
    # -------------------------

    action_result = agent.execute_api_action(
        environment,
        belief_id="B1",
        action_id="A1"
    )

    assert (
        action_result["environment_result"]["success"]
        is False
    )

    # -------------------------
    # Recovery
    # -------------------------

    recovery = RecoveryEngine(agent)

    result = recovery.recover_from_action_failure(
        action_result=action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2"
    )

    # -------------------------
    # Verify recovery
    # -------------------------

    assert result["status"] == "recovered"

    assert (
        agent.graph.get_node("B1").status
        == NodeStatus.INVALID
    )

    assert (
        agent.graph.get_node("B2").status
        == NodeStatus.ACTIVE
    )

    assert (
        agent.graph.get_node("A1").status
        == NodeStatus.INVALID
    )

    assert (
        agent.graph.get_node("A2").status
        == NodeStatus.ACTIVE
    )

    # New action should use updated belief

    new_action = agent.graph.get_node("A2")

    assert new_action.value == "v2"

    assert (
        agent.graph.get_dependency_type(
            "B2",
            "A2"
        )
        == DependencyType.REQUIRES
    )