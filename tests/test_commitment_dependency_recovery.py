import pytest

from app.agent import AgentRuntime
from app.commitments import CommitmentRegistry, Reversibility
from app.commitment_dependency_resolver import CommitmentDependencyResolver
from app.models import DependencyType, NodeType


@pytest.fixture
def dependency_setup():
    agent = AgentRuntime()

    agent.create_belief(
        "inventory-belief",
        "Inventory is available",
        value=True,
    )

    agent.create_node(
        "shipping-plan",
        NodeType.PLAN,
        "Prepare shipment",
    )

    agent.create_node(
        "reserve-action",
        NodeType.ACTION,
        "Reserve inventory for shipment",
    )

    agent.create_node(
        "unrelated-action",
        NodeType.ACTION,
        "Generate an unrelated report",
    )

    agent.add_dependency(
        "inventory-belief",
        "shipping-plan",
        DependencyType.REQUIRES,
    )

    agent.add_dependency(
        "shipping-plan",
        "reserve-action",
        DependencyType.REQUIRES,
    )

    registry = CommitmentRegistry()

    registry.register(
        "shipment-commitment",
        "reserve-action",
        {"reserve-action"},
        "Shipment reservation",
        Reversibility.COMPENSABLE,
    )

    registry.register(
        "report-commitment",
        "unrelated-action",
        {"unrelated-action"},
        "Unrelated reporting task",
        Reversibility.REVERSIBLE,
    )

    resolver = CommitmentDependencyResolver(
        agent.graph,
        registry,
    )

    return agent, registry, resolver


def test_downstream_commitment_is_detected(dependency_setup):
    _, _, resolver = dependency_setup

    report = resolver.resolve({"inventory-belief"})

    assert "shipping-plan" in report.affected_node_ids
    assert "reserve-action" in report.affected_node_ids

    assert (
        "shipment-commitment"
        in report.affected_commitment_ids
    )


def test_unrelated_commitment_remains_unaffected(dependency_setup):
    _, _, resolver = dependency_setup

    report = resolver.resolve({"inventory-belief"})

    assert (
        "report-commitment"
        in report.unaffected_commitment_ids
    )


def test_resolver_does_not_mutate_graph_statuses(dependency_setup):
    agent, _, resolver = dependency_setup

    original_status = (
        agent.graph.graph.nodes["reserve-action"]["data"].status
    )

    resolver.resolve({"inventory-belief"})

    current_status = (
        agent.graph.graph.nodes["reserve-action"]["data"].status
    )

    assert current_status == original_status