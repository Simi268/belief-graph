from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment
from app.models import NodeStatus


def test_agent_revises_belief_after_environment_conflict():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    # Initial belief
    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge"
    )

    # Reality changes
    environment.set_api_version("v2")

    # Agent acts using stale belief
    action_result = agent.execute_api_action(
        environment,
        "B1"
    )

    # Failure becomes evidence + conflict
    evidence_result = (
        agent.create_evidence_from_action_result(
            evidence_id="E1",
            action_result=action_result
        )
    )

    conflict = evidence_result["conflict"]

    # Revise belief
    revision_result = agent.revise_from_action_failure(
        conflict_id=conflict.id,
        new_belief_id="B2"
    )

    assert revision_result["status"] == "revised"

    # Old belief is invalid
    assert (
        agent.get_belief_status("B1")
        == NodeStatus.INVALID
    )

    # New belief is active
    assert (
        agent.get_belief_status("B2")
        == NodeStatus.ACTIVE
    )

    # New belief contains updated reality
    new_belief = agent.graph.get_node("B2")

    assert new_belief.value == "v2"
    assert new_belief.confidence == 1.0