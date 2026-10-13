from app.benchmark import BenchmarkRunner
from app.scenario2 import MultiBranchBeliefRevisionScenario


def test_scenario2_reports_actual_graph_operation_metrics():
    result = MultiBranchBeliefRevisionScenario().run()
    assert result.operation_metrics == {
        "nodes_visited": 4,
        "dependency_edges_examined": 5,
        "impact_classifications_computed": 5,
    }


def test_scenario2_benchmark_exposes_metrics_without_changing_legacy_counts():
    result = BenchmarkRunner().run_scenario2_belief_graph()
    assert result.details["graph_operation_metrics"] == {
        "nodes_visited": 4,
        "dependency_edges_examined": 5,
        "impact_classifications_computed": 5,
    }
    assert result.recomputed_node_count == 0
    assert result.recovery_steps == 1
    assert result.tool_calls == 0
