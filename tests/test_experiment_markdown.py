import json

from app.experiment_markdown import ExperimentMarkdownReport


def test_markdown_report_is_generated(tmp_path):
    input_path = tmp_path / "experiment.json"
    output_path = tmp_path / "report.md"

    input_path.write_text(
        json.dumps(
            {
                "seeds": [1, 2],
                "results": [
                    {"strategy": "baseline"},
                    {"strategy": "memory"},
                ],
                "aggregates": [
                    {
                        "strategy": "baseline",
                        "metrics": [
                            {
                                "metric": "task_success",
                                "mean": 0.0,
                                "population_std": 0.0,
                            }
                        ],
                    },
                    {
                        "strategy": "memory",
                        "metrics": [
                            {
                                "metric": "task_success",
                                "mean": 1.0,
                                "population_std": 0.0,
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = ExperimentMarkdownReport.from_json(
        input_path,
        output_path,
    )

    assert result == output_path
    assert output_path.exists()

    content = output_path.read_text(
        encoding="utf-8"
    )

    assert "# Belief-Graph Experiment Report" in content
    assert "Experiment objective" in content
    assert "Strategy comparison" in content
    assert "baseline" in content
    assert "memory" in content


def test_markdown_report_contains_reproducibility_section(tmp_path):
    input_path = tmp_path / "experiment.json"
    output_path = tmp_path / "report.md"

    input_path.write_text(
        json.dumps(
            {
                "seeds": [1],
                "results": [],
                "aggregates": [],
            }
        ),
        encoding="utf-8",
    )

    ExperimentMarkdownReport.from_json(
        input_path,
        output_path,
    )

    content = output_path.read_text(
        encoding="utf-8"
    )

    assert "## Reproducibility" in content
    assert "deterministic seeded benchmark instances" in content