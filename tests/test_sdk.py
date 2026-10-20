import pytest

from app.environment import DynamicAPIEnvironment
from app.models import DependencyType, NodeStatus, NodeType
from app.sdk import BeliefGraphSDK


def test_sdk_builds_reasoning_chain():
    bg = BeliefGraphSDK()

    bg.belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
        confidence=0.9,
    )

    bg.conclusion(
        node_id="C1",
        content="The v1 endpoint can be used",
    )

    bg.plan(
        node_id="P1",
        content="Fetch customer data",
    )

    bg.action(
        node_id="A1",
        content="Call customer API",
    )

    bg.depends_on("B1", "C1", DependencyType.REQUIRES)
    bg.depends_on("C1", "P1", DependencyType.REQUIRES)
    bg.depends_on("P1", "A1", DependencyType.REQUIRES)

    assert bg.status("B1") == NodeStatus.ACTIVE
    assert bg.status("C1") == NodeStatus.ACTIVE
    assert bg.status("P1") == NodeStatus.ACTIVE
    assert bg.status("A1") == NodeStatus.ACTIVE


def test_sdk_registers_evaluators_directly_and_as_decorators():
    bg = BeliefGraphSDK()
    bg.belief("B1", "API version", value="v1")
    bg.conclusion("C1", "API version can be used")
    bg.plan("P1", "Fetch data")

    direct = lambda node, parents: parents["B1"] == "v2"
    assert bg.register_evaluator("C1", direct) is direct

    @bg.register_evaluator("P1")
    def evaluate_plan(node, parents):
        return {"enabled": parents["C1"]}

    assert bg._evaluators["C1"] is direct
    assert bg._evaluators["P1"] is evaluate_plan


def test_sdk_refuses_semantic_evaluators_for_source_beliefs():
    bg = BeliefGraphSDK()
    bg.belief("B1", "API version", value="v1")

    with pytest.raises(ValueError, match="source belief"):
        bg.register_evaluator("B1", lambda node, parents: "v2")

    with pytest.raises(TypeError, match="callable"):
        bg.register_evaluator("B1", 42)


def test_sdk_executes_action_and_recovers_using_registered_evaluators():
    bg = BeliefGraphSDK()
    environment = DynamicAPIEnvironment()

    bg.belief("B1", "Customer API version", value="v1")
    bg.conclusion("C1", "Customer endpoint is usable", value=None)
    bg.plan("P1", "Retrieve customer data", value=None)
    bg.action("A1", "Call customer API using current version")
    bg.depends_on("B1", "C1")
    bg.depends_on("C1", "P1")
    bg.depends_on("P1", "A1")

    # An independent branch is kept as a control for selective recovery.
    bg.belief("B3", "Reporting database is available", value=True)
    bg.conclusion("C3", "Reporting data can be generated", value="ready")
    bg.plan("P3", "Generate a report", value={"enabled": True})
    bg.depends_on("B3", "C3")
    bg.depends_on("C3", "P3")

    @bg.register_evaluator("C1")
    def evaluate_endpoint(node, predecessors):
        current_version = predecessors["B2"]
        return {
            "available": current_version == "v2",
            "api_version": current_version,
        }

    @bg.register_evaluator("P1")
    def evaluate_plan(node, predecessors):
        conclusion = predecessors["C1"]
        return {
            "operation": "retrieve_customer_data",
            "api_version": conclusion["api_version"],
            "enabled": conclusion["available"],
        }

    environment.set_api_version("v2")
    failed_action_result = bg.execute_action(
        action_id="A1",
        belief_id="B1",
        environment=environment,
    )
    assert failed_action_result["environment_result"]["success"] is False
    assert bg.get("A1").execution_status.value == "failed"

    result = bg.recover_from_action_failure(
        action_result=failed_action_result,
        evidence_id="E1",
        new_belief_id="B2",
        new_action_id="A2",
        environment=environment,
    )

    assert result["selective_recovery"] is not None
    assert result["selective_recovery"]["status"] == "completed"
    assert bg.get("C1").value == {
        "available": True,
        "api_version": "v2",
    }
    assert bg.get("P1").value == {
        "operation": "retrieve_customer_data",
        "api_version": "v2",
        "enabled": True,
    }
    assert result["execution"]["success"] is True
    assert bg.get("A2").execution_result["success"] is True

    assert bg.get("B3").status == NodeStatus.ACTIVE
    assert bg.get("C3").value == "ready"
    assert bg.get("P3").value == {"enabled": True}


def test_sdk_does_not_execute_action_with_unrelated_belief():
    bg = BeliefGraphSDK()
    environment = DynamicAPIEnvironment()
    bg.belief("B1", "API version", value="v1")
    bg.action("A1", "Call customer API")
    bg.belief("B2", "Unrelated version", value="v2")

    with pytest.raises(ValueError, match="does not depend on belief"):
        bg.execute_action(
            action_id="A1",
            belief_id="B1",
            environment=environment,
        )


def test_sdk_registers_multiple_dependencies():
    bg = BeliefGraphSDK()

    bg.belief("B1", "First source")
    bg.belief("B2", "Second source")
    bg.conclusion("C1", "Combined conclusion")
    bg.plan("P1", "Next step")

    created = bg.depends_on_many({
        "C1": ["B1", "B2"],
        "P1": ["C1"],
    })

    assert len(created) == 3
    graph = bg.graph.graph

    assert graph.has_edge("B1", "C1")
    assert graph.has_edge("B2", "C1")
    assert graph.has_edge("C1", "P1")


def test_sdk_rejects_invalid_dependency_mapping():
    bg = BeliefGraphSDK()

    with pytest.raises(TypeError, match="dictionary"):
        bg.depends_on_many([])


def test_sdk_rejects_non_list_prerequisites():
    bg = BeliefGraphSDK()
    bg.belief("B1", "Source")
    bg.conclusion("C1", "Conclusion")

    with pytest.raises(TypeError, match="must be a list"):
        bg.depends_on_many({"C1": "B1"})
