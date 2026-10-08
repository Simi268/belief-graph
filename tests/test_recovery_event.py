from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment
from app.models import (
    NodeType,
    DependencyType
)
from app.recovery import RecoveryEngine


def test_recovery_creates_revision_event():

    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    # Initial belief
    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90
    )

    # Initial action
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

    # Reality changes
    environment.set_api_version("v2")

    # Execute stale action
    action_result = agent.execute_api_action(
        environment,
        belief_id="B1",
        action_id="A1"
    )

    # Recover
    recovery = RecoveryEngine(agent)

    result = recovery.recover_from_action_failure(
        action_result=action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2"
    )

    event = result["event"]

    # Verify event identity
    assert event.event_id == (
        "REV-CONFLICT-E1-B1"
    )

    assert event.conflict_id == (
        "CONFLICT-E1-B1"
    )

    # Verify belief transition
    assert event.old_belief_id == "B1"
    assert event.new_belief_id == "B2"

    # Verify action transition
    assert event.old_action_id == "A1"
    assert event.new_action_id == "A2"

    # Verify affected reasoning
    assert "B1" in event.invalidated_nodes
    assert "A1" in event.invalidated_nodes

    # Verify explanation
    assert (
        "contradicts belief"
        in event.reason
    )

    # Verify timestamp
    assert event.timestamp is not None