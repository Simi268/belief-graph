from app.models import NodeStatus
from app.scenario8 import MultiFailureRecoveryScenario


def test_both_failure_sources_are_invalidated():
    result = MultiFailureRecoveryScenario().run()

    assert result.changed_beliefs == ["B1", "B2"]

    assert "B1" in result.invalidated_nodes
    assert "B2" in result.invalidated_nodes


def test_both_dependency_branches_are_affected():
    result = MultiFailureRecoveryScenario().run()

    assert "C1" in result.invalidated_nodes
    assert "P1" in result.invalidated_nodes
    assert "A1" in result.invalidated_nodes

    assert "C2" in result.invalidated_nodes
    assert "P2" in result.invalidated_nodes
    assert "A2" in result.invalidated_nodes


def test_shared_node_tracks_both_failure_sources():
    result = MultiFailureRecoveryScenario().run()

    assert "S1" in result.shared_affected_nodes

    assert result.shared_affected_nodes["S1"] == ["B1", "B2"]


def test_shared_downstream_action_is_invalidated():
    result = MultiFailureRecoveryScenario().run()

    assert "S1" in result.invalidated_nodes
    assert "A4" in result.invalidated_nodes


def test_independent_branch_remains_preserved():
    result = MultiFailureRecoveryScenario().run()

    assert "B3" not in result.affected_nodes
    assert "C3" in result.preserved_nodes
    assert "P3" in result.preserved_nodes
    assert "A3" in result.preserved_nodes


def test_result_counts_are_consistent():
    result = MultiFailureRecoveryScenario().run()

    assert result.affected_node_count == len(result.affected_nodes)
    assert result.invalidated_node_count == len(result.invalidated_nodes)
    assert result.preserved_node_count == len(result.preserved_nodes)

    assert (
        result.preservation_ratio
        == result.preserved_node_count / result.total_original_nodes
    )


def test_every_reported_impact_has_causal_attribution():
    result = MultiFailureRecoveryScenario().run()

    for details in result.impact_details.values():
        assert details["affected_by"]


def test_operation_metrics_are_recorded():
    result = MultiFailureRecoveryScenario().run()

    metrics = result.operation_metrics

    assert metrics["queue_entries_processed"] > 0
    assert metrics["dependency_edges_examined"] > 0
    assert metrics["impact_classifications_computed"] > 0

    assert (
        metrics["dependency_edges_examined"]
        == metrics["impact_classifications_computed"]
    )


def test_shared_nodes_track_both_failure_sources():
    result = MultiFailureRecoveryScenario().run()

    assert result.shared_affected_nodes["S1"] == ["B1", "B2"]
    assert result.shared_affected_nodes["A4"] == ["B1", "B2"]