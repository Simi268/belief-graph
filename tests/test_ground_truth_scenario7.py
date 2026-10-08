from app.ground_truth import SCENARIO_7_GROUND_TRUTH
from app.models import NodeStatus, NodeType


def test_scenario7_ground_truth_validates():
    SCENARIO_7_GROUND_TRUTH.validate()


def test_scenario7_original_nodes_are_complete():
    gt = SCENARIO_7_GROUND_TRUTH

    assert gt.original_node_ids == {
        "B1",
        "C1",
        "P1",
        "A1",
        "B2",
        "C2",
        "P2",
        "A2",
    }


def test_scenario7_expected_impact():
    gt = SCENARIO_7_GROUND_TRUTH

    assert gt.expected_impact == {
        "B1": NodeStatus.INVALID,
        "C1": NodeStatus.INVALID,
        "P1": NodeStatus.INVALID,
        "A1": NodeStatus.INVALID,
    }


def test_scenario7_preserved_nodes():
    gt = SCENARIO_7_GROUND_TRUTH

    assert gt.expected_preserved == {
        "B2",
        "C2",
        "P2",
        "A2",
    }


def test_scenario7_stale_action():
    gt = SCENARIO_7_GROUND_TRUTH

    assert gt.expected_stale_actions == {"A1"}


def test_scenario7_node_types():
    gt = SCENARIO_7_GROUND_TRUTH

    node_types = {
        node.id: node.node_type
        for node in gt.original_nodes
    }

    assert node_types == {
        "B1": NodeType.BELIEF,
        "C1": NodeType.CONCLUSION,
        "P1": NodeType.PLAN,
        "A1": NodeType.ACTION,
        "B2": NodeType.BELIEF,
        "C2": NodeType.CONCLUSION,
        "P2": NodeType.PLAN,
        "A2": NodeType.ACTION,
    }


def test_scenario7_expected_sets_partition_original_nodes():
    gt = SCENARIO_7_GROUND_TRUTH

    all_expected = (
        gt.expected_invalidated
        | gt.expected_reevaluation
        | gt.expected_uncertain
        | gt.expected_preserved
    )

    assert all_expected == gt.original_node_ids


def test_scenario7_edges_reference_original_nodes():
    gt = SCENARIO_7_GROUND_TRUTH

    original = gt.original_node_ids

    for edge in gt.edges:
        assert edge.source in original
        assert edge.target in original