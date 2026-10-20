"""Small first-run example for BeliefGraph.

Run from the repository root:
    python -m examples.quickstart

This introduces the public SDK and explicit dependency edges. For a complete
failure -> evidence -> revision -> selective recovery workflow, run:
    python -m examples.order_processing_recovery
"""
from app.models import DependencyType
from app.sdk import BeliefGraphSDK


def main() -> None:
    sdk = BeliefGraphSDK()

    # 1. Declare facts the agent currently relies on.
    sdk.belief(
        "B_API_VERSION",
        "Version recorded by service discovery",
        value="v1",
        source="service-discovery",
    )
    sdk.belief(
        "B_INVENTORY",
        "Available inventory for the requested item",
        value=8,
        source="inventory-service",
    )

    # 2. Declare derived reasoning and the action it supports.
    sdk.conclusion(
        "C_CAN_ORDER",
        "The order can be submitted",
        value=True,
    )
    sdk.plan(
        "P_CREATE_ORDER",
        "Create an order for the requested item",
        value={"enabled": True},
    )
    sdk.action(
        "A_SUBMIT_ORDER",
        "Submit the order to the service",
        value="v1",
    )

    # 3. Declare dependencies explicitly: prerequisite -> dependent.
    sdk.depends_on("B_API_VERSION", "C_CAN_ORDER")
    sdk.depends_on("B_INVENTORY", "C_CAN_ORDER")
    sdk.depends_on("C_CAN_ORDER", "P_CREATE_ORDER")
    sdk.depends_on("P_CREATE_ORDER", "A_SUBMIT_ORDER")

    # 4. Register domain logic for derived nodes that may need recomputation.
    @sdk.register_evaluator("C_CAN_ORDER")
    def evaluate_order_eligibility(node, predecessors):
        return (
            predecessors["B_API_VERSION"] == "v2"
            and predecessors["B_INVENTORY"] > 0
        )

    @sdk.register_evaluator("P_CREATE_ORDER")
    def evaluate_order_plan(node, predecessors):
        return {"enabled": bool(predecessors["C_CAN_ORDER"])}

    # 5. Inspect the current graph and impact of a changed source fact.
    print("BeliefGraph quickstart")
    print("----------------------")
    print("Nodes:", len(sdk.graph.graph.nodes))
    print("Dependencies:", len(sdk.graph.graph.edges))
    print("Current order eligibility:", sdk.get("C_CAN_ORDER").value)
    print("Current order plan:", sdk.get("P_CREATE_ORDER").value)

    impact = sdk.analyze_impact(["B_API_VERSION"])
    print("\nImpact analysis after B_API_VERSION changes:")
    for node_id, details in impact.items():
        if isinstance(details, dict) and "impact" in details:
            print(f"- {node_id}: {details['impact']}")

    print(
        "\nNote: registering an evaluator defines how a node is recomputed; "
        "it does not automatically execute the evaluator. Run the complete "
        "recovery example to see an end-to-end recovery."
    )


if __name__ == "__main__":
    main()
