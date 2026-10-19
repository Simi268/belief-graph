from experiments.retroactive_commitment_experiment import _run_strategy, run_experiment


def test_selective_commitment_recovery_is_correct_and_preserves_unrelated_effect():
    result = _run_strategy("beliefgraph_selective")

    assert result.success is True
    assert result.semantic_nodes_recomputed == ["C_ELIGIBILITY", "P_REFUND"]
    assert set(result.affected_commitments_identified) == {
        "refund-001", "notice-001", "audit-001"
    }
    assert result.commitment_statuses["refund-001"] == "reconciled"
    assert result.commitment_statuses["notice-001"] == "requires_review"
    assert result.commitment_statuses["audit-001"] == "requires_review"
    assert result.commitment_statuses["shipment-001"] == "active"
    assert result.external_state == {
        "refund_issued": False,
        "customer_notice_sent": True,
        "audit_exported": True,
        "shipment_reserved": True,
    }
    assert result.compensation_attempts == 1
    assert result.duplicate_compensation_prevented is True


def test_full_restart_is_correct_but_recomputes_all_semantic_nodes():
    full = _run_strategy("full_restart")
    selective = _run_strategy("beliefgraph_selective")

    assert full.success is True
    assert len(full.semantic_nodes_recomputed) == 4
    assert selective.success is True
    assert len(selective.semantic_nodes_recomputed) == 2


def test_dependency_only_recovery_leaves_completed_effects_unhandled():
    result = _run_strategy("dependency_only")

    assert result.success is False
    assert result.external_state["refund_issued"] is True
    assert set(result.unflagged_affected_commitments) == {
        "refund-001", "notice-001", "audit-001"
    }


def test_experiment_report_does_not_claim_literature_novelty():
    report = run_experiment()

    assert report["comparison"]["selective_vs_full_semantic_nodes_saved"] == 2
    assert report["comparison"]["selective_vs_full_semantic_node_reduction_percent"] == 50.0
    assert report["comparison"]["same_commitment_scan_cost_for_full_and_selective"] is True
    assert report["comparison"]["full_restart_commitment_records_examined"] == 16
    assert report["comparison"]["selective_commitment_records_examined"] == 16
    assert report["go_no_go"]["evidence_of_novelty_vs_published_systems"] is False
