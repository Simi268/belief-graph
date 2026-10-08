from app.benchmark_instances import generate_scenario2_instance
from app.experiment import ExperimentRunner
from app.experiment_report import ExperimentReportBuilder
from app.seeded_strategy_adapters import seeded_strategy_evaluators


def build_report():
    runner = ExperimentRunner(
        seeded_strategy_evaluators()
    )

    return runner.run(
        seeds=[1, 2, 3, 4, 5],
        generator=generate_scenario2_instance,
    )


def test_report_contains_all_strategies_and_metrics():
    report = build_report()

    summary = ExperimentReportBuilder.build(report)

    assert summary.seeds == (1, 2, 3, 4, 5)

    assert set(summary.strategies) == {
        "baseline",
        "memory",
        "belief_graph",
    }

    metric_names = {
        comparison.metric
        for comparison in summary.comparisons
    }

    assert "task_success" in metric_names
    assert "preservation_ratio" in metric_names
    assert "unnecessary_recomputation" in metric_names


def test_report_preserves_measured_values():
    report = build_report()

    summary = ExperimentReportBuilder.build(report)

    preservation = next(
        comparison
        for comparison in summary.comparisons
        if comparison.metric == "preservation_ratio"
    )

    assert preservation.values["belief_graph"] == 0.5


def test_report_can_render_text():
    report = build_report()

    summary = ExperimentReportBuilder.build(report)

    text = ExperimentReportBuilder.to_text(summary)

    assert "BELIEF-GRAPH EXPERIMENT" in text
    assert "baseline" in text
    assert "memory" in text
    assert "belief_graph" in text


def test_report_can_render_table():
    report = build_report()

    summary = ExperimentReportBuilder.build(report)

    table = ExperimentReportBuilder.to_table(summary)

    assert "Metric" in table
    assert "baseline" in table
    assert "memory" in table
    assert "belief_graph" in table
    assert "Preservation ratio" in table


def test_report_formats_success_metrics_as_percentages():
    report = build_report()

    summary = ExperimentReportBuilder.build(report)

    text = ExperimentReportBuilder.to_text(summary)

    assert "Task success:" in text
    assert "baseline: 0.0%" in text
    assert "memory: 100.0%" in text
    assert "belief_graph: 100.0%" in text


def test_report_formats_node_metrics_as_integers():
    report = build_report()

    summary = ExperimentReportBuilder.build(report)

    table = ExperimentReportBuilder.to_table(summary)

    assert "Affected nodes" in table
    assert "12" in table
    assert "6" in table