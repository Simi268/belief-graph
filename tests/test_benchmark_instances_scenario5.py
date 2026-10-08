from app.benchmark_instances import generate_scenario5_instance
from app.models import DependencyType, NodeType


def test_scenario5_generator_has_expected_affected_and_preserved_sets():
    instance = generate_scenario5_instance(1)

    assert instance.expected_invalidated == frozenset(
        {
            "B1_S0001",
            "C1_S0001",
            "P1_S0001",
            "A1_S0001",
        }
    )

    assert instance.expected_preserved == frozenset(
        {
            "B2_S0001",
            "C2_S0001",
            "P2_S0001",
            "A2_S0001",
        }
    )


def test_scenario5_generator_declares_evidence_arbitration():
    instance = generate_scenario5_instance(1)

    assert instance.evidence_ids == (
        "E1_S0001",
        "E2_S0001",
    )

    assert instance.expected_selected_evidence == "E2_S0001"
    assert instance.expected_rejected_evidence == frozenset(
        {"E1_S0001"}
    )
    assert instance.expected_revision_count == 1


def test_scenario5_generator_preserves_evidence_ordering_across_seeds():
    for seed in range(1, 6):
        instance = generate_scenario5_instance(seed)
        confidence = dict(instance.evidence_confidences)

        assert confidence[
            instance.expected_selected_evidence
        ] > confidence[
            next(
                evidence_id
                for evidence_id in instance.evidence_ids
                if evidence_id
                != instance.expected_selected_evidence
            )
        ]


def test_scenario5_generator_has_valid_dependency_types():
    instance = generate_scenario5_instance(1)

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


def test_scenario5_generator_has_correct_node_types():
    instance = generate_scenario5_instance(1)

    node_types = {
        node.id: node.node_type
        for node in instance.nodes
    }

    assert node_types["B1_S0001"] == NodeType.BELIEF
    assert node_types["C1_S0001"] == NodeType.CONCLUSION
    assert node_types["P1_S0001"] == NodeType.PLAN
    assert node_types["A1_S0001"] == NodeType.ACTION


def test_scenario5_generator_rejects_negative_seed():
    try:
        generate_scenario5_instance(-1)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError(
            "Negative seed should raise ValueError."
        )
