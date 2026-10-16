from app.benchmark import BenchmarkRunner
from app.unified_benchmark import _strategy_evidence


def test_scenario1_baselines_are_marked_as_executed_simulations():
    runner = BenchmarkRunner()

    for result in [runner.run_baseline(), runner.run_memory_agent()]:
        provenance, note = _strategy_evidence(result, "scenario1")

        assert provenance == "executed_simulation"
        assert "simulated API" in note


def test_other_baselines_remain_modelled():
    runner = BenchmarkRunner()

    result = runner.run_scenario2_all()

    for item in result:
        if item.strategy.lower() in {"baseline", "memory"}:
            provenance, _ = _strategy_evidence(item, "scenario2")
            assert provenance == "modelled_baseline"