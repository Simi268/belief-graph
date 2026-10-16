import networkx as nx

from app.controlled_benchmark import SCENARIOS, build_graph


def test_controlled_benchmark_has_three_graph_structures():
    assert set(SCENARIOS.keys()) == {
        "linear",
        "multi_branch",
        "shared_dependency",
        "deep_chain",
        "diamond_dependency",
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
        changed_node = scenario["changed_node"]

        reachable = {changed_node} | nx.descendants(
            graph.graph, changed_node
        )

        assert reachable == set(scenario["expected_affected"]), (
            f"{name}: expected affected nodes do not match "
            "graph reachability"
        )