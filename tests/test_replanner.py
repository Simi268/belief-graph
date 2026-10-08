from app.agent import AgentRuntime
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)
from app.replanner import Replanner


def test_replanner_creates_action_from_new_belief():

    agent = AgentRuntime()

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.90
    )

    agent.create_belief(
        belief_id="B2",
        content="API version is v2",
        value="v2",
        confidence=1.0
    )

    agent.create_node(
        node_id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API using v1"
    )

    agent.graph.get_node("B1").status = (
        NodeStatus.INVALID
    )

    agent.graph.get_node("A1").status = (
        NodeStatus.INVALID
    )

    replanner = Replanner(agent.graph)

    new_action = replanner.replan_api_action(
        old_belief_id="B1",
        new_belief_id="B2",
        old_action_id="A1",
        new_action_id="A2"
    )

    assert new_action.id == "A2"

    assert new_action.node_type == (
        NodeType.ACTION
    )

    assert new_action.value == "v2"

    assert new_action.status == (
        NodeStatus.ACTIVE
    )

    assert (
        agent.graph.get_dependency_type(
            "B2",
            "A2"
        )
        == DependencyType.REQUIRES
    )