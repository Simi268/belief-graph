import json
from pathlib import Path

from .experiment import ExperimentReport


class ExperimentExporter:
    @staticmethod
    def report_to_json(
        report: ExperimentReport,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "seeds": list(report.seeds),
            "results": [
                {
                    "seed": result.seed,
                    "instance_id": result.instance_id,
                    "strategy": result.strategy,
                    "metrics": result.metrics,
                    "details": result.details,
                }
                for result in report.results
            ],
            "aggregates": [
                {
                    "strategy": aggregate.strategy,
                    "instances": aggregate.instances,
                    "metrics": [
                        {
                            "metric": metric.metric,
                            "mean": metric.mean,
                            "population_std": metric.population_std,
                        }
                        for metric in aggregate.metrics
                    ],
                }
                for aggregate in report.aggregates
            ],
        }

        path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        return path