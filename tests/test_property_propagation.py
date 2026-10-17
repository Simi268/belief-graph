from hypothesis import given, settings, strategies as st

from app.graph import BeliefGraph
from app.models import BeliefNode, NodeStatus, NodeType, DependencyType


@given(
    num_nodes=st.integers(min_value=2, max_value=10),
    seed=st.integers(min_value=0, max_value=10000),
)
@settings(max_examples=100, deadline=None)
def test_generated_chain_propagation_terminates(num_nodes, seed):
    """
    Generated chain graphs should propagate impact to every
    dependent node without hanging or losing nodes.

    The seed determines which node IDs are used.
    """
    graph = BeliefGraph()

    node_ids = [
        f"N{seed}_{i}"
        for i in range(num_nodes)
    ]

    for i, node_id in enumerate(node_ids):
        graph.add_node(
            BeliefNode(
                id=node_id,
                node_type=(
                    NodeType.BELIEF
                    if i == 0
                    else NodeType.CONCLUSION
                ),
                content=f"Generated node {i}",
            )
        )

    for i in range(num_nodes - 1):
        graph.add_dependency(
            node_ids[i],
            node_ids[i + 1],
            DependencyType.REQUIRES,
        )

    result = graph.analyze_multi_belief_impact(
        [node_ids[0]],
        initial_status=NodeStatus.INVALID,
    )

    expected_affected = set(node_ids[1:])

    assert set(result) == expected_affected

    assert all(
        details["impact"] == NodeStatus.INVALID
        for details in result.values()
    )


@given(
    num_nodes=st.integers(min_value=2, max_value=10),
)
@settings(max_examples=100, deadline=None)
def test_generated_cycle_propagation_terminates(num_nodes):
    """
    Generated cyclic graphs should terminate and invalidate
    every node reachable from the changed belief.
    """
    graph = BeliefGraph()

    node_ids = [
        f"N{i}"
        for i in range(num_nodes)
    ]

    for i, node_id in enumerate(node_ids):
        graph.add_node(
            BeliefNode(
                id=node_id,
                node_type=(
                    NodeType.BELIEF
                    if i == 0
                    else NodeType.CONCLUSION
                ),
                content=f"Generated node {i}",
            )
        )

    # Create a directed cycle.
    for i in range(num_nodes):
        graph.add_dependency(
            node_ids[i],
            node_ids[(i + 1) % num_nodes],
            DependencyType.REQUIRES,
        )

    result = graph.analyze_multi_belief_impact(
        [node_ids[0]],
        initial_status=NodeStatus.INVALID,
    )

    expected_affected = set(node_ids[1:])

    assert set(result) == expected_affected

    assert all(
        details["impact"] == NodeStatus.INVALID
        for details in result.values()
    )

@given(
    num_branches=st.integers(min_value=2, max_value=6),
)
@settings(max_examples=50, deadline=None)
def test_generated_branching_preserves_causal_attribution(num_branches):
    """
    A changed root propagating through multiple branches into a
    shared dependent should preserve causal attribution.
    """
    graph = BeliefGraph()

    root_id = "ROOT"
    shared_id = "SHARED"

    graph.add_node(
        BeliefNode(
            id=root_id,
            node_type=NodeType.BELIEF,
            content="Changed root belief",
        )
    )

    graph.add_node(
        BeliefNode(
            id=shared_id,
            node_type=NodeType.PLAN,
            content="Shared downstream plan",
        )
    )

    for i in range(num_branches):
        branch_id = f"BRANCH_{i}"

        graph.add_node(
            BeliefNode(
                id=branch_id,
                node_type=NodeType.CONCLUSION,
                content=f"Branch {i}",
            )
        )

        graph.add_dependency(
            root_id,
            branch_id,
            DependencyType.REQUIRES,
        )

        graph.add_dependency(
            branch_id,
            shared_id,
            DependencyType.REQUIRES,
        )

    result = graph.analyze_multi_belief_impact(
        [root_id],
        initial_status=NodeStatus.INVALID,
    )

    expected_affected = {
        *(f"BRANCH_{i}" for i in range(num_branches)),
        shared_id,
    }

    assert set(result) == expected_affected

    assert set(result[shared_id]["affected_by"]) == {root_id}

    assert all(
        details["impact"] == NodeStatus.INVALID
        for details in result.values()
    )

@given(
    num_roots=st.integers(min_value=2, max_value=6),
)
@settings(max_examples=50, deadline=None)
def test_generated_multiple_roots_preserve_causal_attribution(num_roots):
    """
    Multiple changed roots converging on a shared dependent
    should preserve every causal source.
    """
    graph = BeliefGraph()

    root_ids = [f"ROOT_{i}" for i in range(num_roots)]
    shared_id = "SHARED_PLAN"

    for root_id in root_ids:
        graph.add_node(
            BeliefNode(
                id=root_id,
                node_type=NodeType.BELIEF,
                content=f"Changed belief {root_id}",
            )
        )

    graph.add_node(
        BeliefNode(
            id=shared_id,
            node_type=NodeType.PLAN,
            content="Shared downstream plan",
        )
    )

    for root_id in root_ids:
        graph.add_dependency(
            root_id,
            shared_id,
            DependencyType.REQUIRES,
        )

    result = graph.analyze_multi_belief_impact(
        root_ids,
        initial_status=NodeStatus.INVALID,
    )

    assert set(result) == {shared_id}

    assert set(result[shared_id]["affected_by"]) == set(root_ids)

    assert result[shared_id]["impact"] == NodeStatus.INVALID

@given(
    num_roots=st.integers(min_value=2, max_value=6),
)
@settings(max_examples=50, deadline=None)
def test_generated_root_order_does_not_change_results(num_roots):
    """
    Reversing the order of changed roots should not change
    impact states or causal attribution.
    """

    def build_graph():
        graph = BeliefGraph()

        root_ids = [f"ROOT_{i}" for i in range(num_roots)]

        for root_id in root_ids:
            graph.add_node(
                BeliefNode(
                    id=root_id,
                    node_type=NodeType.BELIEF,
                    content=f"Changed belief {root_id}",
                )
            )

        graph.add_node(
            BeliefNode(
                id="SHARED",
                node_type=NodeType.PLAN,
                content="Shared downstream plan",
            )
        )

        graph.add_node(
            BeliefNode(
                id="DOWNSTREAM",
                node_type=NodeType.ACTION,
                content="Downstream action",
            )
        )

        for root_id in root_ids:
            graph.add_dependency(
                root_id,
                "SHARED",
                DependencyType.REQUIRES,
            )

        graph.add_dependency(
            "SHARED",
            "DOWNSTREAM",
            DependencyType.REQUIRES,
        )

        return graph, root_ids

    graph_forward, root_ids = build_graph()
    graph_reverse, _ = build_graph()

    forward = graph_forward.analyze_multi_belief_impact(
        root_ids,
        initial_status=NodeStatus.INVALID,
    )

    reverse = graph_reverse.analyze_multi_belief_impact(
        list(reversed(root_ids)),
        initial_status=NodeStatus.INVALID,
    )

    assert set(forward) == set(reverse)

    for node_id in forward:
        assert forward[node_id]["impact"] == reverse[node_id]["impact"]

        assert set(forward[node_id]["affected_by"]) == set(
            reverse[node_id]["affected_by"]
        )

@given(
    dependency_type=st.sampled_from(
        [
            DependencyType.REQUIRES,
            DependencyType.DERIVED_FROM,
            DependencyType.SUPPORTS,
            DependencyType.CONTRADICTS,
            DependencyType.CONTEXT,
        ]
    )
)
@settings(max_examples=20, deadline=None)
def test_generated_dependency_types_follow_direct_impact_rules(
    dependency_type,
):
    """Each dependency type should produce its defined direct impact."""
    graph = BeliefGraph()

    graph.add_node(
        BeliefNode(
            id="ROOT",
            node_type=NodeType.BELIEF,
            content="Changed root",
        )
    )
    graph.add_node(
        BeliefNode(
            id="DEPENDENT",
            node_type=NodeType.CONCLUSION,
            content="Dependent conclusion",
        )
    )

    graph.add_dependency(
        "ROOT",
        "DEPENDENT",
        dependency_type,
    )

    result = graph.analyze_multi_belief_impact(
        ["ROOT"],
        initial_status=NodeStatus.INVALID,
    )

    expected = {
        DependencyType.REQUIRES: NodeStatus.INVALID,
        DependencyType.DERIVED_FROM: NodeStatus.INVALID,
        DependencyType.SUPPORTS: NodeStatus.REQUIRES_REEVALUATION,
        DependencyType.CONTRADICTS: NodeStatus.REQUIRES_REEVALUATION,
        DependencyType.CONTEXT: NodeStatus.UNCERTAIN,
    }

    assert result["DEPENDENT"]["impact"] == expected[dependency_type]

@given(
    initial_status=st.sampled_from(
        [
            NodeStatus.REQUIRES_REEVALUATION,
            NodeStatus.UNCERTAIN,
        ]
    ),
)
@settings(max_examples=10, deadline=None)
def test_soft_impacts_do_not_cascade_invalidation(initial_status):
    """
    Soft initial states should not trigger automatic
    downstream propagation.
    """
    graph = BeliefGraph()

    nodes = [
        BeliefNode(
            id="ROOT",
            node_type=NodeType.BELIEF,
            content="Soft-impact source",
        ),
        BeliefNode(
            id="MIDDLE",
            node_type=NodeType.CONCLUSION,
            content="Intermediate conclusion",
        ),
        BeliefNode(
            id="LEAF",
            node_type=NodeType.PLAN,
            content="Downstream plan",
        ),
    ]

    for node in nodes:
        graph.add_node(node)

    graph.add_dependency(
        "ROOT",
        "MIDDLE",
        DependencyType.REQUIRES,
    )
    graph.add_dependency(
        "MIDDLE",
        "LEAF",
        DependencyType.REQUIRES,
    )

    result = graph.analyze_multi_belief_impact(
        ["ROOT"],
        initial_status=initial_status,
    )

    # Soft initial states are not automatically propagated.
    assert result == {}