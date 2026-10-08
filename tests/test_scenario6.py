from app.scenario6 import ToolUnavailableScenario
from app.models import NodeStatus


def test_tool_becomes_unavailable():
    scenario = ToolUnavailableScenario()

    result = scenario.run()

    assert result.tool_available_before is True
    assert result.tool_available_after is False


def test_tool_dependent_branch_is_invalidated():
    result = ToolUnavailableScenario().run()

    assert set(result.invalidated_nodes) == {
        "B1",
        "C1",
        "P1",
        "A1",
    }


def test_independent_branch_is_preserved():
    result = ToolUnavailableScenario().run()

    assert set(result.preserved_nodes) == {
        "B2",
        "C2",
        "P2",
        "A2",
    }


def test_no_soft_impact_is_created():
    result = ToolUnavailableScenario().run()

    assert result.reevaluation_nodes == []
    assert result.uncertain_nodes == []


def test_affected_region_is_exact():
    result = ToolUnavailableScenario().run()

    assert set(result.affected_nodes) == {
        "B1",
        "C1",
        "P1",
        "A1",
    }


def test_propagation_depth():
    result = ToolUnavailableScenario().run()

    assert result.propagation_depth == 3


def test_preservation_ratio():
    result = ToolUnavailableScenario().run()

    assert result.preservation_ratio == 0.5


def test_node_counts():
    result = ToolUnavailableScenario().run()

    assert result.total_original_nodes == 8
    assert result.affected_node_count == 4
    assert result.invalidated_node_count == 4
    assert result.preserved_node_count == 4


def test_graph_statuses():
    scenario = ToolUnavailableScenario()
    scenario.run()

    assert scenario.graph.get_node("B1").status == NodeStatus.INVALID
    assert scenario.graph.get_node("C1").status == NodeStatus.INVALID
    assert scenario.graph.get_node("P1").status == NodeStatus.INVALID
    assert scenario.graph.get_node("A1").status == NodeStatus.INVALID

    assert scenario.graph.get_node("B2").status == NodeStatus.ACTIVE
    assert scenario.graph.get_node("C2").status == NodeStatus.ACTIVE
    assert scenario.graph.get_node("P2").status == NodeStatus.ACTIVE
    assert scenario.graph.get_node("A2").status == NodeStatus.ACTIVE