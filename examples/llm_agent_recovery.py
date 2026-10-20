"""LLM-backed tool agent integrated with BeliefGraph.

Run from the repository root:
    python -m examples.llm_agent_recovery

Requires GROQ_API_KEY in the project-root .env file.
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.environment import DynamicAPIEnvironment
from app.models import NodeStatus
from app.sdk import BeliefGraphSDK


MODEL_NAME = "openai/gpt-oss-120b"


def ask_agent(llm, task: str, tool_result: dict[str, Any] | None = None) -> dict:
    """Ask the real LLM to select an order action and API version."""
    prompt = {
        "task": task,
        "tool_result": tool_result,
        "available_tool": {
            "name": "create_order",
            "description": "Create an order using the selected API version.",
            "accepted_versions": ["v1", "v2"],
        },
        "instruction": (
            'Return only a JSON object with "action", "api_version", and '
            '"reason". The action must be "create_order"; api_version must '
            'be "v1" or "v2".'
        ),
    }

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are an order-processing agent. Use the task and any "
                    "tool feedback to choose an API version. Return valid JSON only."
                )
            ),
            HumanMessage(content=json.dumps(prompt)),
        ]
    )

    text = response.content
    if not isinstance(text, str):
        raise ValueError("Expected a text response from the LLM.")

    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()

    decision = json.loads(text)
    if decision.get("action") != "create_order":
        raise ValueError("The LLM returned an unsupported action.")
    if decision.get("api_version") not in {"v1", "v2"}:
        raise ValueError("The LLM returned an unsupported API version.")
    return decision


def build_agent(initial_api_version: str = "v1"):
    """Create the order scenario with a specified cached API version."""
    sdk = BeliefGraphSDK()
    environment = DynamicAPIEnvironment()

    sdk.belief(
        "B_API_VERSION",
        "Cached order API version",
        value=initial_api_version,
        source="service-discovery-cache",
    )
    sdk.belief(
        "B_INVENTORY",
        "Available inventory for SKU-104",
        value={"sku": "SKU-104", "available_quantity": 8},
        source="inventory-service",
    )
    sdk.belief(
        "B_PRICING",
        "Approved price for SKU-104",
        value={"unit_price": 24.50, "maximum_approved_price": 30.00},
        source="pricing-service",
    )

    sdk.conclusion(
        "C_ORDER_ELIGIBLE",
        "Whether the order can be submitted",
        value={"eligible": True, "api_version": initial_api_version},
    )
    sdk.plan(
        "P_CREATE_ORDER",
        "Create an order for two units of SKU-104",
        value={"api_version": initial_api_version, "quantity": 2},
    )
    sdk.action(
        "A_SUBMIT_ORDER",
        "Submit the order",
        value=initial_api_version,
    )

    sdk.depends_on("B_API_VERSION", "C_ORDER_ELIGIBLE")
    sdk.depends_on("B_INVENTORY", "C_ORDER_ELIGIBLE")
    sdk.depends_on("B_PRICING", "C_ORDER_ELIGIBLE")
    sdk.depends_on("C_ORDER_ELIGIBLE", "P_CREATE_ORDER")
    sdk.depends_on("P_CREATE_ORDER", "A_SUBMIT_ORDER")

    # Independent branch: it should not be recomputed when the API version changes.
    sdk.belief(
        "B_SHIPPING_AUTH",
        "Shipping carrier credentials are valid",
        value=True,
        source="shipping-configuration",
    )
    sdk.conclusion(
        "C_SHIPPING_READY",
        "The shipping integration is ready",
        value={"ready": True},
    )
    sdk.plan(
        "P_CREATE_SHIPMENT",
        "Create a shipment after order acceptance",
        value={"enabled": True},
    )
    sdk.depends_on("B_SHIPPING_AUTH", "C_SHIPPING_READY")
    sdk.depends_on("C_SHIPPING_READY", "P_CREATE_SHIPMENT")

    # Register deterministic semantic evaluators. These recalculate graph
    # state; the LLM is used for decisions, not for claiming correctness.
    def evaluate_order_eligibility(node, predecessors):
        api_version = predecessors.get("B_API_VERSION_V2", predecessors.get("B_API_VERSION"))
        inventory = predecessors["B_INVENTORY"]
        pricing = predecessors["B_PRICING"]
        quantity = 2
        in_stock = inventory["available_quantity"] >= quantity
        price_approved = pricing["unit_price"] <= pricing["maximum_approved_price"]
        return {
            "eligible": api_version == "v2" and in_stock and price_approved,
            "api_version": api_version,
            "sku": inventory["sku"],
            "requested_quantity": quantity,
            "available_quantity": inventory["available_quantity"],
            "unit_price": pricing["unit_price"],
            "price_approved": price_approved,
            "within_stock": in_stock,
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

    sdk.register_evaluator("C_ORDER_ELIGIBLE", evaluate_order_eligibility)
    sdk.register_evaluator("P_CREATE_ORDER", evaluate_order_plan)

    return sdk, environment


def run_connected_agent_workflow(llm) -> dict:
    """Run one connected workflow: real tool failure -> LLM decision -> BeliefGraph recovery."""
    print("=" * 64)
    print("CONNECTED LLM AGENT + BELIEFGRAPH RECOVERY")
    print("=" * 64)

    sdk, environment = build_agent()
    # Deliberately seed a stale cached belief while the live tool uses v2.
    # This makes the failure reproducible instead of depending on model behavior.
    environment.set_api_version("v2")

    print("\n1. Execute the agent's current cached action (v1).")
    action_result = sdk.execute_action(
        action_id="A_SUBMIT_ORDER",
        belief_id="B_API_VERSION",
        environment=environment,
    )
    failure = action_result.get("environment_result", {})
    print("Actual tool result:")
    print(json.dumps(failure, indent=2, default=str))

    if failure.get("error") != "API_VERSION_MISMATCH":
        raise RuntimeError(
            "Expected the seeded stale-v1 action to fail with API_VERSION_MISMATCH."
        )

    print("\n2. Send the ACTUAL tool failure to the LLM.")
    revised_decision = ask_agent(
        llm,
        (
            "An order for two units of SKU-104 failed. Select the API version "
            "for the next attempt using the tool feedback and the current task."
        ),
        tool_result=failure,
    )
    print("LLM recovery decision:")
    print(json.dumps(revised_decision, indent=2))

    # Validate the proposal against the actual tool response before treating it
    # as a sound recovery recommendation. A disagreement does not alter the
    # evidence-driven engine; it is surfaced and causes the overall check to fail.
    evidence_expected_version = failure.get("expected")
    llm_decision_validated = (
        revised_decision["api_version"] == evidence_expected_version
    )
    print(
        "LLM decision validated against tool evidence:",
        llm_decision_validated,
    )
    if not llm_decision_validated:
        print(
            "WARNING: LLM proposal conflicts with tool evidence. "
            "BeliefGraph will still run its independent evidence-driven recovery."
        )

    print("\n3. Run BeliefGraph's existing evidence-driven recovery.")
    recovery = sdk.recover_from_action_failure(
        action_result=action_result,
        evidence_id="E_API_VERSION_MISMATCH",
        new_belief_id="B_API_VERSION_V2",
        new_action_id="A_SUBMIT_ORDER_V2",
        environment=environment,
    )

    replacement = recovery.get("execution") or {}
    selective = recovery.get("selective_recovery") or {}
    metrics = recovery.get("recovery_metrics", {})

    print("Recovery status:", recovery.get("status"))
    print("Replacement action:")
    print(json.dumps(replacement, indent=2, default=str))
    print("Selective recovery metrics:")
    print(json.dumps(metrics, indent=2, default=str))
    print("Recomputed nodes:", selective.get("recomputed_node_ids", []))
    print("Preserved nodes:", selective.get("preserved_node_ids", []))

    # Confirm the engine's replacement agrees with the evidence and separately
    # report whether the LLM proposal agreed. The LLM does not control the engine.
    replacement_version = replacement.get("assumed_version")
    llm_agrees_with_recovery = (
        revised_decision["api_version"] == replacement_version
    )
    replacement_agrees_with_evidence = (
        replacement_version == evidence_expected_version
    )

    independent_branch_preserved = all(
        sdk.get(node_id).status == NodeStatus.ACTIVE
        for node_id in (
            "B_SHIPPING_AUTH",
            "C_SHIPPING_READY",
            "P_CREATE_SHIPMENT",
        )
    )
    semantic_values_correct = (
        sdk.get("C_ORDER_ELIGIBLE").value.get("api_version") == "v2"
        and sdk.get("P_CREATE_ORDER").value.get("api_version") == "v2"
        and sdk.get("P_CREATE_ORDER").value.get("enabled") is True
    )
    recovery_succeeded = replacement.get("success") is True

    # Execute a separate full-restart baseline on the same scenario:
    # rebuild the graph from scratch with the corrected v2 belief, then submit
    # the same order. This is a real baseline execution, but its timing includes
    # graph construction + action while recovery timing is engine-side only.
    import time

    baseline_start = time.perf_counter()
    baseline_sdk, baseline_environment = build_agent(initial_api_version="v2")
    baseline_environment.set_api_version("v2")
    baseline_action = baseline_sdk.execute_action(
        action_id="A_SUBMIT_ORDER",
        belief_id="B_API_VERSION",
        environment=baseline_environment,
    )
    full_restart_elapsed_ms = (time.perf_counter() - baseline_start) * 1000
    baseline_node_ids = [
        "B_API_VERSION",
        "B_INVENTORY",
        "B_PRICING",
        "C_ORDER_ELIGIBLE",
        "P_CREATE_ORDER",
        "A_SUBMIT_ORDER",
        "B_SHIPPING_AUTH",
        "C_SHIPPING_READY",
        "P_CREATE_SHIPMENT",
    ]
    full_restart_node_count = sum(
        1 for node_id in baseline_node_ids if baseline_sdk.get(node_id) is not None
    )
    full_restart_succeeded = (
        (baseline_action.get("environment_result") or {}).get("success") is True
    )
    selective_recomputed_count = len(selective.get("recomputed_node_ids", []))
    work_reduction = (
        1 - selective_recomputed_count / full_restart_node_count
        if full_restart_node_count
        else 0.0
    )

    print("\n4. Validation")
    print("LLM decision validated against tool evidence:", llm_decision_validated)
    print("LLM agrees with replacement version:", llm_agrees_with_recovery)
    print("Replacement agrees with tool evidence:", replacement_agrees_with_evidence)
    print("Replacement succeeded:", recovery_succeeded)
    print("Independent shipping branch preserved:", independent_branch_preserved)
    print("Order semantic values correct:", semantic_values_correct)
    print("\n5. Executed full-restart baseline")
    print("Full-restart graph nodes rebuilt:", full_restart_node_count)
    print("Full-restart order succeeded:", full_restart_succeeded)
    print(f"Full-restart build + action time: {full_restart_elapsed_ms:.3f} ms")
    print("BeliefGraph semantic nodes recomputed:", selective_recomputed_count)
    print(f"Node-count reduction vs rebuilt graph: {work_reduction:.1%}")
    print(
        "Timing note: these durations cover different scopes (full graph build + "
        "action versus recovery-engine metrics). Do not interpret them as a fair "
        "latency speedup comparison."
    )

    passed = (
        recovery_succeeded
        and independent_branch_preserved
        and semantic_values_correct
        and llm_decision_validated
        and llm_agrees_with_recovery
        and replacement_agrees_with_evidence
        and full_restart_succeeded
    )
    print("\nConnected workflow:", "PASS" if passed else "FAIL")

    return {
        "passed": passed,
        "failure": failure,
        "llm_decision": revised_decision,
        "recovery": recovery,
        "replacement": replacement,
        "llm_decision_validated": llm_decision_validated,
        "llm_agrees_with_recovery": llm_agrees_with_recovery,
        "replacement_agrees_with_evidence": replacement_agrees_with_evidence,
        "independent_branch_preserved": independent_branch_preserved,
        "semantic_values_correct": semantic_values_correct,
        "full_restart_node_count": full_restart_node_count,
        "full_restart_succeeded": full_restart_succeeded,
        "full_restart_elapsed_ms": full_restart_elapsed_ms,
        "selective_recomputed_count": selective_recomputed_count,
        "work_reduction": work_reduction,
    }


def run_controlled_recovery() -> dict:
    """Reproduce a stale-v1 failure, then use the existing recovery engine."""
    print("\n" + "=" * 64)
    print("STAGE 2: CONTROLLED BELIEFGRAPH RECOVERY")
    print("=" * 64)

    sdk, environment = build_agent()
    environment.set_api_version("v2")

    action_result = sdk.execute_action(
        action_id="A_SUBMIT_ORDER",
        belief_id="B_API_VERSION",
        environment=environment,
    )
    failure = action_result.get("environment_result", {})
    print("Initial action result:")
    print(json.dumps(failure, indent=2))

    if failure.get("error") != "API_VERSION_MISMATCH":
        raise RuntimeError(
            "Expected API_VERSION_MISMATCH. Check DynamicAPIEnvironment behavior."
        )

    recovery = sdk.recover_from_action_failure(
        action_result=action_result,
        evidence_id="E_API_VERSION_MISMATCH",
        new_belief_id="B_API_VERSION_V2",
        new_action_id="A_SUBMIT_ORDER_V2",
        environment=environment,
    )

    replacement = recovery.get("execution") or {}
    selective = recovery.get("selective_recovery") or {}
    metrics = recovery.get("recovery_metrics", {})

    print("\nRecovery status:", recovery.get("status"))
    print("Replacement action:", json.dumps(replacement, indent=2, default=str))
    print("Recovery metrics:", json.dumps(metrics, indent=2, default=str))
    print("Recomputed nodes:", selective.get("recomputed_node_ids", []))
    print("Preserved nodes:", selective.get("preserved_node_ids", []))

    independent_branch_preserved = all(
        sdk.get(node_id).status == NodeStatus.ACTIVE
        for node_id in (
            "B_SHIPPING_AUTH",
            "C_SHIPPING_READY",
            "P_CREATE_SHIPMENT",
        )
    )
    semantic_values_correct = (
        sdk.get("C_ORDER_ELIGIBLE").value.get("api_version") == "v2"
        and sdk.get("P_CREATE_ORDER").value.get("api_version") == "v2"
        and sdk.get("P_CREATE_ORDER").value.get("enabled") is True
    )

    passed = (
        replacement.get("success") is True
        and independent_branch_preserved
        and semantic_values_correct
    )

    print("\nIndependent shipping branch preserved:", independent_branch_preserved)
    print("Order semantic values correct:", semantic_values_correct)
    print("Controlled recovery test:", "PASS" if passed else "FAIL")

    return {
        "passed": passed,
        "failure": failure,
        "recovery": recovery,
        "replacement": replacement,
        "independent_branch_preserved": independent_branch_preserved,
        "semantic_values_correct": semantic_values_correct,
    }


def main() -> int:
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to the project-root .env file."
        )

    llm = ChatGroq(
        model=MODEL_NAME,
        temperature=0,
        api_key=api_key,
    )

    result = run_connected_agent_workflow(llm)

    print("\n" + "=" * 64)
    print("FINAL SUMMARY")
    print("=" * 64)
    print("LLM recovery decision:", result["llm_decision"]["api_version"])
    print("LLM decision validated:", result["llm_decision_validated"])
    print("LLM agrees with BeliefGraph replacement:", result["llm_agrees_with_recovery"])
    print("BeliefGraph recovery:", "PASS" if result["passed"] else "FAIL")
    print(
        "Executed baseline:",
        f'{result["full_restart_node_count"]} nodes rebuilt; '
        f'action success={result["full_restart_succeeded"]}; '
        f'build+action={result["full_restart_elapsed_ms"]:.3f} ms',
    )
    print(
        "Graph-work comparison:",
        f'{result["selective_recomputed_count"]} semantic nodes recomputed by '
        f'BeliefGraph versus {result["full_restart_node_count"]} nodes rebuilt',
    )
    print(
        "Interpretation: this is a reproducible small-scale integration experiment. "
        "Timing scopes differ, so no latency speedup claim is made."
    )

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
