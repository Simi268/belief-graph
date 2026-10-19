import pytest

from app.agent import AgentRuntime
from app.models import DependencyType, NodeType


def _runtime_with_nodes(*node_ids: str) -> AgentRuntime:
    agent = AgentRuntime()
    for node_id in node_ids:
        agent.create_node(
            node_id=node_id,
            node_type=NodeType.ACTION,
            content=f"Test action {node_id}",
        )
    return agent


def test_selective_recovery_recomputes_in_dependency_order():
    agent = _runtime_with_nodes("A", "B", "C")
    agent.add_dependency("A", "B", DependencyType.REQUIRES)

    calls = []
    result = agent.execute_selective_recovery(
        recovery_plan={
            "replan_nodes": ["B", "A"],
            "preserved_nodes": ["C"],
        },
        recompute_node=lambda node: calls.append(node.id) or {"node": node.id},
    )

    assert calls == ["A", "B"]
    assert result["execution_order"] == ["A", "B"]
    assert result["recomputed_node_ids"] == ["A", "B"]
    assert result["preserved_node_ids"] == ["C"]
    assert result["metrics"]["recomputed_node_count"] == 2
    assert result["metrics"]["successful_recomputations"] == 2
    assert result["metrics"]["failed_recomputations"] == 0
    assert result["metrics"]["skipped_recomputations"] == 0
    assert result["status"] == "completed"


def test_selective_recovery_records_partial_failure_and_continues():
    # A and B are independent, so failure of A must not block B.
    agent = _runtime_with_nodes("A", "B")

    def recompute(node):
        if node.id == "A":
            raise RuntimeError("simulated recomputation failure")
        return "ok"

    result = agent.execute_selective_recovery(
        recovery_plan={"replan_nodes": ["A", "B"], "preserved_nodes": []},
        recompute_node=recompute,
    )

    assert result["status"] == "partial_failure"
    assert result["metrics"]["recomputed_node_count"] == 2
    assert result["metrics"]["successful_recomputations"] == 1
    assert result["metrics"]["failed_recomputations"] == 1
    assert result["metrics"]["skipped_recomputations"] == 0
    assert result["outcomes"][0]["error"] == "simulated recomputation failure"
    assert result["outcomes"][1]["success"] is True
    assert result["failed_node_ids"] == ["A"]
    assert result["skipped_node_ids"] == []


def test_selective_recovery_skips_dependents_of_failed_prerequisites():
    agent = _runtime_with_nodes("A", "B", "C", "D")
    agent.add_dependency("A", "B", DependencyType.REQUIRES)
    agent.add_dependency("B", "C", DependencyType.DERIVED_FROM)

    calls = []

    def recompute(node):
        calls.append(node.id)
        if node.id == "A":
            raise RuntimeError("A failed")
        return {"node": node.id}

    result = agent.execute_selective_recovery(
        recovery_plan={
            "replan_nodes": ["C", "B", "D", "A"],
            "preserved_nodes": [],
        },
        recompute_node=recompute,
    )

    # A fails, B and C are skipped, and independent D still executes.
    assert calls == ["A", "D"]
    assert result["failed_node_ids"] == ["A"]
    assert result["skipped_node_ids"] == ["B", "C"]
    assert result["recomputed_node_ids"] == ["A", "D"]
    assert result["metrics"]["recomputed_node_count"] == 2
    assert result["metrics"]["successful_recomputations"] == 1
    assert result["metrics"]["failed_recomputations"] == 1
    assert result["metrics"]["skipped_recomputations"] == 2
    assert result["status"] == "partial_failure"

    outcomes = {item["node_id"]: item for item in result["outcomes"]}
    assert outcomes["B"]["skipped"] is True
    assert outcomes["B"]["blocked_by"] == ["A"]
    assert outcomes["C"]["skipped"] is True
    assert outcomes["C"]["blocked_by"] == ["B"]
    assert outcomes["D"]["success"] is True


def test_selective_recovery_rejects_missing_nodes_before_callback():
    agent = _runtime_with_nodes("A")
    calls = []

    with pytest.raises(ValueError, match="missing nodes"):
        agent.execute_selective_recovery(
            recovery_plan={"replan_nodes": ["DOES_NOT_EXIST"]},
            recompute_node=lambda node: calls.append(node.id),
        )

    assert calls == []


def test_selective_recovery_rejects_overlap_between_recovery_and_preserved():
    agent = _runtime_with_nodes("A")

    with pytest.raises(ValueError, match="both recovery candidates and preserved"):
        agent.execute_selective_recovery(
            recovery_plan={
                "replan_nodes": ["A"],
                "preserved_nodes": ["A"],
            },
            recompute_node=lambda node: None,
        )


def test_selective_recovery_rejects_dependency_cycles():
    agent = _runtime_with_nodes("A", "B")
    agent.add_dependency("A", "B", DependencyType.REQUIRES)
    agent.add_dependency("B", "A", DependencyType.REQUIRES)

    with pytest.raises(ValueError, match="dependency cycle"):
        agent.execute_selective_recovery(
            recovery_plan={"replan_nodes": ["A", "B"]},
            recompute_node=lambda node: None,
        )


def test_selective_recovery_does_not_call_callback_for_preserved_nodes():
    agent = _runtime_with_nodes("A", "B")
    calls = []

    result = agent.execute_selective_recovery(
        recovery_plan={
            "replan_nodes": ["A"],
            "preserved_nodes": ["B"],
        },
        recompute_node=lambda node: calls.append(node.id),
    )

    assert calls == ["A"]
    assert result["recomputed_node_ids"] == ["A"]
    assert result["preserved_node_ids"] == ["B"]
    assert result["metrics"]["unnecessary_recomputations"] == 0
