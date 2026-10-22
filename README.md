# BeliefGraph

### Dependency-Aware Recovery for AI Agents

BeliefGraph helps developers understand how an AI agent's beliefs,
conclusions, plans, and actions depend on one another---and recover
intelligently when something changes.

When an assumption becomes invalid or an action fails, BeliefGraph
traces the affected dependencies, selectively recomputes registered
semantic nodes, and verifies the recovery while preserving unaffected
branches.

**Instead of restarting everything, recover what actually needs to
change.**

Built with Python, FastAPI, React, and TypeScript.

**Live Demo:** https://beliefgraph-frontend.onrender.com  
**API Documentation:** https://beliefgraph-api.onrender.com/docs  
**API Health:** https://beliefgraph-api.onrender.com/health

------------------------------------------------------------------------

## The Problem

AI agents often perform tasks through multiple dependent steps. A single
change can invalidate conclusions and plans built on top of an earlier
assumption.

Without explicit dependency tracking, developers may struggle to
determine:

-   Which conclusions became invalid after a change.
-   Which plans and actions need to be recomputed.
-   Which parts of an execution remain valid.
-   Whether recovery completed correctly.
-   How to reproduce and investigate a failure.

BeliefGraph makes these dependencies explicit so developers can trace
the impact of changes and perform targeted recovery.

## How It Works

BeliefGraph represents an agent's reasoning and execution state as a
dependency graph.

``` mermaid
flowchart TD
    A[Beliefs and Observations] --> B[Conclusions]
    B --> C[Plans]
    C --> D[Actions]
    E[Changed Belief or Failed Action] --> F[Dependency Analysis]
    F --> G[Identify Affected Nodes]
    G --> H[Selective Recalculation]
    H --> I[Recovery Verification]
    A -. Dependencies .-> B
    B -. Dependencies .-> C
    C -. Dependencies .-> D
```

When a change occurs, BeliefGraph:

1.  **Tracks dependencies** between beliefs, conclusions, plans, and
    actions.
2.  **Identifies affected nodes** whose validity may have changed.
3.  **Propagates invalidation** through relevant dependencies.
4.  **Recomputes selected nodes** using registered semantic
    recomputation logic.
5.  **Preserves unaffected branches** instead of automatically
    recomputing the entire graph.
6.  **Verifies recovery** and exposes the resulting state for
    inspection.

The goal is to make recovery more targeted, traceable, and easier to
debug.

## Key Features

-   **Dependency Graph:** Represent relationships between beliefs,
    conclusions, plans, and actions.
-   **Change Impact Analysis:** Trace which dependent nodes may be
    affected by a changed assumption or failed action.
-   **Selective Recovery:** Recompute affected semantic nodes instead of
    automatically restarting the entire graph.
-   **Failure Propagation:** Track how invalidation can propagate
    through dependent nodes.
-   **Recovery Verification:** Inspect whether the recovery process
    completed successfully.
-   **Execution Inspection:** Explore graph state and recovery outcomes
    through the API and web interface.
-   **Python SDK:** Integrate graph and recovery functionality into
    Python workflows.
-   **Automated Tests:** Validate graph behavior, recovery logic, and
    related functionality.

------------------------------------------------------------------------

## Quick Start

### Prerequisites

-   Python 3.10 or later
-   Git
-   Node.js and npm, if you want to run the frontend separately

### 1. Clone the repository

``` bash
git clone https://github.com/Simi268/belief-graph.git
cd belief-graph
```

### 2. Create a virtual environment

**Windows (PowerShell):**

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

``` cmd
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

``` bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

``` bash
python -m pip install -r requirements.txt
```

### 4. Start the API

``` bash
uvicorn app.main:app --reload
```

The API will be available at:

-   **API:** http://127.0.0.1:8000
-   **Interactive API documentation:** http://127.0.0.1:8000/docs
-   **Health check:** http://127.0.0.1:8000/health

------------------------------------------------------------------------

## Run with Docker

BeliefGraph can also be built and run inside a Docker container.

### 1. Build the image

``` bash
docker build -t beliefgraph:local .
```

### 2. Start the API

``` bash
docker run -d --name beliefgraph-api -p 8000:8000 beliefgraph:local
```

### 3. Check the service

Open http://localhost:8000/health or run:

``` bash
curl http://localhost:8000/health
```

### 4. Run the test suite

Run the tests in a separate container:

``` bash
docker run --rm beliefgraph:local python -m pytest -q
```

The project documentation has previously reported 379 tests passing in a
clean Docker build. Re-run the command above against the current commit
to verify the present test count and result.

### 5. Stop the API

``` bash
docker rm -f beliefgraph-api
```

**Note:** The image includes project files copied during the Docker
build. Runtime data persistence depends on how storage is configured and
whether persistent volumes are mounted.

------------------------------------------------------------------------

## Example: Recovering from an API Version Change

Consider an agent processing an order.

The agent has already checked inventory, pricing, and shipping
requirements. It then attempts to create an order using an API version
that is no longer accepted.

A full restart could repeat all previous checks. BeliefGraph instead
uses the dependency graph to identify the semantic nodes affected by the
failure.

### Example workflow

1.  The agent attempts an operation with an outdated API version.
2.  The operation fails with an API version mismatch.
3.  BeliefGraph identifies the affected dependencies.
4.  Registered recomputation logic updates the relevant semantic nodes.
5.  The agent retries using the replacement action.
6.  The recovery process verifies the resulting state.

### Representative result

In the included deterministic order-processing recovery scenario:

| Metric | Selective recovery | Full restart |
| --- | ---: | ---: |
| Semantic nodes processed | 2 of 4 | 4 of 4 |
| Unaffected semantic nodes preserved | 2 | 0 |
| Recovery outcome | Successful | Successful |

Both approaches succeed in this controlled scenario. Selective recovery
processes fewer semantic nodes while preserving the unaffected branch.

These results describe one example, not a guarantee of improved
performance for every agent or workload.

### Run the example

``` bash
python -m examples.order_processing_recovery
```

The example demonstrates the recovery workflow, including the detected
failure, recomputed nodes, preserved nodes, and recovery verification.

------------------------------------------------------------------------

## Run the LLM-Backed Agent Recovery Example

BeliefGraph includes an LLM-backed example showing how an AI agent can
participate in a recovery workflow while BeliefGraph independently
manages dependency-aware recovery.

The example uses a simulated order-processing agent and a Groq-hosted
language model.

### What the example demonstrates

1.  The agent attempts an action using a cached API version.
2.  The simulated tool rejects the request because the API version is
    outdated.
3.  The LLM receives the actual tool failure and proposes a recovery
    decision.
4.  BeliefGraph runs its evidence-driven recovery process independently.
5.  The replacement action executes, and the example checks the recovery
    outcome.
6.  The example compares selective recovery with a full-restart
    baseline.

The example also checks whether the LLM's proposal agrees with the tool
evidence and the replacement action selected by BeliefGraph.

**Important:** The LLM proposes a decision; it does not replace
BeliefGraph's recovery engine. This controlled integration experiment
does not establish general performance improvements or production
readiness.

### Requirements

Activate the virtual environment created during the quick start, then
install the additional dependencies used by the example:

``` bash
python -m pip install langchain-groq python-dotenv
```

Create a local `.env` file in the repository root:

``` dotenv
GROQ_API_KEY=your_groq_api_key
```

Replace the placeholder with your own key. Do not commit `.env` or
expose API keys in source code, logs, or screenshots.

The example's configured model must be available to your Groq account.
If the provider changes model availability, update the model
configuration in `examples/llm_agent_recovery.py` accordingly.

### Run the example

From the repository root:

``` bash
python -m examples.llm_agent_recovery
```

A successful run should end with:

``` text
Connected workflow: PASS
```

The example reports the tool failure, LLM proposal, BeliefGraph recovery
outcome, recomputed and preserved nodes, and validation results. Exact
metrics and timings can vary between runs.

### Interpreting the results

The example reports the number of semantic nodes recomputed by
BeliefGraph and the number of graph nodes rebuilt by the full-restart
baseline.

These are different measurements of graph work, not a direct comparison
of equivalent runtime costs. Do not interpret the node-count difference
as a percentage reduction in latency or total computational cost.

This is a small-scale integration experiment intended to demonstrate the
workflow, not a general benchmark across AI agents.

------------------------------------------------------------------------

## Python SDK

BeliefGraph provides Python interfaces for working with dependency
graphs and recovery operations.

At a high level, an integration typically involves:

1.  Building a graph of beliefs, conclusions, plans, and actions.
2.  Registering dependencies between nodes.
3.  Registering semantic evaluators where recomputation is needed.
4.  Executing an action or workflow.
5.  Reporting a changed belief or failed action to the recovery API.
6.  Inspecting the recovery result and resulting graph state.

For a working implementation, start with
`examples/order_processing_recovery.py` and
`examples/llm_agent_recovery.py`. The public SDK implementation is in
`app/sdk.py`.

The exact recovery behavior depends on the graph, registered
dependencies, and available semantic recomputation logic. BeliefGraph
does not automatically understand every agent's reasoning or replace the
agent's execution framework.

------------------------------------------------------------------------

## Frontend

BeliefGraph includes a React and TypeScript frontend for interacting
with the application.

To run it locally, open a second terminal:

``` bash
cd frontend
npm install
npm run dev
```

Use the development URL printed by Vite.

Ensure the backend API is running and configure the frontend's API
endpoint according to the project's existing configuration.

------------------------------------------------------------------------

## Project Structure

``` text
belief-graph/
├── app/
│   ├── sdk.py                    # Python SDK
│   ├── recovery_report.py        # Recovery reporting
│   └── ...                       # API and core application logic
├── examples/
│   ├── order_processing_recovery.py
│   └── llm_agent_recovery.py
├── experiments/                  # Experimental scenarios and evaluations
├── tests/
│   ├── test_recovery_report.py
│   └── ...                       # Automated tests
├── data/                         # Project data
├── frontend/                     # React and TypeScript interface
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── README.md
```

------------------------------------------------------------------------

## Current Scope and Limitations

BeliefGraph is an engineering prototype for dependency-aware recovery in
multi-step AI agent workflows.

Its recovery behavior depends on the graph structure, registered
dependencies, and available semantic recomputation logic. It does not
automatically understand every agent's reasoning or replace the
execution framework itself.

The current implementation focuses on:

-   Explicit dependency representation.
-   Change impact and invalidation propagation.
-   Selective semantic recomputation.
-   Preservation of unaffected graph branches.
-   Recovery verification and automated testing.

The included examples and tests demonstrate implemented behavior.
Broader performance, scalability, and effectiveness claims require
evaluation across additional workloads.

------------------------------------------------------------------------

## Contributing

Contributions, bug reports, and suggestions are welcome.

If you find an issue or have an idea for improving dependency tracking
or recovery, open a GitHub issue or submit a pull request.
