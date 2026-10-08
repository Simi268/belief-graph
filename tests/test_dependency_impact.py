from app.agent import AgentRuntime
from app.models import (
    NodeType,
    DependencyType,
    NodeStatus
)


def test_requires_dependency_becomes_invalid():

    agent = AgentRuntime()

    agent.create_belief(
        "B1",
        "API version is v1"
    )

    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "v1 endpoint can be used"
    )

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.REQUIRES
    )

    impact = agent.graph.propagate_impact("B1")

    assert impact["C1"]["impact"] == (
        NodeStatus.INVALID
    )


def test_supports_dependency_requires_reevaluation():

    agent = AgentRuntime()

    agent.create_belief(
        "B1",
        "API version is v1"
    )

    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "v1 is preferred"
    )

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.SUPPORTS
    )

    impact = agent.graph.propagate_impact("B1")

    assert impact["C1"]["impact"] == (
        NodeStatus.REQUIRES_REEVALUATION
    )


def test_context_dependency_becomes_uncertain():

    agent = AgentRuntime()

    agent.create_belief(
        "B1",
        "User is in India"
    )

    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "Use local formatting"
    )

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.CONTEXT
    )

    impact = agent.graph.propagate_impact("B1")

    assert impact["C1"]["impact"] == (
        NodeStatus.UNCERTAIN
    )


def test_derived_dependency_becomes_invalid():

    agent = AgentRuntime()

    agent.create_belief(
        "B1",
        "API version is v1"
    )

    agent.create_node(
        "C1",
        NodeType.CONCLUSION,
        "v1 endpoint is available"
    )

    agent.add_dependency(
        "B1",
        "C1",
        DependencyType.DERIVED_FROM
    )

    impact = agent.graph.propagate_impact("B1")

    assert impact["C1"]["impact"] == (
        NodeStatus.INVALID
    )