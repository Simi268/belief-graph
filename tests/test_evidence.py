from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment


def test_action_failure_creates_evidence():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90
    )

    environment.set_api_version("v2")

    result = agent.execute_api_action(
        environment,
        "B1"
    )

    result = agent.create_evidence_from_action_result(
        evidence_id="E1",
        action_result=result
    )

    evidence = result["evidence"]

    assert evidence.id == "E1"
    assert evidence.source == "environment"
    assert evidence.confidence == 1.0
    assert "v2" in evidence.content
    assert "v1" in evidence.content


def test_action_failure_creates_conflict():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90
    )

    environment.set_api_version("v2")

    action_result = agent.execute_api_action(
        environment,
        "B1"
    )

    result = agent.create_evidence_from_action_result(
        evidence_id="E1",
        action_result=action_result
    )

    conflict = result["conflict"]

    assert conflict.evidence_id == "E1"
    assert conflict.belief_id == "B1"
    assert conflict.resolved is False