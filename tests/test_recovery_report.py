import pytest

from app.recovery_report import format_recovery_report


def test_formats_successful_selective_recovery():
    result = {
        "status": "recovered",
        "recovery_plan": {
            "affected_nodes": ["C1", "P1"],
            "invalidated_nodes": ["C1"],
            "reevaluation_nodes": ["P1"],
            "uncertain_nodes": [],
            "preserved_nodes": ["B2", "C2"],
        },
        "selective_recovery": {
            "status": "completed",
            "recomputed_node_ids": ["C1", "P1"],
            "preserved_node_ids": ["B2", "C2"],
            "failed_node_ids": [],
            "skipped_node_ids": [],
        },
        "new_action": {"id": "A2"},
        "execution": {"success": True},
        "recovery_metrics": {
            "affected_node_count": 2,
            "invalidated_node_count": 1,
            "reevaluation_node_count": 1,
            "successful_recomputations": 2,
            "failed_recomputations": 0,
            "recovery_duration_ms": 12.5,
            "selective_recovery_duration_ms": 4.25,
            "selective_recovery_executed": True,
        },
    }

    report = format_recovery_report(result)

    assert "BELIEFGRAPH RECOVERY REPORT" in report
    assert "Selective recovery status: completed" in report
    assert "Recomputed nodes: C1, P1" in report
    assert "Preserved nodes: B2, C2" in report
    assert "Execution success: True" in report
    assert "12.500 ms" in report


def test_reports_partial_failure_without_claiming_success():
    result = {
        "status": "revised",
        "recovery_plan": {
            "affected_nodes": ["C1", "P1"],
            "preserved_nodes": ["B1"],
        },
        "selective_recovery": {
            "status": "partial_failure",
            "recomputed_node_ids": ["C1"],
            "preserved_node_ids": ["B1"],
            "failed_node_ids": ["P1"],
            "skipped_node_ids": [],
        },
        "execution": {"success": False},
        "recovery_metrics": {
            "selective_recovery_executed": True,
            "successful_recomputations": 1,
            "failed_recomputations": 1,
        },
    }

    report = format_recovery_report(result)

    assert "Selective recovery status: partial_failure" in report
    assert "Failed nodes: P1" in report
    assert "Execution success: False" in report


def test_handles_missing_optional_fields():
    report = format_recovery_report({"status": "no_recovery_needed"})

    assert "Engine status: no_recovery_needed" in report
    assert "Selective recovery status: Not executed" in report
    assert "Recovery duration: Not available" in report
    assert "Execution success: Not available" in report


def test_rejects_non_mapping_input():
    with pytest.raises(TypeError):
        format_recovery_report(None)