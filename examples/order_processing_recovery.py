"""Runnable order-processing recovery example with a full-restart baseline.

Run from the repository root::

    python -m examples.order_processing_recovery

Both strategies start from fresh, equivalent agent instances and encounter the
same API v1/v2 mismatch. Selective recovery recomputes only affected semantic
nodes; the full-restart baseline recomputes every registered semantic
CONCLUSION/PLAN node. Replacement actions are executed by the existing recovery
path in both runs and are not counted as semantic value recomputations.
"""
from __future__ import annotations

from typing import Any, Callable

import networkx as nx

from app.environment import DynamicAPIEnvironment
from app.models import DependencyType, NodeStatus
from app.recovery import RecoveryEngine
from app.recovery_verifier import verify_recovery_run
from app.sdk import BeliefGraphSDK
from app.semantic_recomputation import SemanticRecomputer


SEMANTIC_NODE_IDS = (
    "C_ORDER_ELIGIBLE",
    "P_CREATE_ORDER",
    "C_SHIPPING_READY",
    "P_CREATE_SHIPMENT",
)

EXPECTED_CONCLUSION = {
    "eligible": True,
    "api_version": "v2",
    "sku": "SKU-104",
    "requested_quantity": 2,
    "available_quantity": 8,
    "unit_price": 24.50,
    "price_approved": True,
    "within_stock": True,
}
EXPECTED_ORDER_PLAN = {
    "operation": "create_order",
    "sku": "SKU-104",
    "quantity": 2,
    "api_version": "v2",
    "enabled": True,
}
EXPECTED_SHIPPING_READY = {"ready": True}
EXPECTED_SHIPMENT_PLAN = {"enabled": True}

Evaluator = Callable[[Any, dict[str, Any]], Any]


def _register_evaluators(sdk: BeliefGraphSDK) -> dict[str, Evaluator]:
    """Register explicit semantic rules and return them for baseline reuse."""

    def evaluate_order_eligibility(node, predecessors):
        api_version = predecessors["B_API_VERSION_V2"]
        inventory = predecessors["B_INVENTORY"]
        pricing = predecessors["B_PRICING"]
        requested_quantity = 2
        within_stock = inventory["available_quantity"] >= requested_quantity
        price_approved = (
            pricing["unit_price"] <= pricing["maximum_approved_price"]
        )
        return {
            "eligible": (
                api_version == "v2" and within_stock and price_approved
            ),
            "api_version": api_version,
            "sku": inventory["sku"],
            "requested_quantity": requested_quantity,
            "available_quantity": inventory["available_quantity"],
            "unit_price": pricing["unit_price"],
            "price_approved": price_approved,
            "within_stock": within_stock,
        }

    def evaluate_order_plan(node, predecessors):
        eligibility = predecessors["C_ORDER_ELIGIBLE"]
        return {
            "operation": "create_order",
            "sku": eligibility["sku"],
            "quantity": eligibility["requested_quantity"],
            "api_version": eligibility["api_version"],
            "enabled": eligibility["eligible"],
        }

    def evaluate_shipping_ready(node, predecessors):
        return {"ready": bool(predecessors["B_SHIPPING_AUTH"])}

    def evaluate_shipment_plan(node, predecessors):
        return {"enabled": bool(predecessors["C_SHIPPING_READY"]["ready"])}

    evaluators: dict[str, Evaluator] = {
        "C_ORDER_ELIGIBLE": evaluate_order_eligibility,
        "P_CREATE_ORDER": evaluate_order_plan,
        "C_SHIPPING_READY": evaluate_shipping_ready,
        "P_CREATE_SHIPMENT": evaluate_shipment_plan,
    }
    for node_id, evaluator in evaluators.items():
        sdk.register_evaluator(node_id, evaluator)
    return evaluators


def _build_scenario() -> tuple[BeliefGraphSDK, DynamicAPIEnvironment, dict[str, Evaluator]]:
    """Build one isolated order agent with a separate shipping branch."""
    sdk = BeliefGraphSDK()
    environment = DynamicAPIEnvironment()

    # Source facts for placing a two-unit order.
    sdk.belief(
        "B_API_VERSION",
        "Order service API version",
        value="v1",
        source="service-discovery-cache",
    )
    sdk.belief(
        "B_INVENTORY",
        "Inventory for SKU-104",
        value={"sku": "SKU-104", "available_quantity": 8},
        source="inventory-service",
    )
    sdk.belief(
        "B_PRICING",
        "Approved price for SKU-104",
        value={"unit_price": 24.50, "maximum_approved_price": 30.00},
        source="pricing-service",
    )

    # Order reasoning path.
    sdk.conclusion(
        "C_ORDER_ELIGIBLE",
        "The order can be submitted with current service, stock, and price facts",
        value={"eligible": True, "api_version": "v1"},
    )
    sdk.plan(
        "P_CREATE_ORDER",
        "Create an order for two units of SKU-104",
        value={"enabled": True, "api_version": "v1"},
    )
    sdk.action(
        "A_SUBMIT_ORDER",
        "Submit the order to the order service",
        value="v1",
    )

    sdk.depends_on("B_API_VERSION", "C_ORDER_ELIGIBLE")
    sdk.depends_on("B_INVENTORY", "C_ORDER_ELIGIBLE")
    sdk.depends_on("B_PRICING", "C_ORDER_ELIGIBLE")
    sdk.depends_on("C_ORDER_ELIGIBLE", "P_CREATE_ORDER")
    sdk.depends_on("P_CREATE_ORDER", "A_SUBMIT_ORDER")

    # Independent shipping branch, which selective recovery should preserve.
    sdk.belief(
        "B_SHIPPING_AUTH",
        "Shipping carrier credentials are valid",
        value=True,
        source="shipping-configuration",
    )
    sdk.conclusion(
        "C_SHIPPING_READY",
        "The shipping integration is ready",
        value=EXPECTED_SHIPPING_READY.copy(),
    )
    sdk.plan(
        "P_CREATE_SHIPMENT",
        "Create a shipment after order acceptance",
        value=EXPECTED_SHIPMENT_PLAN.copy(),
    )
    sdk.depends_on("B_SHIPPING_AUTH", "C_SHIPPING_READY")
    sdk.depends_on("C_SHIPPING_READY", "P_CREATE_SHIPMENT")

    evaluators = _register_evaluators(sdk)
    return sdk, environment, evaluators


def _trigger_same_failure(
    sdk: BeliefGraphSDK,
    environment: DynamicAPIEnvironment,
) -> dict[str, Any]:
    """Cause the reproducible stale-v1 failure on a fresh scenario."""
    environment.set_api_version("v2")
    action_result = sdk.execute_action(
        action_id="A_SUBMIT_ORDER",
        belief_id="B_API_VERSION",
        environment=environment,
    )
    if action_result["environment_result"].get("error") != "API_VERSION_MISMATCH":
        raise AssertionError(
            "The example did not reproduce the intended API version failure."
        )
    return action_result


def _expected_statuses() -> dict[str, NodeStatus]:
    return {
        "B_API_VERSION": NodeStatus.INVALID,
        "B_API_VERSION_V2": NodeStatus.ACTIVE,
        "C_ORDER_ELIGIBLE": NodeStatus.INVALID,
        "P_CREATE_ORDER": NodeStatus.INVALID,
        "A_SUBMIT_ORDER": NodeStatus.INVALID,
        "A_SUBMIT_ORDER_V2": NodeStatus.ACTIVE,
        "B_INVENTORY": NodeStatus.ACTIVE,
        "B_PRICING": NodeStatus.ACTIVE,
        "B_SHIPPING_AUTH": NodeStatus.ACTIVE,
        "C_SHIPPING_READY": NodeStatus.ACTIVE,
        "P_CREATE_SHIPMENT": NodeStatus.ACTIVE,
    }


def _semantic_values_correct(sdk: BeliefGraphSDK) -> bool:
    return (
        sdk.get("C_ORDER_ELIGIBLE").value == EXPECTED_CONCLUSION
        and sdk.get("P_CREATE_ORDER").value == EXPECTED_ORDER_PLAN
        and sdk.get("C_SHIPPING_READY").value == EXPECTED_SHIPPING_READY
        and sdk.get("P_CREATE_SHIPMENT").value == EXPECTED_SHIPMENT_PLAN
    )


def _stale_semantic_node_ids(sdk: BeliefGraphSDK) -> list[str]:
    expected_values = {
        "C_ORDER_ELIGIBLE": EXPECTED_CONCLUSION,
        "P_CREATE_ORDER": EXPECTED_ORDER_PLAN,
        "C_SHIPPING_READY": EXPECTED_SHIPPING_READY,
        "P_CREATE_SHIPMENT": EXPECTED_SHIPMENT_PLAN,
    }
    return [
        node_id
        for node_id, expected in expected_values.items()
        if sdk.get(node_id).value != expected
    ]


def _run_selective_strategy() -> dict[str, Any]:
    sdk, environment, _evaluators = _build_scenario()
    failed_action_result = _trigger_same_failure(sdk, environment)

    recovery_result = sdk.recover_from_action_failure(
        action_result=failed_action_result,
        evidence_id="E_API_VERSION_MISMATCH",
        new_belief_id="B_API_VERSION_V2",
        new_action_id="A_SUBMIT_ORDER_V2",
        environment=environment,
    )

    verification = verify_recovery_run(
        agent=sdk.runtime,
        recovery_result=recovery_result,
        expected_statuses=_expected_statuses(),
    )
    semantic_correct = _semantic_values_correct(sdk)
    verification["semantic_values_correct"] = semantic_correct
    verification["stale_semantic_nodes"] = _stale_semantic_node_ids(sdk)
    verification["verified"] = bool(
        verification["verified"]
        and semantic_correct
        and not verification["stale_semantic_nodes"]
    )

    independent_branch_preserved = all(
        sdk.get(node_id).status == NodeStatus.ACTIVE
        for node_id in (
            "B_SHIPPING_AUTH",
            "C_SHIPPING_READY",
            "P_CREATE_SHIPMENT",
        )
    )
    recomputed = list(
        recovery_result.get("selective_recovery", {}).get(
            "recomputed_node_ids", []
        )
    )
    preserved_semantic = [
        node_id for node_id in SEMANTIC_NODE_IDS if node_id not in recomputed
    ]
    correct = bool(verification["verified"] and independent_branch_preserved)

    return {
        "failure": failed_action_result["environment_result"],
        "recovery": recovery_result,
        "verification": verification,
        "semantic_values_correct": semantic_correct,
        "independent_branch_preserved": independent_branch_preserved,
        "recomputed_node_ids": recomputed,
        "preserved_node_ids": list(
            recovery_result.get("selective_recovery", {}).get(
                "preserved_node_ids", []
            )
        ),
        "semantic_nodes_processed": recomputed,
        "semantic_nodes_preserved": preserved_semantic,
        "final_correct": correct,
    }


def _run_full_restart_baseline() -> dict[str, Any]:
    """Run the same failure, then recompute all registered semantic nodes."""
    sdk, environment, evaluators = _build_scenario()
    failed_action_result = _trigger_same_failure(sdk, environment)

    # Omit the callback here deliberately: this baseline first performs the
    # same revision/replacement-action path, then recomputes all semantic nodes.
    recovery_result = RecoveryEngine(sdk.runtime).recover_from_action_failure(
        action_result=failed_action_result,
        evidence_id="E_API_VERSION_MISMATCH",
        new_belief_id="B_API_VERSION_V2",
        new_action_id="A_SUBMIT_ORDER_V2",
        environment=environment,
    )

    graph = sdk.runtime.graph.graph
    semantic_subgraph = graph.subgraph(SEMANTIC_NODE_IDS)
    recomputation_order = list(nx.topological_sort(semantic_subgraph))
    recomputer = SemanticRecomputer(sdk.runtime, evaluators)
    recomputation_records = []
    for node_id in recomputation_order:
        recomputation_records.append(recomputer(sdk.runtime.graph.get_node(node_id)))

    verification = verify_recovery_run(
        agent=sdk.runtime,
        recovery_result=recovery_result,
        expected_statuses=_expected_statuses(),
    )
    semantic_correct = _semantic_values_correct(sdk)
    stale_semantic_nodes = _stale_semantic_node_ids(sdk)
    verification["semantic_values_correct"] = semantic_correct
    verification["stale_semantic_nodes"] = stale_semantic_nodes
    verification["verified"] = bool(
        verification["verified"] and semantic_correct and not stale_semantic_nodes
    )

    independent_branch_correct = all(
        sdk.get(node_id).status == NodeStatus.ACTIVE
        for node_id in (
            "B_SHIPPING_AUTH",
            "C_SHIPPING_READY",
            "P_CREATE_SHIPMENT",
        )
    )
    recomputed = [record["node_id"] for record in recomputation_records]
    preserved_semantic = [
        node_id for node_id in SEMANTIC_NODE_IDS if node_id not in recomputed
    ]
    correct = bool(verification["verified"] and independent_branch_correct)

    return {
        "failure": failed_action_result["environment_result"],
        "recovery": recovery_result,
        "verification": verification,
        "semantic_values_correct": semantic_correct,
        "independent_branch_preserved": independent_branch_correct,
        "recomputed_node_ids": recomputed,
        "preserved_node_ids": preserved_semantic,
        "semantic_nodes_processed": recomputed,
        "semantic_nodes_preserved": preserved_semantic,
        "recomputation_records": recomputation_records,
        "final_correct": correct,
    }


def run_example() -> dict[str, Any]:
    """Run selective recovery and an isolated full-restart comparison."""
    selective = _run_selective_strategy()
    full_restart = _run_full_restart_baseline()

    same_failure = (
        selective["failure"].get("error") == "API_VERSION_MISMATCH"
        and selective["failure"].get("error") == full_restart["failure"].get("error")
        and selective["failure"].get("expected") == full_restart["failure"].get("expected")
        and selective["failure"].get("received") == full_restart["failure"].get("received")
    )
    if not same_failure:
        raise AssertionError("Selective and full-restart runs did not encounter the same failure.")

    comparison = {
        "same_failure": same_failure,
        "semantic_node_universe": list(SEMANTIC_NODE_IDS),
        "selective": {
            "failure": selective["failure"].get("error"),
            "replacement_action_succeeded": selective["verification"]["execution_successful"],
            "processed_node_ids": selective["semantic_nodes_processed"],
            "preserved_node_ids": selective["semantic_nodes_preserved"],
            "final_correct": selective["final_correct"],
        },
        "full_restart": {
            "failure": full_restart["failure"].get("error"),
            "replacement_action_succeeded": full_restart["verification"]["execution_successful"],
            "processed_node_ids": full_restart["semantic_nodes_processed"],
            "preserved_node_ids": full_restart["semantic_nodes_preserved"],
            "final_correct": full_restart["final_correct"],
        },
    }

    return {
        **selective,
        "comparison": comparison,
        "full_restart": full_restart,
    }


def _print_comparison(comparison: dict[str, Any]) -> None:
    selective = comparison["selective"]
    full = comparison["full_restart"]
    total = len(comparison["semantic_node_universe"])

    print("\nRecovery comparison (same API-version failure)")
    print(
        f"{'Strategy':<20} {'Failure':<24} {'Replacement':<16} "
        f"{'Semantic nodes':<17} {'Preserved':<12} {'Correct':<10}"
    )
    print("-" * 103)
    for label, result in (("Selective recovery", selective), ("Full restart", full)):
        processed_count = len(result["processed_node_ids"])
        preserved_count = len(result["preserved_node_ids"])
        replacement = "succeeded" if result["replacement_action_succeeded"] else "FAILED"
        correctness = "PASS" if result["final_correct"] else "FAIL"
        print(
            f"{label:<20} {result['failure']:<24} {replacement:<16} "
            f"{f'{processed_count}/{total} processed':<17} "
            f"{preserved_count:<12} {correctness:<10}"
        )

    selective_processed = selective["processed_node_ids"]
    selective_preserved = selective["preserved_node_ids"]
    full_processed = full["processed_node_ids"]
    full_preserved = full["preserved_node_ids"]
    print(
        "Selective recomputed: "
        + (", ".join(selective_processed) if selective_processed else "none")
    )
    print(
        "Selective preserved: "
        + (", ".join(selective_preserved) if selective_preserved else "none")
    )
    print(
        "Full-restart recomputed: "
        + (", ".join(full_processed) if full_processed else "none")
    )
    print(
        "Full-restart preserved: "
        + (", ".join(full_preserved) if full_preserved else "none")
    )
    print(
        "Comparison basis: all registered semantic CONCLUSION/PLAN nodes; "
        "replacement actions use the existing execution path in both runs."
    )


def main() -> int:
    result = run_example()
    verification = result["verification"]
    failure = result["failure"]
    recovery = result["recovery"]

    print("BeliefGraph example: order processing")
    print(
        "Initial failure: "
        f"{failure.get('error')} (expected={failure.get('expected')}, "
        f"received={failure.get('received')})"
    )
    print(f"Recovery status: {recovery.get('status')}")
    print(
        "Semantic recomputation: "
        f"{recovery.get('selective_recovery', {}).get('status')}"
    )
    print(f"Replacement action succeeded: {verification['execution_successful']}")
    print(f"Semantic values correct: {result['semantic_values_correct']}")
    stale_nodes = verification.get("stale_nodes", [])
    stale_semantic_nodes = verification.get("stale_semantic_nodes", [])
    recomputed_nodes = result.get("recomputed_node_ids", [])
    preserved_nodes = result.get("preserved_node_ids", [])
    print(f"Stale nodes remaining: {', '.join(stale_nodes) if stale_nodes else 'none'}")
    print(
        "Stale semantic nodes remaining: "
        f"{', '.join(stale_semantic_nodes) if stale_semantic_nodes else 'none'}"
    )
    print(
        "Recomputed nodes: "
        f"{', '.join(recomputed_nodes) if recomputed_nodes else 'none'}"
    )
    print(
        "Preserved nodes: "
        f"{', '.join(preserved_nodes) if preserved_nodes else 'none'}"
    )
    print(f"Independent branch preserved: {result['independent_branch_preserved']}")
    print(f"Recovery verified: {verification['verified']}")
    _print_comparison(result["comparison"])

    comparison = result["comparison"]
    all_correct = (
        verification["verified"]
        and result["independent_branch_preserved"]
        and comparison["same_failure"]
        and comparison["selective"]["final_correct"]
        and comparison["full_restart"]["final_correct"]
    )
    return 0 if all_correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
