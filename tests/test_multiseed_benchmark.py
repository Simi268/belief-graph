from app.benchmark_instances import generate_scenario2_instance
from app.multiseed_benchmark import MultiSeedBenchmarkRunner, SeedResult


def _evaluator(name):
    def evaluate(instance):
        return SeedResult(
            seed=instance.seed,
            instance_id=instance.instance_id,
            strategy=name,
            metrics={
                "task_success": True,
                "stale_actions": len(instance.expected_stale_actions),
                "affected_nodes": len(instance.affected_nodes),
            },
            details={},
        )
    return evaluate


def test_multiseed_runner_uses_same_instances_for_all_strategies():
    runner = MultiSeedBenchmarkRunner({
        "baseline": _evaluator("baseline"),
        "belief_graph": _evaluator("belief_graph"),
    })

    instances = runner.generate_instances(
        [1, 2, 3, 4, 5], generate_scenario2_instance
    )
    results = runner.run(instances)

    assert len(results) == 10

    for instance in instances:
        matching = [
            result for result in results
            if result.instance_id == instance.instance_id
        ]
        assert {result.strategy for result in matching} == {
            "baseline", "belief_graph"
        }


def test_multiseed_runner_is_deterministic():
    runner = MultiSeedBenchmarkRunner({"baseline": _evaluator("baseline")})

    first = runner.run(
        runner.generate_instances([1, 2, 3, 4, 5], generate_scenario2_instance)
    )
    second = runner.run(
        runner.generate_instances([1, 2, 3, 4, 5], generate_scenario2_instance)
    )

    assert first == second


def test_multiseed_runner_aggregates_metrics():
    runner = MultiSeedBenchmarkRunner({"baseline": _evaluator("baseline")})

    instances = runner.generate_instances(
        [1, 2, 3, 4, 5], generate_scenario2_instance
    )
    aggregates = runner.aggregate(runner.run(instances))

    assert len(aggregates) == 1
    assert aggregates[0].strategy == "baseline"
    assert aggregates[0].instances == 5

    stale = next(
        m for m in aggregates[0].metrics if m.metric == "stale_actions"
    )
    assert stale.mean == 3.0
    assert stale.population_std == 0.0


def test_multiseed_runner_rejects_duplicate_seeds():
    runner = MultiSeedBenchmarkRunner({"baseline": _evaluator("baseline")})

    try:
        runner.generate_instances([1, 1], generate_scenario2_instance)
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("Duplicate seeds should be rejected.")
