from app.ground_truth import SCENARIO_3_GROUND_TRUTH
from app.scenario3 import DatabaseSchemaChangeScenario


def test_database_schema_change_matches_ground_truth():
    result = DatabaseSchemaChangeScenario().run()
    ground_truth = SCENARIO_3_GROUND_TRUTH

    assert result.scenario_id == ground_truth.scenario_id
    assert result.changed_belief == ground_truth.changed_node

    assert set(result.invalidated_nodes) == (
        ground_truth.expected_invalidated
    )

    assert set(result.reevaluation_nodes) == (
        ground_truth.expected_reevaluation
    )

    assert set(result.uncertain_nodes) == (
        ground_truth.expected_uncertain
    )

    assert set(result.preserved_nodes) == (
        ground_truth.expected_preserved
    )


def test_database_schema_change_metrics():
    result = DatabaseSchemaChangeScenario().run()

    assert result.total_original_nodes == 12
    assert result.affected_node_count == 4
    assert result.invalidated_node_count == 4
    assert result.preserved_node_count == 8
    assert result.propagation_depth == 3
    assert result.preservation_ratio == 8 / 12