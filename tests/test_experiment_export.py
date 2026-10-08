import json

from app.benchmark_instances import generate_scenario2_instance
from app.experiment import ExperimentRunner
from app.experiment_export import ExperimentExporter
from app.seeded_strategy_adapters import seeded_strategy_evaluators


def build_report():
    runner = ExperimentRunner(
        seeded_strategy_evaluators()
    )

    return runner.run(
        seeds=[1, 2, 3, 4, 5],
        generator=generate_scenario2_instance,
    )


def test_report_can_be_exported_to_json(tmp_path):
    report = build_report()

    output_path = tmp_path / "experiment.json"

    exported_path = ExperimentExporter.report_to_json(
        report,
        output_path,
    )

    assert exported_path == output_path
    assert output_path.exists()

    data = json.loads(
        output_path.read_text(encoding="utf-8")
    )

    assert data["seeds"] == [1, 2, 3, 4, 5]

    assert len(data["results"]) == 15
    assert len(data["aggregates"]) == 3


def test_export_preserves_belief_graph_results(tmp_path):
    report = build_report()

    output_path = tmp_path / "experiment.json"

    ExperimentExporter.report_to_json(
        report,
        output_path,
    )

    data = json.loads(
        output_path.read_text(encoding="utf-8")
    )

    belief_graph = next(
        result
        for result in data["results"]
        if result["strategy"] == "belief_graph"
    )

    assert belief_graph["metrics"]["task_success"] is True
    assert belief_graph["metrics"]["preservation_ratio"] == 0.5
    assert belief_graph["metrics"]["unnecessary_recomputation"] == 0