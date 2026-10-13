from app.agent import AgentRuntime
from app.models import DependencyType, NodeStatus, NodeType
from app.runs import RunSession


def test_each_runtime_has_an_independent_graph():
    runtime_a = AgentRuntime()
    runtime_b = AgentRuntime()

    assert runtime_a.graph is not runtime_b.graph


def test_same_node_id_can_exist_in_separate_runtimes():
    runtime_a = AgentRuntime()
    runtime_b = AgentRuntime()

    runtime_a.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
    )

    runtime_b.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
    )

    assert runtime_a.graph.get_node("B1").value == "v1"
    assert runtime_b.graph.get_node("B1").value == "v1"

    assert (
        runtime_a.graph.get_node("B1")
        is not runtime_b.graph.get_node("B1")
    )


def test_revising_one_runtime_does_not_change_another():
    runtime_a = AgentRuntime()
    runtime_b = AgentRuntime()

    runtime_a.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
    )

    runtime_b.create_belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
    )

    runtime_a.create_node(
        node_id="C1",
        node_type=NodeType.CONCLUSION,
        content="The v1 endpoint is valid",
    )

    runtime_a.add_dependency(
        "B1",
        "C1",
        DependencyType.REQUIRES,
    )

    new_belief = runtime_a.create_belief(
        belief_id="B2",
        content="API version is v2",
        value="v2",
    )

    runtime_a.graph.revise_belief(
        old_id="B1",
        new_belief=new_belief,
    )

    assert (
        runtime_a.graph.get_node("B1").status
        == NodeStatus.INVALID
    )

    assert (
        runtime_b.graph.get_node("B1").status
        == NodeStatus.ACTIVE
    )


def test_run_sessions_have_unique_ids_and_independent_graphs():
    run_a = RunSession()
    run_b = RunSession()

    assert run_a.run_id != run_b.run_id
    assert run_a.graph is not run_b.graph


def test_run_sessions_keep_same_node_ids_independent():
    run_a = RunSession()
    run_b = RunSession()

    run_a.belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
    )

    run_b.belief(
        belief_id="B1",
        content="API version is v2",
        value="v2",
    )

    assert run_a.get("B1").value == "v1"
    assert run_b.get("B1").value == "v2"


def test_sdk_new_run_creates_isolated_sessions():
    from app.sdk import BeliefGraphSDK

    sdk = BeliefGraphSDK()

    run_a = sdk.new_run()
    run_b = sdk.new_run()

    assert run_a.run_id != run_b.run_id
    assert run_a.graph is not run_b.graph

    run_a.belief(
        belief_id="B1",
        content="API version is v1",
        value="v1",
    )

    assert run_a.get("B1").value == "v1"

    try:
        run_b.get("B1")
    except KeyError:
        pass
    else:
        raise AssertionError("Run B must not contain Run A's belief.")

def test_langgraph_adapters_can_use_separate_run_sessions():
    from app.langgraph_adapter import LangGraphAdapter

    run_a = RunSession()
    run_b = RunSession()

    adapter_a = LangGraphAdapter(belief_graph=run_a.sdk)
    adapter_b = LangGraphAdapter(belief_graph=run_b.sdk)

    adapter_a.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        value="v1",
    )

    adapter_b.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v2",
        value="v2",
    )

    assert adapter_a.graph is not adapter_b.graph
    assert adapter_a.get(node_id="B1").value == "v1"
    assert adapter_b.get(node_id="B1").value == "v2"

def test_recovery_in_one_run_does_not_affect_another_run():
    run_a = RunSession()
    run_b = RunSession()

    # Create identical initial graphs in both runs.
    for run in (run_a, run_b):
        run.belief(
            belief_id="B1",
            content="API version is v1",
            value="v1",
        )
        run.conclusion(
            node_id="C1",
            content="The v1 endpoint is valid",
        )
        run.depends_on(
            source_id="B1",
            target_id="C1",
        )

    # Create a replacement belief in Run A.
    run_a.belief(
        belief_id="B2",
        content="API version is v2",
        value="v2",
    )

    # Revise B1 directly through Run A's runtime.
    run_a.runtime.graph.revise_belief(
        old_id="B1",
        new_belief=run_a.get("B2"),
    )

    # Run A should reflect the revision.
    assert run_a.status("B1") == NodeStatus.INVALID

    # Run B must remain unchanged.
    assert run_b.status("B1") == NodeStatus.ACTIVE
    assert run_b.status("C1") == NodeStatus.ACTIVE

def test_run_session_creates_adapter_bound_to_its_own_graph():
    run_a = RunSession()
    run_b = RunSession()

    adapter_a = run_a.langgraph_adapter()
    adapter_b = run_b.langgraph_adapter()

    assert adapter_a.graph is run_a.graph
    assert adapter_b.graph is run_b.graph
    assert adapter_a.graph is not adapter_b.graph

    adapter_a.register_node(
        langgraph_node="retrieve",
        belief_node_id="B1",
        node_type=NodeType.BELIEF,
        content="API version is v1",
        value="v1",
    )

    assert run_a.get("B1").value == "v1"

    try:
        run_b.get("B1")
    except KeyError:
        pass
    else:
        raise AssertionError(
            "Run B must not contain Run A's belief."
        )