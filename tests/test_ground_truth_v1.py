from app.benchmark import BenchmarkRunner
from app.ground_truth import SCENARIO_1_GROUND_TRUTH, SCENARIO_2_GROUND_TRUTH
from app.models import NodeStatus


def test_ground_truth_specs_are_valid_partitions():
    SCENARIO_1_GROUND_TRUTH.validate()
    SCENARIO_2_GROUND_TRUTH.validate()

    assert SCENARIO_1_GROUND_TRUTH.original_node_ids == (
        SCENARIO_1_GROUND_TRUTH.expected_invalidated
        | SCENARIO_1_GROUND_TRUTH.expected_reevaluation
        | SCENARIO_1_GROUND_TRUTH.expected_uncertain
        | SCENARIO_1_GROUND_TRUTH.expected_preserved
    )
    assert SCENARIO_2_GROUND_TRUTH.original_node_ids == (
        SCENARIO_2_GROUND_TRUTH.expected_invalidated
        | SCENARIO_2_GROUND_TRUTH.expected_reevaluation
        | SCENARIO_2_GROUND_TRUTH.expected_uncertain
        | SCENARIO_2_GROUND_TRUTH.expected_preserved
    )


def test_scenario2_ground_truth_matches_actual_belief_graph_result():
    result = BenchmarkRunner().run_scenario2_belief_graph()
    gt = SCENARIO_2_GROUND_TRUTH

    assert set(result.details["invalidated_nodes"]) == gt.expected_invalidated
    assert set(result.details["reevaluation_nodes"]) == gt.expected_reevaluation
    assert set(result.details["uncertain_nodes"]) == gt.expected_uncertain
    assert set(result.details["preserved_nodes"]) == gt.expected_preserved

    assert result.details["ground_truth"]["changed_node"] == gt.changed_node
    assert result.details["ground_truth"]["expected_invalidated"] == sorted(gt.expected_invalidated)


def test_scenario2_ground_truth_state_map_is_explicit():
    impact = SCENARIO_2_GROUND_TRUTH.expected_impact

    assert impact["B1"] == NodeStatus.INVALID
    assert impact["C1"] == NodeStatus.INVALID
    assert impact["P1"] == NodeStatus.INVALID
    assert impact["A1"] == NodeStatus.INVALID
    assert impact["P2"] == NodeStatus.REQUIRES_REEVALUATION
    assert impact["P3"] == NodeStatus.UNCERTAIN
    assert "A2" not in impact
    assert "A3" not in impact
    assert "A4" not in impact
