import pytest

from app.agent import AgentRuntime
from app.models import DependencyType, NodeType
from app.semantic_recomputation import SemanticRecomputer


def build_graph():
    agent = AgentRuntime()
    agent.create_belief("B1", "Base quantity", value=4)
    agent.create_node("C1", NodeType.CONCLUSION, "Double the base quantity", value=None)
    agent.create_node("P1", NodeType.PLAN, "Add three", value=None)
    agent.add_dependency("B1", "C1", DependencyType.REQUIRES)
    agent.add_dependency("C1", "P1", DependencyType.REQUIRES)
    return agent


def test_semantic_recomputation_uses_predecessor_values_and_updates_node():
    agent = build_graph()
    recomputer = SemanticRecomputer(
        agent,
        {
            "C1": lambda node, parents: parents["B1"] * 2,
            "P1": lambda node, parents: parents["C1"] + 3,
        },
    )

    first = recomputer(agent.graph.get_node("C1"))
    second = recomputer(agent.graph.get_node("P1"))

    assert first["new_value"] == 8
    assert second["new_value"] == 11
    assert agent.graph.get_node("C1").value == 8
    assert agent.graph.get_node("P1").value == 11


def test_semantic_recomputation_uses_updated_upstream_value():
    agent = build_graph()
    recomputer = SemanticRecomputer(
        agent,
        {
            "C1": lambda node, parents: parents["B1"] * 2,
            "P1": lambda node, parents: parents["C1"] + 3,
        },
    )

    recomputer(agent.graph.get_node("C1"))
    recomputer(agent.graph.get_node("P1"))
    agent.graph.get_node("B1").value = 10
    recomputer(agent.graph.get_node("C1"))
    result = recomputer(agent.graph.get_node("P1"))

    assert result["new_value"] == 23


def test_missing_evaluator_fails_explicitly():
    agent = build_graph()
    recomputer = SemanticRecomputer(agent, {})

    with pytest.raises(KeyError, match="No semantic evaluator"):
        recomputer(agent.graph.get_node("C1"))


def test_belief_nodes_are_not_silently_recomputed():
    agent = build_graph()
    recomputer = SemanticRecomputer(agent, {"C1": lambda node, parents: 0})

    with pytest.raises(ValueError, match="source fact"):
        recomputer(agent.graph.get_node("B1"))


def test_recompute_nodes_reports_failures_without_hiding_them():
    agent = build_graph()
    recomputer = SemanticRecomputer(
        agent,
        {"C1": lambda node, parents: parents["B1"] * 2},
    )

    result = recomputer.recompute_nodes(["C1", "P1"])

    assert result["success"] is False
    assert result["recomputed_node_ids"] == ["C1"]
    assert result["failures"][0]["node_id"] == "P1"
