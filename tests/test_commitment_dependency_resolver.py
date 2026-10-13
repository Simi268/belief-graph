import pytest

from app.agent import AgentRuntime
from app.commitments import CommitmentRegistry, Reversibility
from app.commitment_dependency_resolver import CommitmentDependencyResolver
from app.models import DependencyType, NodeType


@pytest.fixture
def setup_resolver():
    agent = AgentRuntime()

    agent.create_belief("belief-stock", "Stock is available", value=True)

    agent.create_node(
        "plan-shipping",
        NodeType.PLAN,
        "Prepare shipment",
    )
    agent.create_node(
        "action-shipping",
        NodeType.ACTION,
        "Reserve shipment",
    )
    agent.create_node(
        "unrelated-action",
        NodeType.ACTION,
        "Send unrelated report",
    )

    agent.add_dependency(
        "belief-stock",
        "plan-shipping",
        DependencyType.REQUIRES,
    )
    agent.add_dependency(
        "plan-shipping",
        "action-shipping",
        DependencyType.REQUIRES,
    )

    registry = CommitmentRegistry()

    registry.register(
        "shipment-001",
        "action-shipping",
        {"action-shipping"},
        "Shipment reservation",
        Reversibility.COMPENSABLE,
    )

    registry.register(
        "report-001",
        "unrelated-action",
        {"unrelated-action"},
        "Unrelated report",
        Reversibility.REVERSIBLE,
    )

    resolver = CommitmentDependencyResolver(agent.graph, registry)

    return agent, registry, resolver


def test_resolves_commitment_through_dependency_chain(setup_resolver):
    _, _, resolver = setup_resolver

    report = resolver.resolve({"belief-stock"})

    assert "plan-shipping" in report.affected_node_ids
    assert "action-shipping" in report.affected_node_ids
    assert report.affected_commitment_ids == ["shipment-001"]


def test_unrelated_commitment_is_not_affected(setup_resolver):
    _, _, resolver = setup_resolver

    report = resolver.resolve({"belief-stock"})

    assert report.unaffected_commitment_ids == ["report-001"]


def test_changed_node_can_be_excluded(setup_resolver):
    _, _, resolver = setup_resolver

    report = resolver.resolve(
        {"belief-stock"},
        include_changed_nodes=False,
    )

    assert "belief-stock" not in report.affected_node_ids
    assert "action-shipping" in report.affected_node_ids


def test_unknown_node_is_rejected(setup_resolver):
    _, _, resolver = setup_resolver

    with pytest.raises(ValueError, match="Unknown graph node"):
        resolver.resolve({"missing-belief"})


def test_empty_changed_nodes_are_rejected(setup_resolver):
    _, _, resolver = setup_resolver

    with pytest.raises(ValueError, match="At least one changed node"):
        resolver.resolve(set())