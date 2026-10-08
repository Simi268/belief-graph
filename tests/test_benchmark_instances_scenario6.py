from app.benchmark_instances import generate_scenario6_instance
from app.models import DependencyType, NodeType


def test_scenario6_generator_has_expected_affected_branch():
    instance = generate_scenario6_instance(1)

    assert instance.changed_belief == "B1_S0001"
    assert instance.expected_invalidated == frozenset(
        {
            "B1_S0001",
            "C1_S0001",
            "P1_S0001",
            "A1_S0001",
        }
    )


def test_scenario6_generator_preserves_independent_core_branch():
    instance = generate_scenario6_instance(1)

    assert {
        "B2_S0001",
        "C2_S0001",
        "P2_S0001",
        "A2_S0001",
    }.issubset(instance.expected_preserved)


def test_scenario6_generator_declares_tool_failure_metadata():
    instance = generate_scenario6_instance(1)

    assert instance.metadata == {
        "scenario_type": "tool_unavailable_v1",
        "tool_id": "T1",
        "tool_available_before": True,
        "tool_available_after": False,
        "failure_mode": "required_tool_unavailable",
    }


def test_scenario6_generator_changes_size_across_seeds():
    instance1 = generate_scenario6_instance(1)
    instance2 = generate_scenario6_instance(2)
    instance3 = generate_scenario6_instance(3)

    assert len(instance1.nodes) != len(instance3.nodes)
    assert len(instance2.nodes) != len(instance3.nodes)


def test_scenario6_generator_dependency_chain_is_requires():
    instance = generate_scenario6_instance(1)

    edge_map = {
        (edge.source, edge.target): edge.dependency_type
        for edge in instance.edges
    }

    assert edge_map[
        ("B1_S0001", "C1_S0001")
    ] == DependencyType.REQUIRES

    assert edge_map[
        ("C1_S0001", "P1_S0001")
    ] == DependencyType.REQUIRES

    assert edge_map[
        ("P1_S0001", "A1_S0001")
    ] == DependencyType.REQUIRES


def test_scenario6_generator_node_types_are_correct():
    instance = generate_scenario6_instance(1)

    node_types = {
        node.id: node.node_type
        for node in instance.nodes
    }

    assert node_types["B1_S0001"] == NodeType.BELIEF
    assert node_types["C1_S0001"] == NodeType.CONCLUSION
    assert node_types["P1_S0001"] == NodeType.PLAN
    assert node_types["A1_S0001"] == NodeType.ACTION


def test_scenario6_generator_rejects_negative_seed():
    try:
        generate_scenario6_instance(-1)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError(
            "Negative seed should raise ValueError."
        )
