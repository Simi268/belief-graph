from app.scenario import APIVersionChangeScenario


def test_api_version_change_scenario():

    scenario = APIVersionChangeScenario()

    result = scenario.run()

    assert result.scenario_id == (
        "api-version-change"
    )

    assert result.initial_belief == "B1"

    assert result.revised_belief == "B2"

    assert result.old_action == "A1"

    assert result.new_action == "A4"

    assert result.recovery_successful is True

    assert result.total_nodes > 0

    assert result.propagation_depth >= 1

    assert "B1" in result.impact_states

    assert "C1" in result.impact_states