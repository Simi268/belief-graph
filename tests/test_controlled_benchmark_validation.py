import networkx as nx

from app.controlled_benchmark import SCENARIOS, build_graph


def test_controlled_benchmark_has_six_graph_structures():
    assert set(SCENARIOS.keys()) == {
        "linear",
        "multi_branch",
        "shared_dependency",
        "deep_chain",
        "diamond_dependency",
        "multi_belief_change",
    }


def test_scenario_ground_truth_covers_all_nodes():
    for name, scenario in SCENARIOS.items():
        affected = set(scenario["expected_affected"])
        preserved = set(scenario["expected_preserved"])
        all_nodes = set(scenario["nodes"])

        assert affected.isdisjoint(preserved), (
            f"{name}: affected and preserved nodes overlap"
        )

        assert affected | preserved == all_nodes, (
            f"{name}: ground truth does not cover every node"
        )


def test_expected_affected_nodes_match_graph_reachability():
    for name, scenario in SCENARIOS.items():
        graph = build_graph(scenario)

        changed_nodes = scenario.get(
            "changed_nodes",
            [scenario["changed_node"]],
        )

        reachable = set(changed_nodes)

        for changed_node in changed_nodes:
            reachable.update(
                nx.descendants(graph.graph, changed_node)
            )

        assert reachable == set(scenario["expected_affected"]), (
            f"{name}: expected affected nodes do not match "
            "graph reachability"
        )


def test_multi_belief_scenario_has_two_changed_roots():
    scenario = SCENARIOS["multi_belief_change"]

    assert set(scenario["changed_nodes"]) == {"B1", "B2"}


def test_multi_belief_scenario_preserves_independent_branch():
    scenario = SCENARIOS["multi_belief_change"]

    assert scenario["expected_preserved"] == {"B3", "C3"}


def test_multi_belief_scenario_has_shared_downstream_nodes():
    scenario = SCENARIOS["multi_belief_change"]
    graph = build_graph(scenario)

    assert set(graph.graph.predecessors("P1")) == {"C1", "C2"}
    assert set(graph.graph.predecessors("A1")) == {"P1"}