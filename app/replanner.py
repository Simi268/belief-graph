from .models import (
    BeliefNode,
    NodeType,
    NodeStatus,
    DependencyType
)


class Replanner:

    def __init__(self, graph):
        self.graph = graph

    def replan_api_action(
        self,
        old_belief_id: str,
        new_belief_id: str,
        old_action_id: str,
        new_action_id: str
    ):
        old_belief = self.graph.get_node(
            old_belief_id
        )

        new_belief = self.graph.get_node(
            new_belief_id
        )

        old_action = self.graph.get_node(
            old_action_id
        )

        if old_belief.status != NodeStatus.INVALID:
            raise ValueError(
                "Old belief must be invalid before replanning."
            )

        if new_belief.status != NodeStatus.ACTIVE:
            raise ValueError(
                "New belief must be active before replanning."
            )

        if old_action.status != NodeStatus.INVALID:
            raise ValueError(
                "Old action must be invalid before replanning."
            )

        new_action = BeliefNode(
            id=new_action_id,
            node_type=NodeType.ACTION,
            content=(
                f"Call customer API using "
                f"{new_belief.value}"
            ),
            value=new_belief.value,
            confidence=new_belief.confidence,
            source="replanner"
        )

        self.graph.add_node(new_action)

        self.graph.add_dependency(
            new_belief_id,
            new_action_id,
            DependencyType.REQUIRES
        )

        return new_action