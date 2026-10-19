"""Deterministic go/no-go experiment for retroactive commitment reconciliation.

This experiment uses the existing BeliefGraph graph, semantic recomputation,
commitment resolver, impact analyzer, and reconciler. It adds no production API.

Scenario: an agent completed an order decision while believing a customer was
eligible. Authoritative evidence later corrects that belief. The simulated
external system already contains the completed effects: a compensable refund,
an irreversible customer notice, an effect of unknown reversibility, and an
unrelated shipment reservation.

Strategies:
- dependency_only: recompute only affected semantic nodes, without commitment
  tracking or reconciliation;
- full_restart: recompute all semantic conclusion/plan nodes, then use the
  same commitment-aware reconciliation policy;
- beliefgraph_selective: recompute only affected semantic nodes, then use the
  commitment-aware reconciliation policy.

The full-restart comparator intentionally uses the same commitment policy as
BeliefGraph so the comparison does not give it a weaker safety contract. The
experiment measures work saved in semantic recomputation, not a universal
performance claim or a comparison against another published system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import sys

# Support both direct execution (python experiments\retroactive_commitment_experiment.py)
# and module execution from the repository root. Direct execution otherwise puts
# only the experiments directory on sys.path, so the sibling `app` package may
# not be importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import networkx as nx

from app.agent import AgentRuntime
from app.commitment_analyzer import CommitmentImpactAnalyzer
from app.commitment_dependency_resolver import CommitmentDependencyResolver
from app.commitment_reconciler import CommitmentReconciler
from app.commitments import CommitmentRegistry, CommitmentStatus, Reversibility
from app.models import BeliefNode, DependencyType, NodeType
from app.semantic_recomputation import SemanticRecomputer


@dataclass
class SimulatedExternalSystem:
    """Minimal external state; compensation verifies the state after mutation."""

    refund_issued: bool = True
    customer_notice_sent: bool = True
    audit_exported: bool = True
    shipment_reserved: bool = True
    refund_cancellation_attempts: int = 0

    def cancel_refund(self, _commitment: Any) -> dict[str, Any]:
        self.refund_cancellation_attempts += 1
        self.refund_issued = False
        # Independent assertion against the simulated system's actual state.
        verified = self.refund_issued is False
        return {
            "success": verified,
            "verification_evidence": (
                "external-state check: refund_issued=false"
                if verified else "external-state check failed"
            ),
        }


@dataclass
class StrategyResult:
    strategy: str
    semantic_nodes_selected: list[str]
    semantic_nodes_recomputed: list[str]
    commitment_records_assessed: int
    commitment_registry_scan_passes: int
    affected_commitments_identified: list[str]
    recommendations: dict[str, str]
    commitment_statuses: dict[str, str]
    external_state: dict[str, Any]
    compensation_attempts: int
    unflagged_affected_commitments: list[str]
    unaffected_effect_preserved: bool
    compensation_verified: bool
    duplicate_compensation_prevented: bool
    success: bool
    checks: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "semantic_nodes_selected": self.semantic_nodes_selected,
            "semantic_nodes_recomputed": self.semantic_nodes_recomputed,
            "semantic_node_count": len(self.semantic_nodes_recomputed),
            "commitment_records_assessed": self.commitment_records_assessed,
            "commitment_registry_scan_passes": self.commitment_registry_scan_passes,
            "affected_commitments_identified": self.affected_commitments_identified,
            "recommendations": self.recommendations,
            "commitment_statuses": self.commitment_statuses,
            "external_state": self.external_state,
            "compensation_attempts": self.compensation_attempts,
            "unflagged_affected_commitments": self.unflagged_affected_commitments,
            "unaffected_effect_preserved": self.unaffected_effect_preserved,
            "compensation_verified": self.compensation_verified,
            "duplicate_compensation_prevented": self.duplicate_compensation_prevented,
            "success": self.success,
            "checks": self.checks,
        }


def _build_scenario():
    agent = AgentRuntime()
    agent.create_belief("B_ELIGIBLE", "Customer is eligible for refund", value=True)
    agent.create_belief("B_INVENTORY", "Shipment inventory is available", value=True)

    agent.create_node("C_ELIGIBILITY", NodeType.CONCLUSION, "Refund eligibility", value=True)
    agent.create_node("P_REFUND", NodeType.PLAN, "Issue approved refund", value={"refund_allowed": True})
    agent.create_node("A_PROCESS_ORDER", NodeType.ACTION, "Process refund and send notice")

    agent.create_node("C_INVENTORY", NodeType.CONCLUSION, "Shipment inventory is available", value=True)
    agent.create_node("P_SHIPMENT", NodeType.PLAN, "Prepare shipment", value={"shipment_allowed": True})
    agent.create_node("A_RESERVE_SHIPMENT", NodeType.ACTION, "Reserve shipment")

    edges = [
        ("B_ELIGIBLE", "C_ELIGIBILITY"),
        ("C_ELIGIBILITY", "P_REFUND"),
        ("P_REFUND", "A_PROCESS_ORDER"),
        ("B_INVENTORY", "C_INVENTORY"),
        ("C_INVENTORY", "P_SHIPMENT"),
        ("P_SHIPMENT", "A_RESERVE_SHIPMENT"),
    ]
    for source, target in edges:
        agent.add_dependency(source, target, DependencyType.REQUIRES)

    registry = CommitmentRegistry()
    registry.register(
        commitment_id="refund-001",
        action_id="A_PROCESS_ORDER",
        originating_belief_ids={"B_ELIGIBLE"},
        description="Refund was issued to a customer believed eligible",
        reversibility=Reversibility.COMPENSABLE,
    )
    registry.register(
        commitment_id="notice-001",
        action_id="A_PROCESS_ORDER",
        originating_belief_ids={"B_ELIGIBLE"},
        description="Customer was told the refund was approved",
        reversibility=Reversibility.IRREVERSIBLE,
    )
    registry.register(
        commitment_id="audit-001",
        action_id="A_PROCESS_ORDER",
        originating_belief_ids={"B_ELIGIBLE"},
        description="Eligibility decision was exported to an external audit queue",
        reversibility=Reversibility.UNKNOWN,
    )
    registry.register(
        commitment_id="shipment-001",
        action_id="A_RESERVE_SHIPMENT",
        originating_belief_ids={"B_INVENTORY"},
        description="Unrelated shipment reservation",
        reversibility=Reversibility.COMPENSABLE,
    )

    external = SimulatedExternalSystem()

    # Retroactive correction arrives after all three effects already exist.
    agent.graph.revise_belief(
        "B_ELIGIBLE",
        BeliefNode(
            id="B_ELIGIBLE_V2",
            node_type=NodeType.BELIEF,
            content="Authoritative record says customer is not eligible",
            value=False,
            confidence=1.0,
        ),
    )

    evaluators = {
        "C_ELIGIBILITY": lambda _node, parents: bool(
            parents.get("B_ELIGIBLE_V2", parents.get("B_ELIGIBLE"))
        ),
        "P_REFUND": lambda _node, parents: {
            "refund_allowed": bool(parents["C_ELIGIBILITY"])
        },
        "C_INVENTORY": lambda _node, parents: bool(parents["B_INVENTORY"]),
        "P_SHIPMENT": lambda _node, parents: {
            "shipment_allowed": bool(parents["C_INVENTORY"])
        },
    }
    return agent, registry, external, SemanticRecomputer(agent, evaluators)


def _semantic_order(agent) -> list[str]:
    order = list(nx.topological_sort(agent.graph.graph))
    return [
        node_id for node_id in order
        if agent.graph.get_node(node_id).node_type in {NodeType.CONCLUSION, NodeType.PLAN}
    ]


def _run_strategy(strategy: str) -> StrategyResult:
    if strategy not in {"dependency_only", "full_restart", "beliefgraph_selective"}:
        raise ValueError(f"Unknown strategy: {strategy}")

    agent, registry, external, recomputer = _build_scenario()
    all_semantic_nodes = _semantic_order(agent)
    affected_graph_nodes = {"B_ELIGIBLE"} | set(
        nx.descendants(agent.graph.graph, "B_ELIGIBLE")
    )
    affected_semantic_nodes = [
        node_id for node_id in all_semantic_nodes if node_id in affected_graph_nodes
    ]

    selected_nodes = (
        all_semantic_nodes
        if strategy == "full_restart"
        else affected_semantic_nodes
    )
    recompute_result = recomputer.recompute_nodes(selected_nodes)
    recomputed_nodes = recompute_result["recomputed_node_ids"]

    impact_resolver = CommitmentDependencyResolver(agent.graph, registry)
    impact_analyzer = CommitmentImpactAnalyzer(registry)
    reconciler = CommitmentReconciler(registry)

    affected_commitments: list[str] = []
    recommendations: dict[str, str] = {}
    commitment_records_assessed = 0
    commitment_registry_scan_passes = 0
    if strategy != "dependency_only":
        dependency_report = impact_resolver.resolve({"B_ELIGIBLE"})
        commitment_registry_scan_passes += 1
        affected_commitments = dependency_report.affected_commitment_ids
        impact_report = impact_analyzer.analyze(
            changed_belief_ids=dependency_report.affected_node_ids,
            reason="Authoritative eligibility record corrected after completion.",
        )
        commitment_registry_scan_passes += 1
        recommendations = {
            commitment_id: reconciler.recommend(commitment_id)["recommendation"]
            for commitment_id in affected_commitments
        }

        # The harness provides explicit approval for the known compensable
        # refund. Unsafe effects remain review-only. The callback verifies the
        # simulated external state after attempting compensation.
        for commitment_id in affected_commitments:
            recommendation = reconciler.recommend(commitment_id)
            if recommendation["recommendation"] == "compensate":
                approval_result = reconciler.reconcile(
                    commitment_id,
                    external.cancel_refund,
                    approved=False,
                )
                if approval_result.status != "approval_required":
                    raise AssertionError("Compensation did not require approval first.")
                reconciler.reconcile(
                    commitment_id,
                    external.cancel_refund,
                    approved=True,
                )

    # Idempotency probe: repeat impact analysis and reconciliation after the
    # correction has already been handled. A reconciled refund must not invoke
    # compensation a second time. Dependency-only has no such protection.
    if strategy != "dependency_only" and registry.get("refund-001").status == CommitmentStatus.RECONCILED:
        duplicate_report = impact_resolver.resolve({"B_ELIGIBLE"})
        commitment_registry_scan_passes += 1
        impact_analyzer.analyze(
            changed_belief_ids=duplicate_report.affected_node_ids,
            reason="Duplicate processing of the same authoritative correction.",
        )
        commitment_registry_scan_passes += 1
        before = external.refund_cancellation_attempts
        second = reconciler.reconcile(
            "refund-001",
            external.cancel_refund,
            approved=True,
        )
        duplicate_compensation_prevented = (
            second.status == "blocked"
            and external.refund_cancellation_attempts == before
            and registry.get("refund-001").status == CommitmentStatus.RECONCILED
        )
    else:
        duplicate_compensation_prevented = False

    commitment_records_assessed = commitment_registry_scan_passes * len(registry.all())
    statuses = {item.commitment_id: item.status.value for item in registry.all()}
    external_state = {
        "refund_issued": external.refund_issued,
        "customer_notice_sent": external.customer_notice_sent,
        "audit_exported": external.audit_exported,
        "shipment_reserved": external.shipment_reserved,
    }

    # In this ground-truth scenario, an affected effect is safe only when it is
    # verified reconciled or explicitly flagged for review; it must not remain
    # active/unflagged. The unrelated shipment must remain untouched and active.
    affected_ids = ["refund-001", "notice-001", "audit-001"]
    unflagged = [
        commitment_id for commitment_id in affected_ids
        if statuses[commitment_id] == CommitmentStatus.ACTIVE.value
    ]
    compensation_verified = (
        not external.refund_issued
        and statuses["refund-001"] == CommitmentStatus.RECONCILED.value
        and bool(registry.get("refund-001").metadata.get("verification_evidence"))
    )
    affected_unsafe_reviewed = (
        statuses["notice-001"] == CommitmentStatus.REQUIRES_REVIEW.value
        and statuses["audit-001"] == CommitmentStatus.REQUIRES_REVIEW.value
        and external.customer_notice_sent
        and external.audit_exported
    ) if strategy != "dependency_only" else False
    unrelated_preserved = (
        external.shipment_reserved
        and statuses["shipment-001"] == CommitmentStatus.ACTIVE.value
    )

    checks = {
        "affected_refund_handled": compensation_verified,
        "irreversible_notice_and_unknown_effect_flagged_for_review": affected_unsafe_reviewed,
        "unrelated_shipment_preserved": unrelated_preserved,
        "no_affected_commitment_left_active": not unflagged,
        "duplicate_compensation_prevented": duplicate_compensation_prevented,
        "semantic_recomputation_succeeded": recompute_result["success"],
        "corrected_eligibility_value": agent.graph.get_node("C_ELIGIBILITY").value is False,
        "unaffected_inventory_value": agent.graph.get_node("C_INVENTORY").value is True,
    }
    success = all(checks.values())

    return StrategyResult(
        strategy=strategy,
        semantic_nodes_selected=selected_nodes,
        semantic_nodes_recomputed=recomputed_nodes,
        commitment_records_assessed=commitment_records_assessed,
        commitment_registry_scan_passes=commitment_registry_scan_passes,
        affected_commitments_identified=affected_commitments,
        recommendations=recommendations,
        commitment_statuses=statuses,
        external_state=external_state,
        compensation_attempts=external.refund_cancellation_attempts,
        unflagged_affected_commitments=unflagged,
        unaffected_effect_preserved=unrelated_preserved,
        compensation_verified=compensation_verified,
        duplicate_compensation_prevented=duplicate_compensation_prevented,
        success=success,
        checks=checks,
    )


def run_experiment() -> dict[str, Any]:
    """Run all three strategies and return a machine-readable report."""
    results = {
        strategy: _run_strategy(strategy)
        for strategy in ("dependency_only", "full_restart", "beliefgraph_selective")
    }
    full = results["full_restart"]
    selective = results["beliefgraph_selective"]
    dependency_only = results["dependency_only"]

    report = {
        "experiment": "retroactive_completed_commitment_reconciliation",
        "scenario": (
            "A post-completion eligibility correction invalidates a compensable refund, "
            "an irreversible customer notice, and an external effect of unknown reversibility, "
            "while an unrelated shipment remains valid."
        ),
        "ground_truth": {
            "affected_commitments": ["audit-001", "notice-001", "refund-001"],
            "refund_must_be_cancelled_and_verified": True,
            "irreversible_notice_and_unknown_effect_must_be_flagged_for_review": True,
            "shipment_must_remain_untouched": True,
        },
        "strategies": {name: result.as_dict() for name, result in results.items()},
        "comparison": {
            "selective_vs_full_semantic_nodes_saved": (
                len(full.semantic_nodes_recomputed) - len(selective.semantic_nodes_recomputed)
            ),
            "selective_vs_full_semantic_node_reduction_percent": round(
                100 * (len(full.semantic_nodes_recomputed) - len(selective.semantic_nodes_recomputed))
                / max(1, len(full.semantic_nodes_recomputed)), 1
            ),
            "full_restart_success": full.success,
            "beliefgraph_selective_success": selective.success,
            "dependency_only_success": dependency_only.success,
            "same_commitment_scan_cost_for_full_and_selective": (
                full.commitment_records_assessed == selective.commitment_records_assessed
            ),
            "full_restart_commitment_registry_passes": full.commitment_registry_scan_passes,
            "selective_commitment_registry_passes": selective.commitment_registry_scan_passes,
            "full_restart_commitment_records_examined": full.commitment_records_assessed,
            "selective_commitment_records_examined": selective.commitment_records_assessed,
        },
        "interpretation_limits": [
            "This is a deterministic in-memory scenario, not a production benchmark.",
            "The dependency-only comparator intentionally has no commitment registry or reconciliation policy.",
            "Full restart uses the same commitment policy as BeliefGraph to avoid weakening its safety baseline.",
            "BeliefGraph currently scans all registered commitments during impact analysis; this experiment does not claim to reduce that scan cost.",
            "The reconciler trusts its compensation callback's verification evidence. The simulated adapter checks external state itself; production adapters must independently verify the actual external state.",
            "This scenario is orchestrated directly from existing graph/commitment components; the public RecoveryEngine does not currently expose a dedicated retroactive-correction entry point.",
            "This result does not establish superiority over REVISE, DART, Corollary, or other published systems."
        ],
        "go_no_go": {
            "technical_scenario_passed": selective.success,
            "selective_saves_semantic_recomputation_vs_full": (
                len(selective.semantic_nodes_recomputed) < len(full.semantic_nodes_recomputed)
            ),
            "beats_dependency_only_on_external_commitment_safety": (
                selective.success and not dependency_only.success
            ),
            "evidence_of_novelty_vs_published_systems": False,
            "novelty_verdict": "NOT ESTABLISHED; literature-level differentiation still required",
        },
    }
    return report


def main() -> int:
    import json
    from pathlib import Path

    report = run_experiment()
    output_path = Path("experiments/results/retroactive_commitment_experiment.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Retroactive commitment reconciliation experiment")
    print("Scenario: eligibility corrected after completed external effects")
    print()
    print(f"{'Strategy':<24} {'Semantic nodes':>15} {'Registry visits':>17} {'Safe outcome':>13}")
    print("-" * 78)
    for name in ("dependency_only", "full_restart", "beliefgraph_selective"):
        result = report["strategies"][name]
        count = len(result["semantic_nodes_recomputed"])
        assessed = result["commitment_records_assessed"]
        print(f"{name:<24} {count:>15} {assessed:>17} {str(result['success']):>13}")
    print()
    print("Selective vs full-restart semantic nodes saved:", report["comparison"]["selective_vs_full_semantic_nodes_saved"])
    print("Selective vs full-restart reduction:", f"{report['comparison']['selective_vs_full_semantic_node_reduction_percent']}%")
    print("BeliefGraph scenario checks:")
    for key, passed in report["strategies"]["beliefgraph_selective"]["checks"].items():
        print(f"  {'PASS' if passed else 'FAIL'}  {key}")
    print("Novelty verdict:", report["go_no_go"]["novelty_verdict"])
    print("JSON report written to:", output_path)
    return 0 if report["go_no_go"]["technical_scenario_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
