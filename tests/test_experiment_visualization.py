from app.benchmark_instances import generate_scenario2_instance
from app.experiment import ExperimentRunner
from app.experiment_visualization import ExperimentVisualizationData
from app.seeded_strategy_adapters import seeded_strategy_evaluators


def build_report():
    runner = ExperimentRunner(
        seeded_strategy_evaluators()
    )

    return runner.run(
        seeds=[1, 2, 3, 4, 5],
        generator=generate_scenario2_instance,
    )


def test_metric_points_use_measured_experiment_values():
    report = build_report()

    points = ExperimentVisualizationData.metric_points(
        report,
        "unnecessary_recomputation",
    )

    values = {
        point.strategy: point.value
        for point in points
    }

    assert values == {
        "baseline": 0.0,
        "memory": 6.0,
        "belief_graph": 0.0,
    }


def test_visualization_data_contains_all_strategies():
    report = build_report()

    data = ExperimentVisualizationData.to_chart_data(
        report,
        "preservation_ratio",
    )

    assert len(data) == 3

    assert {
        item["strategy"]
        for item in data
    } == {
        "baseline",
        "memory",
        "belief_graph",
    }


def test_missing_metric_is_rejected():
    report = build_report()

    try:
        ExperimentVisualizationData.metric_points(
            report,
            "does_not_exist",
        )
    except ValueError as exc:
        assert "does_not_exist" in str(exc)
    else:
        raise AssertionError(
            "Expected missing metric to raise ValueError."
        )

def test_preservation_ratio_uses_measured_values():
    report = build_report()

    points = ExperimentVisualizationData.metric_points(
        report,
        "preservation_ratio",
    )

    values = {
        point.strategy: point.value
        for point in points
    }

    assert values == {
        "baseline": 0.0,
        "memory": 0.0,
        "belief_graph": 0.5,
    }

def test_strategy_comparison_contains_requested_metrics():
    report = build_report()

    comparison = ExperimentVisualizationData.strategy_comparison(
        report,
        (
            "task_success",
            "preservation_ratio",
            "unnecessary_recomputation",
        ),
    )

    assert set(comparison) == {
        "baseline",
        "memory",
        "belief_graph",
    }

    assert comparison["baseline"] == {
        "task_success": 0.0,
        "preservation_ratio": 0.0,
        "unnecessary_recomputation": 0.0,
    }

    assert comparison["memory"] == {
        "task_success": 1.0,
        "preservation_ratio": 0.0,
        "unnecessary_recomputation": 6.0,
    }

    assert comparison["belief_graph"] == {
        "task_success": 1.0,
        "preservation_ratio": 0.5,
        "unnecessary_recomputation": 0.0,
    }

def test_strategy_comparison_rejects_missing_metric():
    report = build_report()

    try:
        ExperimentVisualizationData.strategy_comparison(
            report,
            ("not_a_real_metric",),
        )
    except ValueError as exc:
        assert "not_a_real_metric" in str(exc)
    else:
        raise AssertionError(
            "Expected missing metric to raise ValueError."
        )

def test_dashboard_data_contains_core_experiment_metrics():
    report = build_report()

    dashboard = ExperimentVisualizationData.dashboard_data(
        report
    )

    assert len(dashboard) == 3

    belief_graph = next(
        item
        for item in dashboard
        if item.strategy == "belief_graph"
    )

    assert belief_graph.task_success == 1.0
    assert belief_graph.recovery_success == 1.0
    assert belief_graph.preservation_ratio == 0.5
    assert belief_graph.affected_node_count == 6.0
    assert belief_graph.invalidated_node_count == 4.0
    assert belief_graph.recomputed_node_count == 0.0
    assert belief_graph.unnecessary_recomputation == 0.0