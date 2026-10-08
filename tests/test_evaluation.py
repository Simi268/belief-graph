from app.scenario import APIVersionChangeScenario
from app.evaluation import EvaluationEngine


def test_evaluation_engine():

    scenario = APIVersionChangeScenario()

    scenario_result = scenario.run()

    evaluator = EvaluationEngine()

    result = evaluator.evaluate(
        scenario_result=scenario_result,
        total_nodes=len(
            scenario_result.initial_node_ids
        )
    )

    assert result.scenario_id == (
        "api-version-change"
    )

    assert result.recovery_successful is True

    assert result.total_nodes == (
        len(
            scenario_result.initial_node_ids
        )
    )

    assert result.invalidated_nodes > 0

    assert result.reevaluation_nodes >= 0

    assert result.uncertain_nodes >= 0

    assert result.preserved_nodes >= 0

    assert result.preserved_nodes == (
        result.total_nodes
        - result.invalidated_nodes
        - result.reevaluation_nodes
        - result.uncertain_nodes
    )

    assert result.propagation_depth == (
        scenario_result.propagation_depth
    )

    assert result.recovery_steps == 4

    assert (
        0.0
        <= result.selective_recovery_ratio
        <= 1.0
    )