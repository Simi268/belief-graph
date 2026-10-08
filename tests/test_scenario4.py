from app.ground_truth import SCENARIO_4_GROUND_TRUTH
from app.scenario4 import PolicyChangeScenario


def test_policy_change_matches_ground_truth():
    result = PolicyChangeScenario().run()
    ground_truth = SCENARIO_4_GROUND_TRUTH

    assert result.scenario_id == ground_truth.scenario_id
    assert result.changed_belief == ground_truth.changed_node
    assert set(result.invalidated_nodes) == ground_truth.expected_invalidated
    assert set(result.reevaluation_nodes) == ground_truth.expected_reevaluation
    assert set(result.uncertain_nodes) == ground_truth.expected_uncertain
    assert set(result.preserved_nodes) == ground_truth.expected_preserved


def test_policy_change_metrics():
    result = PolicyChangeScenario().run()

    assert result.total_original_nodes == 12
    assert result.affected_node_count == 4
    assert result.invalidated_node_count == 4
    assert result.preserved_node_count == 8
    assert result.propagation_depth == 3
    assert result.preservation_ratio == 8 / 12


def test_policy_change_does_not_invalidate_independent_branches():
    result = PolicyChangeScenario().run()

    assert set(result.invalidated_nodes) == {"B1", "C1", "P1", "A1"}
    assert {"B2", "C2", "P2", "A2"}.issubset(
        set(result.preserved_nodes)
    )
    assert {"B3", "C3", "P3", "A3"}.issubset(
        set(result.preserved_nodes)
    )
