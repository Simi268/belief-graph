from app.ground_truth import SCENARIO_5_GROUND_TRUTH
from app.scenario5 import ContradictoryEvidenceScenario


def test_contradictory_evidence_matches_ground_truth():
    result = ContradictoryEvidenceScenario().run()
    ground_truth = SCENARIO_5_GROUND_TRUTH

    assert result.scenario_id == ground_truth.scenario_id
    assert result.changed_belief == ground_truth.changed_node

    assert (
        set(result.invalidated_nodes)
        == ground_truth.expected_invalidated
    )

    assert (
        set(result.reevaluation_nodes)
        == ground_truth.expected_reevaluation
    )

    assert (
        set(result.uncertain_nodes)
        == ground_truth.expected_uncertain
    )

    assert (
        set(result.preserved_nodes)
        == ground_truth.expected_preserved
    )


def test_weaker_contradictory_evidence_is_rejected():
    result = ContradictoryEvidenceScenario().run()

    assert result.weak_evidence_id == "E1"
    assert result.weak_evidence_accepted is False


def test_stronger_contradictory_evidence_is_accepted():
    result = ContradictoryEvidenceScenario().run()

    assert result.strong_evidence_id == "E2"
    assert result.strong_evidence_accepted is True
    assert result.selected_evidence_id == "E2"


def test_contradictory_evidence_metrics():
    result = ContradictoryEvidenceScenario().run()

    assert result.total_original_nodes == 8
    assert result.affected_node_count == 4
    assert result.invalidated_node_count == 4
    assert result.reevaluation_node_count == 0
    assert result.uncertain_node_count == 0
    assert result.preserved_node_count == 4

    assert result.propagation_depth == 3
    assert result.preservation_ratio == 4 / 8
    assert result.revision_count == 1


def test_unrelated_branch_is_preserved():
    result = ContradictoryEvidenceScenario().run()

    assert set(result.preserved_nodes) == {
        "B2",
        "C2",
        "P2",
        "A2",
    }