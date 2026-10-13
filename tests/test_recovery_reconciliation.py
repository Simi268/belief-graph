from app.agent import AgentRuntime
from app.commitments import (
    CommitmentRegistry,
    CommitmentStatus,
    Reversibility,
)
from app.commitment_reconciler import CommitmentReconciler
from app.environment import DynamicAPIEnvironment
from app.models import DependencyType, NodeType
from app.recovery import RecoveryEngine


def test_recovery_returns_commitment_recommendations():
    agent = AgentRuntime()
    environment = DynamicAPIEnvironment()

    agent.create_belief(
        belief_id="belief-v1",
        content="API version v1",
        value="v1",
    )

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
        "belief-v1", "plan-v1", DependencyType.REQUIRES
    )
    agent.add_dependency(
        "plan-v1", "action-v1", DependencyType.REQUIRES
    )

    registry = CommitmentRegistry()

    registry.register(
        commitment_id="shipment-001",
        action_id="action-v1",
        originating_belief_ids={"belief-v1"},
        description="Shipment reservation",
        reversibility=Reversibility.COMPENSABLE,
    )

    engine = RecoveryEngine(agent, commitment_registry=registry)

    environment.set_api_version("v2")

    action_result = agent.execute_api_action(
        environment,
        belief_id="belief-v1",
        action_id="action-v1",
    )

    result = engine.recover_from_action_failure(
        action_result=action_result,
        evidence_id="evidence-v2",
        new_belief_id="belief-v2",
        new_action_id="action-v2",
    )

    assert "commitment_impact" in result
    assert "commitment_recommendations" in result

    recommendations = result["commitment_recommendations"]

    assert len(recommendations) == 1
    assert recommendations[0]["commitment_id"] == "shipment-001"
    assert recommendations[0]["recommendation"] == "compensate"
    assert recommendations[0]["requires_approval"] is True


def test_recovery_engine_reconciles_with_approval_and_evidence():
    registry = CommitmentRegistry()

    registry.register(
        commitment_id="shipment-002",
        action_id="action-002",
        originating_belief_ids={"belief-stock"},
        description="Shipment reservation",
        reversibility=Reversibility.COMPENSABLE,
    )

    registry.mark_inconsistent(
        "shipment-002",
        "The stock belief changed.",
    )

    engine = RecoveryEngine(
        AgentRuntime(),
        commitment_registry=registry,
    )

    result = engine.reconcile_commitment(
        "shipment-002",
        lambda commitment: {
            "success": True,
            "verification_evidence": (
                "External reservation cancellation verified."
            ),
        },
    )

    assert result.status == "approval_required"
    assert (
        registry.get("shipment-002").status
        == CommitmentStatus.INCONSISTENT
    )

    result = engine.reconcile_commitment(
        "shipment-002",
        lambda commitment: {
            "success": True,
            "verification_evidence": (
                "External reservation cancellation verified."
            ),
        },
        approved=True,
    )

    assert result.status == "reconciled"
    assert (
        registry.get("shipment-002").status
        == CommitmentStatus.RECONCILED
    )