"""Ground-truth validation for Scenario 1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.scenario1_runtime_experiment import (
    run_belief_graph_runtime_experiment,
)


@dataclass
class ValidationResult:
    scenario_id: str
    instance_id: str
    task_success: bool
    final_status: str
    ground_truth_validation: dict[str, Any]
    validation_passed: bool


def validate_scenario1(seed: int = 1) -> dict[str, Any]:
    execution = run_belief_graph_runtime_experiment(seed=seed)
    validation = execution.ground_truth_validation

    result = ValidationResult(
        scenario_id="scenario1",
        instance_id=validation["instance_id"],
        task_success=execution.success,
        final_status=execution.final_status,
        ground_truth_validation=validation,
        validation_passed=(
            execution.success and validation["passed"]
        ),
    )

    return asdict(result)


if __name__ == "__main__":
    import json

    print(json.dumps(validate_scenario1(), indent=2))