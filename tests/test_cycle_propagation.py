import pytest

from app.graph import BeliefGraph
from app.models import BeliefNode, NodeStatus, NodeType, DependencyType


def build_cyclic_graph():
    graph = BeliefGraph()

    nodes = [
        BeliefNode(id="B1", node_type=NodeType.BELIEF, content="Changed belief"),
        BeliefNode(id="C1", node_type=NodeType.CONCLUSION, content="Conclusion"),
        BeliefNode(id="P1", node_type=NodeType.PLAN, content="Plan"),
        BeliefNode(id="A1", node_type=NodeType.ACTION, content="Action"),
    ]

    for node in nodes:
        graph.add_node(node)

    graph.add_dependency("B1", "C1", DependencyType.REQUIRES)
    graph.add_dependency("C1", "P1", DependencyType.REQUIRES)
    graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

    # Add a cycle: A1 -> C1.
    graph.add_dependency("A1", "C1", DependencyType.REQUIRES)

    return graph


def test_single_belief_propagation_terminates_on_cycle():
    graph = build_cyclic_graph()

    result = graph.propagate_state_impact(
        "B1",
        initial_status=NodeStatus.INVALID,
    )

    assert set(result) == {"C1", "P1", "A1"}
    assert all(
        details["impact"] == NodeStatus.INVALID
        for details in result.values()
    )


def test_multi_belief_propagation_terminates_on_cycle():
    graph = build_cyclic_graph()

    result = graph.analyze_multi_belief_impact(
        ["B1"],
        initial_status=NodeStatus.INVALID,
    )

    assert set(result) == {"C1", "P1", "A1"}
    assert all(
        details["impact"] == NodeStatus.INVALID
        for details in result.values()
    )


def test_multi_belief_propagation_preserves_multiple_sources_in_cycle():
    graph = build_cyclic_graph()

    graph.add_node(
        BeliefNode(
            id="B2",
            node_type=NodeType.BELIEF,
            content="Second changed belief",
        )
    )
    graph.add_dependency("B2", "P1", DependencyType.REQUIRES)

    result = graph.analyze_multi_belief_impact(
        ["B1", "B2"],
        initial_status=NodeStatus.INVALID,
    )

    assert set(result["P1"]["affected_by"]) == {"B1", "B2"}
    assert set(result["A1"]["affected_by"]) == {"B1", "B2"}

def test_multiple_paths_preserve_causal_attribution():
    graph = BeliefGraph()

    nodes = [
        BeliefNode(id="B1", node_type=NodeType.BELIEF, content="Changed belief"),
        BeliefNode(id="C1", node_type=NodeType.CONCLUSION, content="Conclusion 1"),
        BeliefNode(id="C2", node_type=NodeType.CONCLUSION, content="Conclusion 2"),
        BeliefNode(id="P1", node_type=NodeType.PLAN, content="Shared plan"),
        BeliefNode(id="A1", node_type=NodeType.ACTION, content="Dependent action"),
    ]

    for node in nodes:
        graph.add_node(node)

    graph.add_dependency("B1", "C1", DependencyType.REQUIRES)
    graph.add_dependency("B1", "C2", DependencyType.REQUIRES)
    graph.add_dependency("C1", "P1", DependencyType.REQUIRES)
    graph.add_dependency("C2", "P1", DependencyType.REQUIRES)
    graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

    result = graph.analyze_multi_belief_impact(
        ["B1"],
        initial_status=NodeStatus.INVALID,
    )

    assert {"C1", "C2", "P1", "A1"} <= set(result)

    assert set(result["P1"]["affected_by"]) == {"B1"}
    assert set(result["A1"]["affected_by"]) == {"B1"}

    assert result["P1"]["impact"] == NodeStatus.INVALID
    assert result["A1"]["impact"] == NodeStatus.INVALID

def test_invalid_state_preserved_when_new_soft_source_arrives():
    graph = BeliefGraph()

    nodes = [
        BeliefNode(id="B1", node_type=NodeType.BELIEF, content="Invalidating belief"),
        BeliefNode(id="B2", node_type=NodeType.BELIEF, content="Uncertain belief"),
        BeliefNode(id="P1", node_type=NodeType.PLAN, content="Shared plan"),
        BeliefNode(id="A1", node_type=NodeType.ACTION, content="Dependent action"),
    ]

    for node in nodes:
        graph.add_node(node)

    # B1 invalidates P1 directly.
    graph.add_dependency("B1", "P1", DependencyType.REQUIRES)

    # B2 reaches P1 through a softer impact.
    graph.add_dependency("B2", "P1", DependencyType.SUPPORTS)

    # P1's impact must propagate to A1.
    graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

    result = graph.analyze_multi_belief_impact(
        ["B1", "B2"],
        initial_status=NodeStatus.INVALID,
    )

    assert result["P1"]["impact"] == NodeStatus.INVALID
    assert set(result["P1"]["affected_by"]) == {"B1", "B2"}

    assert result["A1"]["impact"] == NodeStatus.INVALID
    assert set(result["A1"]["affected_by"]) == {"B1", "B2"}

def test_invalid_impact_wins_over_soft_impact_from_another_source():
    graph = BeliefGraph()

    nodes = [
        BeliefNode(id="B1", node_type=NodeType.BELIEF, content="Hard invalidation source"),
        BeliefNode(id="B2", node_type=NodeType.BELIEF, content="Soft impact source"),
        BeliefNode(id="P1", node_type=NodeType.PLAN, content="Shared plan"),
        BeliefNode(id="A1", node_type=NodeType.ACTION, content="Dependent action"),
    ]

    for node in nodes:
        graph.add_node(node)

    # B1 produces a hard INVALID impact on P1.
    graph.add_dependency("B1", "P1", DependencyType.REQUIRES)

    # B2 produces only REQUIRES_REEVALUATION on P1.
    graph.add_dependency("B2", "P1", DependencyType.SUPPORTS)

    # The hard-invalidated plan must propagate INVALID to A1.
    graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

    result = graph.analyze_multi_belief_impact(
        ["B1", "B2"],
        initial_status=NodeStatus.INVALID,
    )

    # The highest-priority impact must win.
    assert result["P1"]["impact"] == NodeStatus.INVALID

    # Both original causal sources must be retained.
    assert set(result["P1"]["affected_by"]) == {"B1", "B2"}

    # Both sources must be propagated downstream.
    assert result["A1"]["impact"] == NodeStatus.INVALID
    assert set(result["A1"]["affected_by"]) == {"B1", "B2"}

def test_conflicting_impacts_are_independent_of_root_order():
    def build_graph():
        graph = BeliefGraph()

        nodes = [
            BeliefNode(id="B1", node_type=NodeType.BELIEF, content="Hard impact source"),
            BeliefNode(id="B2", node_type=NodeType.BELIEF, content="Soft impact source"),
            BeliefNode(id="P1", node_type=NodeType.PLAN, content="Shared plan"),
            BeliefNode(id="A1", node_type=NodeType.ACTION, content="Dependent action"),
        ]

        for node in nodes:
            graph.add_node(node)

        graph.add_dependency("B1", "P1", DependencyType.REQUIRES)
        graph.add_dependency("B2", "P1", DependencyType.SUPPORTS)
        graph.add_dependency("P1", "A1", DependencyType.REQUIRES)

        return graph

    result_forward = build_graph().analyze_multi_belief_impact(
        ["B1", "B2"],
        initial_status=NodeStatus.INVALID,
    )

    result_reverse = build_graph().analyze_multi_belief_impact(
        ["B2", "B1"],
        initial_status=NodeStatus.INVALID,
    )

    for node_id in ("P1", "A1"):
        assert result_forward[node_id]["impact"] == result_reverse[node_id]["impact"]
        assert set(result_forward[node_id]["affected_by"]) == set(
            result_reverse[node_id]["affected_by"]
        )