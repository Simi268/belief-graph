from app.agent import AgentRuntime

from app.models import (
    BeliefNode,
    NodeStatus,
    NodeType
)


def test_agent_creates_belief():

    agent = AgentRuntime()

    belief = agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.80,
        source="initial-knowledge"
    )

    assert belief.id == "B1"

    assert belief.content == (
        "API version is v1"
    )

    assert belief.value == "v1"

    assert belief.confidence == 0.80

    assert (
        agent.get_belief_status("B1")
        == NodeStatus.ACTIVE
    )


def test_agent_observes_evidence():

    agent = AgentRuntime()

    evidence = agent.observe(
        evidence_id="E1",
        content="API documentation says v1",
        source="official-docs",
        confidence=0.95
    )

    assert evidence.id == "E1"

    assert evidence.content == (
        "API documentation says v1"
    )

    assert evidence.source == (
        "official-docs"
    )

    assert evidence.confidence == 0.95


def test_agent_supports_belief():

    agent = AgentRuntime()

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        confidence=0.80
    )

    agent.observe(
        evidence_id="E1",
        content="Documentation says v1",
        source="official-docs",
        confidence=0.95
    )

    agent.support_belief(
        "E1",
        "B1"
    )

    dependency = (
        agent.graph.get_dependency_type(
            "E1",
            "B1"
        )
    )

    from app.models import DependencyType

    assert dependency == (
        DependencyType.SUPPORTS
    )


def test_agent_detects_contradiction():

    agent = AgentRuntime()

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        confidence=0.70
    )

    agent.observe(
        evidence_id="E2",
        content="Documentation says v2",
        source="official-docs",
        confidence=0.99
    )

    conflict = (
        agent.detect_contradiction(
            "E2",
            "B1"
        )
    )

    assert conflict.evidence_id == "E2"

    assert conflict.belief_id == "B1"

    assert conflict.resolved is False


def test_agent_revises_belief():

    agent = AgentRuntime()

    agent.create_belief(
        belief_id="B1",
        content="API version is v1",
        confidence=0.70
    )

    agent.observe(
        evidence_id="E2",
        content="Documentation says v2",
        source="official-docs",
        confidence=0.99
    )

    conflict = (
        agent.detect_contradiction(
            "E2",
            "B1"
        )
    )

    new_belief = BeliefNode(
        id="B2",
        node_type=NodeType.BELIEF,
        content="API version is v2",
        value="v2",
        confidence=0.99,
        source="official-docs"
    )

    result = agent.revise(
        conflict.id,
        new_belief
    )

    assert result["status"] == "revised"

    assert (
        agent.get_belief_status("B1")
        == NodeStatus.INVALID
    )

    assert (
        agent.get_belief_status("B2")
        == NodeStatus.ACTIVE
    )