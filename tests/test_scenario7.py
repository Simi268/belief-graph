from app.models import NodeStatus
from app.scenario7 import StaleInformationScenario


def test_stale_information_is_detected():
    scenario = StaleInformationScenario()

    result = scenario.mark_information_stale()

    assert result["source"] == "documentation-v1"
    assert result["fresh_before"] is True
    assert result["stale_after"] is True


def test_stale_information_invalidates_dependent_belief():
    scenario = StaleInformationScenario()

    scenario.mark_information_stale()
    scenario.revise_stale_belief()

    assert (
        scenario.agent.graph.get_node("B1").status
        == NodeStatus.INVALID
    )


def test_dependent_chain_is_invalidated():
    result = StaleInformationScenario().run()

    assert set(result.invalidated_nodes) == {
        "B1",
        "C1",
        "P1",
        "A1",
    }


def test_no_reevaluation_nodes_are_created():
    result = StaleInformationScenario().run()

    assert result.reevaluation_nodes == []
    assert result.reevaluation_node_count == 0


def test_no_uncertain_nodes_are_created():
    result = StaleInformationScenario().run()

    assert result.uncertain_nodes == []
    assert result.uncertain_node_count == 0


def test_independent_branch_is_preserved():
    result = StaleInformationScenario().run()

    assert set(result.preserved_nodes) == {
        "B2",
        "C2",
        "P2",
        "A2",
    }


def test_exact_affected_region():
    result = StaleInformationScenario().run()

    assert set(result.affected_nodes) == {
        "B1",
        "C1",
        "P1",
        "A1",
    }


def test_propagation_depth_is_three():
    result = StaleInformationScenario().run()

    assert result.propagation_depth == 3


def test_preservation_ratio_is_half():
    result = StaleInformationScenario().run()

    assert result.preservation_ratio == 0.5


def test_result_counts_are_consistent():
    result = StaleInformationScenario().run()

    assert result.affected_node_count == 4
    assert result.invalidated_node_count == 4
    assert result.reevaluation_node_count == 0
    assert result.uncertain_node_count == 0
    assert result.preserved_node_count == 4
    assert result.total_original_nodes == 8
    assert result.revision_count == 1