from app.agent import AgentRuntime
from app.environment import DynamicAPIEnvironment
from app.recovery import RecoveryEngine
from app.models import NodeType, DependencyType


def test_revision_event_separates_impact_states():

    agent = AgentRuntime()

    environment = DynamicAPIEnvironment()

    # ==================================================
    # INITIAL BELIEF
    # ==================================================

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90,
        source="initial-knowledge"
    )

    # ==================================================
    # INITIAL ACTION
    # ==================================================

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Call API using v1",
        value="v1"
    )

    agent.add_dependency(
        "B1",
        "A1",
        DependencyType.REQUIRES
    )

    # ==================================================
    # SUPPORTING CONCLUSION
    # ==================================================

    agent.create_node(
        node_id="C2",
        node_type=NodeType.CONCLUSION,
        content="API availability supports retrieval"
    )

    agent.add_dependency(
        "B1",
        "C2",
        DependencyType.SUPPORTS
    )

    # ==================================================
    # ENVIRONMENT CHANGES
    # ==================================================

    environment.set_api_version("v2")

    # ==================================================
    # EXECUTE STALE ACTION
    # ==================================================

    action_result = agent.execute_api_action(
        environment=environment,
        belief_id="B1",
        action_id="A1"
    )

    # ==================================================
    # RECOVERY
    # ==================================================

    recovery = RecoveryEngine(agent)

    result = recovery.recover_from_action_failure(
        action_result=action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2"
    )

    event = result["event"]

    # ==================================================
    # VERIFY RECOVERY
    # ==================================================

    assert result["status"] == "recovered"

    assert event.old_belief_id == "B1"

    assert event.new_belief_id == "B2"

    assert event.old_action_id == "A1"

    assert event.new_action_id == "A2"

    # ==================================================
    # VERIFY INVALIDATION
    # ==================================================

    assert "B1" in event.invalidated_nodes

    assert "A1" in event.invalidated_nodes

    # ==================================================
    # VERIFY REEVALUATION
    # ==================================================

    assert "C2" in event.reevaluation_nodes

    # C2 must NOT be considered invalid.
    assert "C2" not in event.invalidated_nodes

    # ==================================================
    # VERIFY AFFECTED NODES
    # ==================================================

    assert "B1" in event.affected_nodes

    assert "A1" in event.affected_nodes

    assert "C2" in event.affected_nodes

    assert "B2" in event.affected_nodes

    # ==================================================
    # VERIFY STATE GROUPS DO NOT OVERLAP
    # ==================================================

    invalidated = set(
        event.invalidated_nodes
    )

    reevaluation = set(
        event.reevaluation_nodes
    )

    uncertain = set(
        event.uncertain_nodes
    )

    assert invalidated.isdisjoint(
        reevaluation
    )

    assert invalidated.isdisjoint(
        uncertain
    )

    assert reevaluation.isdisjoint(
        uncertain
    )

    # ==================================================
    # VERIFY ALL CLASSIFIED NODES ARE AFFECTED
    # ==================================================

    classified = (
        invalidated
        | reevaluation
        | uncertain
    )

    assert classified.issubset(
        set(event.affected_nodes)
    )