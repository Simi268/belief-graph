import pytest

from app.benchmark_instances import (
    generate_scenario1_instance,
    generate_scenario2_instance,
    generate_scenario3_instance,
    generate_scenario4_instance,
    generate_scenario5_instance,
    generate_scenario6_instance,
    generate_scenario7_instance,
)
from app.seeded_strategy_adapters import run_seeded_baseline


GENERATORS = [
    generate_scenario1_instance,
    generate_scenario2_instance,
    generate_scenario3_instance,
    generate_scenario4_instance,
    generate_scenario5_instance,
    generate_scenario6_instance,
    generate_scenario7_instance,
]


@pytest.mark.parametrize("generator", GENERATORS)
def test_baseline_does_not_claim_dependency_aware_impact_detection(
    generator,
):
    instance = generator(1)

    result = run_seeded_baseline(instance)

    assert result.metrics["affected_node_count"] == 0
    assert result.metrics["invalidated_node_count"] == 0
    assert result.metrics["recomputed_node_count"] == 0
    assert result.metrics["preserved_node_count"] == 0
    assert result.metrics["preservation_ratio"] == 0.0

    assert result.details["strategy_detected_affected_nodes"] == []
    assert (
        result.details["ground_truth_affected_node_count"]
        == len(instance.affected_nodes)
    )
    assert (
        set(result.details["ground_truth_affected_nodes"])
        == set(instance.affected_nodes)
    )
    assert (
        result.details["ground_truth_preserved_node_count"]
        == len(instance.expected_preserved)
    )


@pytest.mark.parametrize("generator", GENERATORS)
def test_baseline_still_reports_stale_actions(
    generator,
):
    instance = generator(1)

    result = run_seeded_baseline(instance)

    assert result.metrics["task_success"] is False
    assert result.metrics["stale_actions"] == len(
        instance.expected_stale_actions
    )


def test_scenario5_baseline_evidence_metrics_remain_explicit():
    instance = generate_scenario5_instance(1)

    result = run_seeded_baseline(instance)

    assert result.metrics["evidence_selection_correct"] is False
    assert result.metrics["revision_count"] == 0
    assert result.details["selected_evidence"] is None
