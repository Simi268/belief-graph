from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment


def test_agent_executes_action_using_belief():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge"
    )

    result = agent.execute_api_action(
        environment,
        "B1"
    )

    assert result["environment_result"]["success"] is True
    assert result["assumed_version"] == "v1"


def test_agent_detects_stale_belief_from_environment_failure():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge"
    )

    # Reality changes
    environment.set_api_version("v2")

    result = agent.execute_api_action(
        environment,
        "B1"
    )

    assert result["environment_result"]["success"] is False
    assert result["environment_result"]["error"] == "API_VERSION_MISMATCH"
    assert result["environment_result"]["expected"] == "v2"
    assert result["environment_result"]["received"] == "v1"
    