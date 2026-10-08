from dataclasses import dataclass

from .models import NodeStatus


@dataclass
class EvaluationResult:
    scenario_id: str

    recovery_successful: bool

    total_nodes: int

    invalidated_nodes: int
    reevaluation_nodes: int
    uncertain_nodes: int

    preserved_nodes: int

    propagation_depth: int

    recovery_steps: int

    selective_recovery_ratio: float


class EvaluationEngine:

    def evaluate(
        self,
        scenario_result,
        total_nodes: int
    ):

        impact_states = getattr(
            scenario_result,
            "impact_states",
            {}
        )

        initial_node_ids = getattr(
            scenario_result,
            "initial_node_ids",
            list(impact_states.keys())
        )

        invalidated = 0
        reevaluation = 0
        uncertain = 0

        for node_id in initial_node_ids:

            status = impact_states.get(
                node_id
            )

            if status == NodeStatus.INVALID.value:

                invalidated += 1

            elif (
                status
                == NodeStatus.REQUIRES_REEVALUATION.value
            ):

                reevaluation += 1

            elif status == NodeStatus.UNCERTAIN.value:

                uncertain += 1

        affected_nodes = (
            invalidated
            + reevaluation
            + uncertain
        )

        preserved = max(
            total_nodes - affected_nodes,
            0
        )

        selective_ratio = (
            preserved / total_nodes
            if total_nodes > 0
            else 0.0
        )

        propagation_depth = (
            scenario_result.propagation_depth
            if hasattr(
                scenario_result,
                "propagation_depth"
            )
            else 0
        )

        return EvaluationResult(
            scenario_id=(
                scenario_result.scenario_id
            ),

            recovery_successful=(
                scenario_result.recovery_successful
            ),

            total_nodes=total_nodes,

            invalidated_nodes=invalidated,

            reevaluation_nodes=reevaluation,

            uncertain_nodes=uncertain,

            preserved_nodes=preserved,

            propagation_depth=(
                propagation_depth
            ),

            recovery_steps=(
                scenario_result.recovery_steps
            ),

            selective_recovery_ratio=(
                selective_ratio
            )
        )