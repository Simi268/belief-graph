from app.benchmark_instances import generate_scenario5_instance
from app.seeded_strategy_adapters import (
    run_seeded_baseline,
    run_seeded_belief_graph,
    run_seeded_memory,
)


def test_scenario5_baseline_does_not_select_evidence():
    result = run_seeded_baseline(
        generate_scenario5_instance(1)
    )

    assert result.metrics["task_success"] is False
    assert result.metrics["evidence_selection_correct"] is False
    assert result.metrics["revision_count"] == 0
    assert result.details["selected_evidence"] is None


def test_scenario5_memory_selects_strong_evidence_but_recomputes_all():
    result = run_seeded_memory(
        generate_scenario5_instance(1)
    )

    assert result.metrics["task_success"] is True
    assert result.metrics["evidence_selection_correct"] is True
    assert result.metrics["revision_count"] == 1
    assert result.metrics["recomputed_node_count"] == 8
    assert result.metrics["unnecessary_recomputation"] == 4
    assert result.details["selected_evidence"] == "E2_S0001"


def test_scenario5_belief_graph_selects_strong_evidence():
    result = run_seeded_belief_graph(
        generate_scenario5_instance(1)
    )

    assert result.metrics["task_success"] is True
    assert result.metrics["evidence_selection_correct"] is True
    assert result.metrics["revision_count"] == 1
    assert result.metrics["affected_node_count"] == 4
    assert result.metrics["invalidated_node_count"] == 4
    assert result.metrics["preserved_node_count"] == 4
    assert result.details["selected_evidence"] == "E2_S0001"


def test_scenario5_belief_graph_preserves_unrelated_branch():
    result = run_seeded_belief_graph(
        generate_scenario5_instance(2)
    )

    assert result.details["preserved_nodes"] == [
        "A2_S0002",
        "B2_S0002",
        "C2_S0002",
        "P2_S0002",
    ]
