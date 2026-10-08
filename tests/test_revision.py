from app.graph import BeliefGraph
from app.models import (
    BeliefNode,
    ConflictSeverity,
    Evidence,
    NodeType,
    NodeStatus,
    DependencyType
)


def test_belief_revision():

    graph = BeliefGraph()

    old_belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        value="v1",
        source="documentation-v1"
    )

    conclusion = BeliefNode(
        id="C1",
        node_type=NodeType.CONCLUSION,
        content="v1 endpoint can be used"
    )

    plan = BeliefNode(
        id="P1",
        node_type=NodeType.PLAN,
        content="Fetch customer data using v1"
    )

    action = BeliefNode(
        id="A1",
        node_type=NodeType.ACTION,
        content="Call customer API"
    )

    graph.add_node(old_belief)
    graph.add_node(conclusion)
    graph.add_node(plan)
    graph.add_node(action)

    graph.add_dependency(
        "B1",
        "C1",
        DependencyType.SUPPORTS
    )

    graph.add_dependency(
        "C1",
        "P1",
        DependencyType.REQUIRES
    )

    graph.add_dependency(
        "P1",
        "A1",
        DependencyType.REQUIRES
    )

    new_belief = BeliefNode(
        id="B2",
        node_type=NodeType.BELIEF,
        content="API version is v2",
        value="v2",
        source="documentation-v2"
    )

    impact = graph.revise_belief(
        "B1",
        new_belief
    )

    assert (
        graph.get_node("B1").status
        == NodeStatus.INVALID
    )

    assert (
        graph.get_node("B1").superseded_by
        == "B2"
    )

    assert (
        graph.get_node("B2").status
        == NodeStatus.ACTIVE
    )

    assert (
        graph.get_node("B2").version
        == 2
    )

    assert (
        impact["C1"]["impact"]
        == NodeStatus.REQUIRES_REEVALUATION
    )

    assert (
        impact["C1"]["dependency_type"]
        == DependencyType.SUPPORTS
    )


def test_dependency_type():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    plan = BeliefNode(
        id="P1",
        node_type=NodeType.PLAN,
        content="Use API v1"
    )

    graph.add_node(belief)
    graph.add_node(plan)

    graph.add_dependency(
        "B1",
        "P1",
        DependencyType.REQUIRES
    )

    assert (
        graph.get_dependency_type(
            "B1",
            "P1"
        )
        == DependencyType.REQUIRES
    )


def test_dependency_aware_impact_analysis():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    conclusion = BeliefNode(
        id="C1",
        node_type=NodeType.CONCLUSION,
        content="v1 endpoint is usable"
    )

    plan = BeliefNode(
        id="P1",
        node_type=NodeType.PLAN,
        content="Use v1 API"
    )

    context = BeliefNode(
        id="CTX1",
        node_type=NodeType.CONCLUSION,
        content="Customer API is external"
    )

    graph.add_node(belief)
    graph.add_node(conclusion)
    graph.add_node(plan)
    graph.add_node(context)

    graph.add_dependency(
        "B1",
        "C1",
        DependencyType.SUPPORTS
    )

    graph.add_dependency(
        "B1",
        "P1",
        DependencyType.REQUIRES
    )

    graph.add_dependency(
        "B1",
        "CTX1",
        DependencyType.CONTEXT
    )

    impact = graph.analyze_impact(
        "B1"
    )

    assert (
        impact["C1"]["impact"]
        == NodeStatus.REQUIRES_REEVALUATION
    )

    assert (
        impact["P1"]["impact"]
        == NodeStatus.INVALID
    )

    assert (
        impact["CTX1"]["impact"]
        == NodeStatus.UNCERTAIN
    )


def test_impact_analysis_does_not_mutate_nodes():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    conclusion = BeliefNode(
        id="C1",
        node_type=NodeType.CONCLUSION,
        content="v1 endpoint is usable"
    )

    graph.add_node(belief)
    graph.add_node(conclusion)

    graph.add_dependency(
        "B1",
        "C1",
        DependencyType.SUPPORTS
    )

    graph.analyze_impact("B1")

    assert (
        graph.get_node("B1").status
        == NodeStatus.ACTIVE
    )

    assert (
        graph.get_node("C1").status
        == NodeStatus.ACTIVE
    )


def test_impact_propagation():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    conclusion = BeliefNode(
        id="C1",
        node_type=NodeType.CONCLUSION,
        content="v1 endpoint is usable"
    )

    plan = BeliefNode(
        id="P1",
        node_type=NodeType.PLAN,
        content="Use v1 API"
    )

    action = BeliefNode(
        id="A1",
        node_type=NodeType.ACTION,
        content="Call v1 API"
    )

    graph.add_node(belief)
    graph.add_node(conclusion)
    graph.add_node(plan)
    graph.add_node(action)

    graph.add_dependency(
        "B1",
        "C1",
        DependencyType.SUPPORTS
    )

    graph.add_dependency(
        "C1",
        "P1",
        DependencyType.REQUIRES
    )

    graph.add_dependency(
        "P1",
        "A1",
        DependencyType.REQUIRES
    )

    impact = graph.propagate_impact(
        "B1"
    )

    assert (
        impact["C1"]["impact"]
        == NodeStatus.REQUIRES_REEVALUATION
    )

    assert (
        impact["P1"]["impact"]
        == NodeStatus.INVALID
    )

    assert (
        impact["A1"]["impact"]
        == NodeStatus.INVALID
    )

    assert impact["C1"]["depth"] == 1
    assert impact["P1"]["depth"] == 2
    assert impact["A1"]["depth"] == 3


def test_propagation_depth_limit():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    conclusion = BeliefNode(
        id="C1",
        node_type=NodeType.CONCLUSION,
        content="v1 endpoint works"
    )

    plan = BeliefNode(
        id="P1",
        node_type=NodeType.PLAN,
        content="Use v1 API"
    )

    graph.add_node(belief)
    graph.add_node(conclusion)
    graph.add_node(plan)

    graph.add_dependency(
        "B1",
        "C1",
        DependencyType.SUPPORTS
    )

    graph.add_dependency(
        "C1",
        "P1",
        DependencyType.REQUIRES
    )

    impact = graph.propagate_impact(
        "B1",
        max_depth=1
    )

    assert "C1" in impact
    assert "P1" not in impact


def test_add_evidence():

    graph = BeliefGraph()

    evidence = Evidence(
        id="E1",
        content="Official documentation says API version is v2",
        source="official-api-docs",
        confidence=0.98
    )

    graph.add_evidence(
        evidence
    )

    stored = graph.get_evidence(
        "E1"
    )

    assert stored.id == "E1"

    assert stored.content == (
        "Official documentation says API version is v2"
    )

    assert stored.source == (
        "official-api-docs"
    )

    assert stored.confidence == 0.98


def test_link_evidence_to_belief():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    evidence = Evidence(
        id="E1",
        content="Documentation states API version is v1",
        source="official-api-docs",
        confidence=0.95
    )

    graph.add_node(
        belief
    )

    graph.add_evidence(
        evidence
    )

    graph.link_evidence(
        "E1",
        "B1",
        DependencyType.SUPPORTS
    )

    assert (
        graph.get_dependency_type(
            "E1",
            "B1"
        )
        == DependencyType.SUPPORTS
    )


def test_evidence_contradicts_belief():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    evidence = Evidence(
        id="E2",
        content="Official documentation now says API version is v2",
        source="official-api-docs-v2",
        confidence=0.99
    )

    graph.add_node(
        belief
    )

    graph.add_evidence(
        evidence
    )

    graph.link_evidence(
        "E2",
        "B1",
        DependencyType.CONTRADICTS
    )

    impact = graph.analyze_impact(
        "E2"
    )

    assert (
        impact["B1"]["impact"]
        == NodeStatus.REQUIRES_REEVALUATION
    )

    assert (
        impact["B1"]["dependency_type"]
        == DependencyType.CONTRADICTS
    )


def test_detect_conflict():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    evidence = Evidence(
        id="E2",
        content="Official documentation says API version is v2",
        source="official-api-docs-v2",
        confidence=0.99
    )

    graph.add_node(
        belief
    )

    graph.add_evidence(
        evidence
    )

    conflict = graph.detect_conflict(
        "E2",
        "B1"
    )

    assert conflict.id == (
        "CONFLICT-E2-B1"
    )

    assert conflict.evidence_id == "E2"

    assert conflict.belief_id == "B1"

    assert conflict.resolved is False

    assert conflict.severity == (
        ConflictSeverity.HIGH
    )


def test_duplicate_conflict_is_not_created():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1"
    )

    evidence = Evidence(
        id="E2",
        content="API version is v2",
        source="official-docs",
        confidence=0.95
    )

    graph.add_node(
        belief
    )

    graph.add_evidence(
        evidence
    )

    conflict_1 = graph.detect_conflict(
        "E2",
        "B1"
    )

    conflict_2 = graph.detect_conflict(
        "E2",
        "B1"
    )

    assert conflict_1.id == conflict_2.id

    assert len(
        graph.conflicts
    ) == 1

def test_resolve_conflict_with_stronger_evidence():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        confidence=0.70
    )

    evidence = Evidence(
        id="E2",
        content="Official documentation says API version is v2",
        source="official-api-docs",
        confidence=0.99
    )

    graph.add_node(belief)
    graph.add_evidence(evidence)

    conflict = graph.detect_conflict(
        "E2",
        "B1"
    )

    new_belief = BeliefNode(
        id="B2",
        node_type=NodeType.BELIEF,
        content="API version is v2",
        confidence=0.99
    )

    result = graph.resolve_conflict(
        conflict.id,
        new_belief
    )

    assert result["status"] == "revised"

    assert result["old_belief"] == "B1"

    assert result["new_belief"] == "B2"

    assert (
        graph.get_node("B1").status
        == NodeStatus.INVALID
    )

    assert (
        graph.get_node("B1").superseded_by
        == "B2"
    )

    assert (
        graph.get_node("B2").status
        == NodeStatus.ACTIVE
    )

    assert (
        graph.get_node("B2").version
        == 2
    )

    assert (
        graph.get_conflict(
            conflict.id
        ).resolved
        is True
    )


def test_reject_weaker_evidence():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        confidence=0.95
    )

    evidence = Evidence(
        id="E2",
        content="Someone claims API version is v2",
        source="unverified-source",
        confidence=0.40
    )

    graph.add_node(belief)
    graph.add_evidence(evidence)

    conflict = graph.detect_conflict(
        "E2",
        "B1"
    )

    new_belief = BeliefNode(
        id="B2",
        node_type=NodeType.BELIEF,
        content="API version is v2",
        confidence=0.40
    )

    result = graph.resolve_conflict(
        conflict.id,
        new_belief
    )

    assert result["status"] == "rejected"

    assert (
        graph.get_node("B1").status
        == NodeStatus.ACTIVE
    )

    assert (
        "B2" not in graph.graph.nodes
    )

    assert (
        graph.get_conflict(
            conflict.id
        ).resolved
        is False
    )


def test_equal_confidence_creates_uncertainty():

    graph = BeliefGraph()

    belief = BeliefNode(
        id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        confidence=0.80
    )

    evidence = Evidence(
        id="E2",
        content="Another source says API version is v2",
        source="second-source",
        confidence=0.80
    )

    graph.add_node(belief)
    graph.add_evidence(evidence)

    conflict = graph.detect_conflict(
        "E2",
        "B1"
    )

    new_belief = BeliefNode(
        id="B2",
        node_type=NodeType.BELIEF,
        content="API version is v2",
        confidence=0.80
    )

    result = graph.resolve_conflict(
        conflict.id,
        new_belief
    )

    assert result["status"] == "uncertain"

    assert (
        graph.get_node("B1").status
        == NodeStatus.UNCERTAIN
    )

    assert (
        "B2" not in graph.graph.nodes
    )