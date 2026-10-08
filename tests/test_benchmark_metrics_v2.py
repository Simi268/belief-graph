from app.benchmark import BenchmarkRunner

def test_scenario2_baseline_reports_stale_not_invalidated_plans():
    result = BenchmarkRunner().run_scenario2_baseline()
    assert result.task_success is False
    assert result.recovery_success is False
    assert result.stale_actions == 3
    assert result.stale_plans == 3
    assert result.invalid_plans == 0
    assert result.invalidated_node_count == 0
    assert result.recomputed_node_count == 0
    assert result.preserved_node_count == 6

def test_scenario2_memory_reports_full_restart_separately():
    result = BenchmarkRunner().run_scenario2_memory()
    assert result.task_success is True
    assert result.recovery_success is True
    assert result.stale_actions == 0
    assert result.stale_plans == 0
    assert result.invalid_plans == 0
    assert result.invalidated_node_count == 0
    assert result.recomputed_node_count == 12
    assert result.unnecessary_recomputation == 6
    assert result.preserved_node_count == 0
    assert result.preservation_ratio == 0.0
    assert result.details["recovery_policy"] == "full_restart"
    assert result.details["recomputed_plan_count"] == 4

def test_scenario2_belief_graph_reports_selective_revision():
    result = BenchmarkRunner().run_scenario2_belief_graph()
    assert result.task_success is True
    assert result.recovery_success is True
    assert result.stale_plans == 0
    assert result.invalid_plans == 1
    assert result.invalidated_node_count == 4
    assert result.recomputed_node_count == 0
    assert result.unnecessary_recomputation == 0
    assert result.preserved_node_count == 6
    assert result.preservation_ratio == 0.5
    assert result.propagation_depth == 3

def test_scenario2_strategies_share_the_same_scenario():
    results = BenchmarkRunner().run_scenario2_all()
    assert len(results) == 3
    assert {r.scenario_id for r in results} == {"multi_branch_belief_revision_v1"}
    assert {r.strategy for r in results} == {"baseline", "memory", "belief_graph"}

def test_scenario2_memory_and_belief_graph_have_comparable_selectivity_metrics():
    baseline, memory, belief_graph = BenchmarkRunner().run_scenario2_all()
    assert memory.recomputed_node_count == 12
    assert memory.unnecessary_recomputation == 6
    assert belief_graph.recomputed_node_count == 0
    assert belief_graph.unnecessary_recomputation == 0
    assert belief_graph.preserved_node_count > memory.preserved_node_count
