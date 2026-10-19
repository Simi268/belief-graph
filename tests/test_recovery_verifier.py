from app.models import NodeStatus
from app.recovery_verifier import verify_recovery

from app.graph import BeliefGraph
from app.models import BeliefNode, NodeType
from app.recovery_verifier import verify_graph_recovery


def expected_graph():
    return {
        "B1": NodeStatus.INVALID,
        "C1": NodeStatus.INVALID,
        "P2": NodeStatus.REQUIRES_REEVALUATION,
        "P3": NodeStatus.UNCERTAIN,
        "A2": NodeStatus.ACTIVE,
    }


def test_correct_recovery_is_verified():
    result = verify_recovery(
        actual_statuses=expected_graph(),
        expected_statuses=expected_graph(),
        execution_result={"success": True},
    )

    assert result.verified is True
    assert result.graph_correct is True
    assert result.execution_successful is True
    assert result.stale_nodes == []
    assert result.unnecessarily_invalidated_nodes == []


def test_successful_execution_does_not_hide_stale_state():
    actual = expected_graph()
    actual["C1"] = NodeStatus.ACTIVE

    result = verify_recovery(
        actual_statuses=actual,
        expected_statuses=expected_graph(),
        execution_result={"success": True},
    )

    assert result.verified is False
    assert result.execution_successful is True
    assert result.graph_correct is False
    assert "C1" in result.stale_nodes


def test_unnecessary_invalidation_is_detected():
    actual = expected_graph()
    actual["A2"] = NodeStatus.INVALID

    result = verify_recovery(
        actual_statuses=actual,
        expected_statuses=expected_graph(),
        execution_result={"success": True},
    )

    assert result.verified is False
    assert "A2" in result.unnecessarily_invalidated_nodes


def test_correct_graph_does_not_hide_execution_failure():
    result = verify_recovery(
        actual_statuses=expected_graph(),
        expected_statuses=expected_graph(),
        execution_result={"success": False},
    )

    assert result.graph_correct is True
    assert result.execution_successful is False
    assert result.verified is False


def test_wrong_node_classification_is_detected():
    actual = expected_graph()
    actual["P2"] = NodeStatus.INVALID

    result = verify_recovery(
        actual_statuses=actual,
        expected_statuses=expected_graph(),
        execution_result={"success": True},
    )

    assert result.verified is False
    assert result.status_mismatches["P2"] == {
        "expected": "requires_reevaluation",
        "actual": "invalid",
    }


def test_missing_node_is_detected():
    actual = expected_graph()
    del actual["C1"]

    result = verify_recovery(
        actual_statuses=actual,
        expected_statuses=expected_graph(),
        execution_result={"success": True},
    )

    assert result.verified is False
    assert "C1" in result.missing_nodes

def test_verifier_reads_actual_graph_states():
    graph = BeliefGraph()

    for node_id, status in expected_graph().items():
        graph.add_node(
            BeliefNode(
                id=node_id,
                node_type=(
                    NodeType.BELIEF
                    if node_id in {"B1"}
                    else NodeType.PLAN
                    if node_id in {"P2", "P3"}
                    else NodeType.ACTION
                    if node_id == "A2"
                    else NodeType.CONCLUSION
                ),
                content=f"Test node {node_id}",
                status=status,
            )
        )

    result = verify_graph_recovery(
        graph=graph,
        expected_statuses=expected_graph(),
        execution_result={"success": True},
    )

    assert result.verified is True
    assert result.graph_correct is True


def test_verifier_detects_stale_state_in_actual_graph():
    graph = BeliefGraph()

    for node_id, status in expected_graph().items():
        if node_id == "C1":
            status = NodeStatus.ACTIVE

        graph.add_node(
            BeliefNode(
                id=node_id,
                node_type=(
                    NodeType.BELIEF
                    if node_id == "B1"
                    else NodeType.PLAN
                    if node_id in {"P2", "P3"}
                    else NodeType.ACTION
                    if node_id == "A2"
                    else NodeType.CONCLUSION
                ),
                content=f"Test node {node_id}",
                status=status,
            )
        )

    result = verify_graph_recovery(
        graph=graph,
        expected_statuses=expected_graph(),
        execution_result={"success": True},
    )

    assert result.verified is False
    assert "C1" in result.stale_nodes

def test_end_to_end_recovery_verification():
    from app.agent import AgentRuntime
    from app.environment import DynamicAPIEnvironment
    from app.models import DependencyType, NodeType
    from app.recovery import RecoveryEngine
    from app.recovery_verifier import verify_recovery_run

    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief(
        belief_id='B1',
        content='API version is v1',
        value='v1',
        confidence=0.9,
        source='initial-knowledge',
    )
    agent.create_node(
        node_id='A1',
        node_type=NodeType.ACTION,
        content='Call customer API using v1',
        value='v1',
    )
    agent.add_dependency('B1', 'A1', DependencyType.REQUIRES)

    environment.set_api_version('v2')
    failed_action = agent.execute_api_action(
        environment, belief_id='B1', action_id='A1'
    )
    assert failed_action['environment_result']['success'] is False

    recovery = RecoveryEngine(agent)
    result = recovery.recover_from_action_failure(
        action_result=failed_action,
        evidence_id='E1',
        new_belief_id='B2',
        new_action_id='A2',
        environment=environment,
    )

    assert result['status'] == 'recovered'
    assert result['execution'] is not None
    assert result['execution']['success'] is True

    expected_statuses = {
        'B1': NodeStatus.INVALID,
        'B2': NodeStatus.ACTIVE,
        'A1': NodeStatus.INVALID,
        'A2': NodeStatus.ACTIVE,
    }

    report = verify_recovery_run(
        agent=agent,
        recovery_result=result,
        expected_statuses=expected_statuses,
    )

    assert report['graph_correct'] is True
    assert report['execution_successful'] is True
    assert report['verified'] is True
    assert report['stale_nodes'] == []
    assert report['unnecessarily_invalidated_nodes'] == []
    assert report['replacement_action_id'] == 'A2'

def test_end_to_end_verifier_rejects_unnecessary_invalidation():
    from app.agent import AgentRuntime
    from app.environment import DynamicAPIEnvironment
    from app.models import DependencyType, NodeType
    from app.recovery import RecoveryEngine
    from app.recovery_verifier import verify_recovery_run

    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief(
        belief_id='B1',
        content='API version is v1',
        value='v1',
        confidence=0.9,
        source='initial-knowledge',
    )
    agent.create_node(
        node_id='A1',
        node_type=NodeType.ACTION,
        content='Call customer API using v1',
        value='v1',
    )
    agent.add_dependency('B1', 'A1', DependencyType.REQUIRES)

    # This unrelated node must remain active after recovery.
    agent.create_belief(
        belief_id='B_UNRELATED',
        content='Independent authentication belief remains valid',
        value=True,
        confidence=0.95,
        source='authentication-service',
    )

    environment.set_api_version('v2')
    failed_action = agent.execute_api_action(
        environment, belief_id='B1', action_id='A1'
    )
    assert failed_action['environment_result']['success'] is False

    recovery = RecoveryEngine(agent)
    result = recovery.recover_from_action_failure(
        action_result=failed_action,
        evidence_id='E1',
        new_belief_id='B2',
        new_action_id='A2',
        environment=environment,
    )

    assert result['execution']['success'] is True

    # Inject an intentional graph-state defect after successful recovery.
    agent.graph.get_node('B_UNRELATED').status = NodeStatus.INVALID

    expected_statuses = {
        'B1': NodeStatus.INVALID,
        'B2': NodeStatus.ACTIVE,
        'A1': NodeStatus.INVALID,
        'A2': NodeStatus.ACTIVE,
        'B_UNRELATED': NodeStatus.ACTIVE,
    }

    report = verify_recovery_run(
        agent=agent,
        recovery_result=result,
        expected_statuses=expected_statuses,
    )

    assert report['execution_successful'] is True
    assert report['graph_correct'] is False
    assert report['verified'] is False
    assert 'B_UNRELATED' in report['unnecessarily_invalidated_nodes']

def test_planned_recovery_without_execution_is_not_verified():
    from app.agent import AgentRuntime
    from app.models import NodeType
    from app.recovery_verifier import verify_recovery_run

    agent = AgentRuntime()

    expected_statuses = {
        "B1": NodeStatus.INVALID,
        "B2": NodeStatus.ACTIVE,
    }

    agent.create_belief(
        belief_id="B1",
        content="Old belief",
        value="v1",
    )
    agent.create_belief(
        belief_id="B2",
        content="Replacement belief",
        value="v2",
    )

    # Set up the graph to match the expected recovered state.
    agent.graph.get_node("B1").status = NodeStatus.INVALID

    report = verify_recovery_run(
        agent=agent,
        recovery_result={
            "status": "recovered",
            "new_action": None,
            "execution": None,
        },
        expected_statuses=expected_statuses,
    )

    assert report["graph_correct"] is True
    assert report["execution_successful"] is False
    assert report["verified"] is False


def test_failed_replacement_execution_is_not_verified():
    from app.agent import AgentRuntime
    from app.models import ActionExecutionStatus, NodeType
    from app.recovery_verifier import verify_recovery_run

    agent = AgentRuntime()

    agent.create_belief(
        belief_id="B1",
        content="Old belief",
        value="v1",
    )
    agent.create_belief(
        belief_id="B2",
        content="Replacement belief",
        value="v2",
    )

    # Match the expected graph state before testing execution verification.
    agent.graph.get_node("B1").status = NodeStatus.INVALID

    action = agent.create_node(
        node_id="A2",
        node_type=NodeType.ACTION,
        content="Replacement API action",
        value="v2",
    )

    action.execution_status = ActionExecutionStatus.FAILED
    action.execution_result = {
        "success": False,
        "action_id": "A2",
    }

    expected_statuses = {
        "B1": NodeStatus.INVALID,
        "B2": NodeStatus.ACTIVE,
        "A2": NodeStatus.ACTIVE,
    }

    # The verifier must use the failed result stored on the actual action.
    report = verify_recovery_run(
        agent=agent,
        recovery_result={
            "status": "recovered",
            "new_action": action,
            "execution": {"success": True},
        },
        expected_statuses=expected_statuses,
    )

    assert report["graph_correct"] is True
    assert report["execution_successful"] is False
    assert report["verified"] is False