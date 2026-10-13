"""Tests for graph-derived stale-action detection."""

from app.agent import AgentRuntime
from app.benchmark_instances import generate_scenario2_instance
from app.models import DependencyType, NodeStatus, NodeType
from app.stale_action_detector import detect_stale_actions


def build_scenario2_runtime():
    instance = generate_scenario2_instance(seed=1)
    runtime = AgentRuntime()

    for node in instance.nodes:
        if node.node_type == NodeType.BELIEF:
            runtime.create_belief(
                belief_id=node.id,
                content=node.id,
                value="v1",
            )
        else:
            runtime.create_node(
                node_id=node.id,
                node_type=node.node_type,
                content=node.id,
            )

    for edge in instance.edges:
        runtime.add_dependency(
            edge.source,
            edge.target,
            edge.dependency_type,
        )

    return runtime


def test_invalid_plan_marks_dependent_action_stale():
    runtime = build_scenario2_runtime()

    runtime.graph.get_node("P1_S0001").status = NodeStatus.INVALID

    assert "A1_S0001" in detect_stale_actions(runtime.graph)


def test_reevaluation_plan_marks_dependent_action_stale():
    runtime = build_scenario2_runtime()

    runtime.graph.get_node(
        "P2_S0001"
    ).status = NodeStatus.REQUIRES_REEVALUATION

    assert "A2_S0001" in detect_stale_actions(runtime.graph)


def test_uncertain_plan_marks_dependent_action_stale():
    runtime = build_scenario2_runtime()

    runtime.graph.get_node(
        "P3_S0001"
    ).status = NodeStatus.UNCERTAIN

    assert "A3_S0001" in detect_stale_actions(runtime.graph)


def test_active_independent_plan_does_not_mark_action_stale():
    runtime = build_scenario2_runtime()

    stale_actions = detect_stale_actions(runtime.graph)

    assert "A4_S0001" not in stale_actions


def test_detector_does_not_use_benchmark_expected_actions():
    runtime = build_scenario2_runtime()

    runtime.graph.get_node("P1_S0001").status = NodeStatus.INVALID

    stale_actions = detect_stale_actions(runtime.graph)

    assert stale_actions == {"A1_S0001"}