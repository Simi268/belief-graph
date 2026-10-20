# BeliefGraph Quickstart Patch

## First run

From the repository root, activate the project's virtual environment and install
the dependencies using the repository's existing setup instructions. Then run:

```bash
python -m examples.quickstart
```

This small example introduces the public SDK without asking a new user to read
the full recovery scenario first. It demonstrates:

1. Declaring source beliefs.
2. Declaring a conclusion, plan, and action.
3. Connecting nodes with explicit prerequisite-to-dependent edges.
4. Registering developer-defined evaluators.
5. Inspecting graph size and analyzing the impact of a changed belief.

**Important:** evaluator registration defines the recomputation logic; it does
not run that logic immediately. For a complete failure, evidence, belief
revision, selective recomputation, replacement action, and verification flow,
run the existing end-to-end example:

```bash
python -m examples.order_processing_recovery
```

## Mental model

- **Belief:** a source fact the agent currently relies on.
- **Conclusion:** a derived interpretation of one or more facts.
- **Plan:** a proposed next step based on the reasoning.
- **Action:** an operation the agent may execute.
- **Dependency:** an explicit edge from prerequisite to dependent.
- **Evaluator:** your domain-specific function for recomputing a derived node.

BeliefGraph does not infer every semantic dependency or invent domain logic for
your application. Developers declare dependencies and provide evaluators for
derived nodes that need recomputation.

## Developer API: smallest useful pattern

```python
from app.sdk import BeliefGraphSDK

sdk = BeliefGraphSDK()

sdk.belief("B_STOCK", "Available stock", value=8)
sdk.conclusion("C_AVAILABLE", "Item is available", value=True)
sdk.depends_on("B_STOCK", "C_AVAILABLE")

@sdk.register_evaluator("C_AVAILABLE")
def evaluate_availability(node, predecessor_values):
    return predecessor_values["B_STOCK"] > 0
```

The dependency direction is `prerequisite -> dependent`. The evaluator receives
the node and a mapping of predecessor IDs to their current values, and returns
the recomputed value. Use `sdk.analyze_impact([...])` to inspect downstream
impact. Use `examples/order_processing_recovery.py` as the reference for the
complete action-failure recovery workflow.
