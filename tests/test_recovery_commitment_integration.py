from app.agent import AgentRuntime
from app.commitments import (
    CommitmentRegistry,
    CommitmentStatus,
    Reversibility,
)
from app.environment import DynamicAPIEnvironment
from app.models import DependencyType, NodeType
from app.recovery import RecoveryEngine


def test_recovery_marks_affected_commitments_and_returns_report():
    # 1. Create the agent and environment.
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    # 2. Establish the agent's original belief.
    agent.create_belief(
        belief_id="belief-v1",
        content="The API is running version v1",
        value="v1",
    )

    # 3. Create a dependent plan and action.
    agent.create_node(
        node_id="plan-v1",
        node_type=NodeType.PLAN,
        content="Use API v1",
    )

    agent.create_node(
        node_id="action-v1",
        node_type=NodeType.ACTION,
        content="Call API v1",
    )

    agent.add_dependency(
        "belief-v1",
        "plan-v1",
        DependencyType.REQUIRES,
    )
    agent.add_dependency(
        "plan-v1",
        "action-v1",
        DependencyType.REQUIRES,
    )

    # 4. Register external commitments tied to the original belief.
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="shipment-001",
        action_id="action-v1",
        originating_belief_ids={"belief-v1"},
        description="Shipment reservation created",
        reversibility=Reversibility.COMPENSABLE,
    )

    registry.register(
        commitment_id="payment-001",
        action_id="action-v1",
        originating_belief_ids={"belief-v1"},
        description="Payment submitted",
        reversibility=Reversibility.IRREVERSIBLE,
    )

    engine = RecoveryEngine(
        agent,
        commitment_registry=registry,
    )

    # 5. Change the environment to v2 and execute the old belief.
    environment.set_api_version("v2")

    action_result = agent.execute_api_action(
        environment=environment,
        belief_id="belief-v1",
        action_id="action-v1",
    )

    assert action_result["environment_result"]["success"] is False

    # 6. Run the actual recovery workflow.
    result = engine.recover_from_action_failure(
        action_result=action_result,
        evidence_id="evidence-v2",
        new_belief_id="belief-v2",
        new_action_id="action-v2",
    )

    # 7. Verify the recovery result includes commitment analysis.
    assert result["status"] in {"recovered", "revised"}

    report = result["commitment_impact"]

    assert set(report.affected_commitment_ids) == {
        "shipment-001",
        "payment-001",
    }

    # Reversible/compensable effect: inconsistent, requiring reconciliation.
    assert (
        registry.get("shipment-001").status
        == CommitmentStatus.INCONSISTENT
    )

    # Irreversible effect: requires human review.
    assert (
        registry.get("payment-001").status
        == CommitmentStatus.REQUIRES_REVIEW
    )

    # The revised belief should be present in the recovery result.
    assert result["revision"]["new_belief"] == "belief-v2"