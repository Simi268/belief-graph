from app.benchmark import BenchmarkRunner

def test_scenario2_baseline_is_non_recovering():
    result = BenchmarkRunner().run_scenario2_baseline()
    assert result.task_success is False
    assert result.recovery_success is False
    assert result.stale_actions == 3
    assert result.stale_plans == 3
    assert result.invalid_plans == 0
    assert result.tool_calls == 0
    assert result.details["dependency_tracking"] is False

def test_scenario2_memory_uses_full_restart():
    result = BenchmarkRunner().run_scenario2_memory()
    assert result.task_success is True
    assert result.recovery_success is True
    assert result.stale_actions == 0
    assert result.invalid_plans == 0
    assert result.stale_plans == 0
    assert result.recomputed_node_count == 12
    assert result.unnecessary_recomputation == 6
    assert result.recovery_steps == 2
    assert result.tool_calls == 3
    assert result.details["recovery_policy"] == "full_restart"
    assert result.details["preserved_nodes"] == []
    assert result.unnecessary_invalidation == 0

def test_scenario2_belief_graph_is_selective():
    result = BenchmarkRunner().run_scenario2_belief_graph()
    assert result.task_success is True
    assert result.recovery_success is True
    assert result.invalid_plans == 1
    assert result.details["affected_node_count"] == 6
    assert result.details["preserved_node_count"] == 6
    assert result.details["preservation_ratio"] == 0.5
    assert result.propagation_depth == 3

def test_scenario2_strategies_share_the_same_scenario():
    runner = BenchmarkRunner()
    results = runner.run_scenario2_all()
    assert len(results) == 3
    assert {r.scenario_id for r in results} == {"multi_branch_belief_revision_v1"}
    assert {r.strategy for r in results} == {"baseline", "memory", "belief_graph"}

def test_belief_graph_preserves_unrelated_branch():
    result = BenchmarkRunner().run_scenario2_belief_graph()
    preserved = set(result.details["preserved_nodes"])
    assert {"B4", "C4", "P4", "A4"}.issubset(preserved)
    assert result.unnecessary_invalidation == 0
