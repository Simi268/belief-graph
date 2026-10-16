from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus,
    ActionExecutionStatus,
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
def test_recovery_executes_replacement_action_successfully():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    # Create the outdated belief.
    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge",
    )

    # Create the original action.
    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1",
        value="v1",
    )

    agent.add_dependency(
        "B1",
        "A1",
        DependencyType.REQUIRES,
    )

    # The environment now requires v2.
    environment.set_api_version("v2")

    # Confirm the original action fails.
    action_result = agent.execute_api_action(
        environment,
        belief_id="B1",
        action_id="A1",
    )

    assert action_result["environment_result"]["success"] is False

    # Revise the belief and execute the replacement action.
    recovery = RecoveryEngine(agent)

    result = recovery.recover_from_action_failure(
        action_result=action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
        environment=environment,
    )

    # Verify actual recovery execution.
    assert result["execution"] is not None
    assert result["execution"]["environment_result"]["success"] is True

    # Verify the revised belief is used.
    assert agent.graph.get_node("B2").value == "v2"

    # Verify the replacement action was executed successfully.
    replacement = agent.graph.get_node("A2")
    assert replacement.value == "v2"
    assert replacement.execution_status == ActionExecutionStatus.SUCCEEDED

def test_selective_recovery_preserves_unrelated_branch():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    # Main branch: API belief -> conclusion -> plan -> action.
    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge",
    )

    agent.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="The API supports v1",
    )

    agent.create_node(
        node_id="P1",
        node_type=NodeType.PLAN,
        content="Call the API using v1",
    )

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Execute API request using v1",
        value="v1",
    )

    agent.add_dependency("B1", "C1", DependencyType.REQUIRES)
    agent.add_dependency("C1", "P1", DependencyType.REQUIRES)
    agent.add_dependency("P1", "A1", DependencyType.REQUIRES)

    # Independent branch: it should not be affected by the API change.
    agent.create_belief(
        belief_id="B3",
        content="Independent fact remains true",
        value="independent",
        confidence=0.95,
        source="independent-knowledge",
    )

    agent.create_node(
        node_id="C3",
        node_type=NodeType.CONCLUSION,
        content="Independent conclusion",
    )

    agent.create_node(
        node_id="P3",
        node_type=NodeType.PLAN,
        content="Independent plan",
    )

    agent.add_dependency("B3", "C3", DependencyType.REQUIRES)
    agent.add_dependency("C3", "P3", DependencyType.REQUIRES)

    # Capture the unrelated branch's original state.
    unrelated_ids = ["B3", "C3", "P3"]
    original_statuses = {
        node_id: agent.graph.get_node(node_id).status
        for node_id in unrelated_ids
    }

    # The API changes from v1 to v2.
    environment.set_api_version("v2")

    action_result = agent.execute_api_action(
        environment,
        belief_id="B1",
        action_id="A1",
    )

    assert action_result["environment_result"]["success"] is False

    # Revise the belief and execute the replacement action.
    recovery = RecoveryEngine(agent)

    result = recovery.recover_from_action_failure(
        action_result=action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
        environment=environment,
    )

    # Verify that the replacement action actually succeeded.
    assert result["execution"] is not None
    assert result["execution"]["success"] is True
    assert (
        result["execution"]["environment_result"]["success"] is True
    )

    assert agent.graph.get_node("B2").value == "v2"
    assert agent.graph.get_node("A2").value == "v2"

    # Verify that the unrelated branch retained its original states.
    for node_id in unrelated_ids:
        assert (
            agent.graph.get_node(node_id).status
            == original_statuses[node_id]
        )

def test_selective_recovery_preserves_unrelated_branch():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    # Main branch: API belief -> conclusion -> plan -> action.
    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge",
    )

    agent.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="The API supports v1",
    )

    agent.create_node(
        node_id="P1",
        node_type=NodeType.PLAN,
        content="Call the API using v1",
    )

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Execute API request using v1",
        value="v1",
    )

    agent.add_dependency("B1", "C1", DependencyType.REQUIRES)
    agent.add_dependency("C1", "P1", DependencyType.REQUIRES)
    agent.add_dependency("P1", "A1", DependencyType.REQUIRES)

    # Independent branch: it should not be affected by the API change.
    agent.create_belief(
        belief_id="B3",
        content="Independent fact remains true",
        value="independent",
        confidence=0.95,
        source="independent-knowledge",
    )

    agent.create_node(
        node_id="C3",
        node_type=NodeType.CONCLUSION,
        content="Independent conclusion",
    )

    agent.create_node(
        node_id="P3",
        node_type=NodeType.PLAN,
        content="Independent plan",
    )

    agent.add_dependency("B3", "C3", DependencyType.REQUIRES)
    agent.add_dependency("C3", "P3", DependencyType.REQUIRES)

    # Capture the unrelated branch's original state.
    unrelated_ids = ["B3", "C3", "P3"]
    original_statuses = {
        node_id: agent.graph.get_node(node_id).status
        for node_id in unrelated_ids
    }

    # The API changes from v1 to v2.
    environment.set_api_version("v2")

    action_result = agent.execute_api_action(
        environment,
        belief_id="B1",
        action_id="A1",
    )

    assert action_result["environment_result"]["success"] is False

    # Revise the belief and execute the replacement action.
    recovery = RecoveryEngine(agent)

    result = recovery.recover_from_action_failure(
        action_result=action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
        environment=environment,
    )

    # Verify that the replacement action actually succeeded.
    assert result["execution"] is not None
    assert result["execution"]["success"] is True
    assert (
        result["execution"]["environment_result"]["success"] is True
    )

    assert agent.graph.get_node("B2").value == "v2"
    assert agent.graph.get_node("A2").value == "v2"

    # Verify that the unrelated branch retained its original states.
    for node_id in unrelated_ids:
        assert (
            agent.graph.get_node(node_id).status
            == original_statuses[node_id]
        )