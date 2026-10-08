from app.benchmark_instances import generate_scenario2_instance


def test_seeded_instances_are_deterministic():
    first = generate_scenario2_instance(1)
    second = generate_scenario2_instance(1)

    assert first == second


def test_seed_changes_instance_identity_and_node_namespace():
    first = generate_scenario2_instance(1)
    second = generate_scenario2_instance(2)

    assert first.instance_id != second.instance_id
    assert first.seed != second.seed
    assert first.node_ids.isdisjoint(second.node_ids)


def test_scenario2_ground_truth_preserves_soft_state_boundaries():
    instance = generate_scenario2_instance(7)

    assert {x.split("_")[0] for x in instance.expected_invalidated} == {
        "B1", "C1", "P1", "A1"
    }
    assert {x.split("_")[0] for x in instance.expected_reevaluation} == {"P2"}
    assert {x.split("_")[0] for x in instance.expected_uncertain} == {"P3"}
    assert {x.split("_")[0] for x in instance.expected_preserved} == {
        "A2", "A3", "B4", "C4", "P4", "A4"
    }
    assert {x.split("_")[0] for x in instance.expected_stale_actions} == {
        "A1", "A2", "A3"
    }


def test_optional_branches_change_ground_truth_explicitly():
    instance = generate_scenario2_instance(
        9,
        support_branch=False,
        context_branch=True,
        unrelated_branch=True,
    )

    assert instance.expected_reevaluation == frozenset()
    assert {x.split("_")[0] for x in instance.expected_uncertain} == {"P3"}
    assert {x.split("_")[0] for x in instance.expected_stale_actions} == {
        "A1", "A3"
    }
    assert "A2_S0009" not in instance.node_ids
