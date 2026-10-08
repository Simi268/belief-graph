from app.benchmark_instances import generate_scenario2_instance
from app.experiment import ExperimentRunner
from app.seeded_strategy_adapters import seeded_strategy_evaluators


def test_experiment_runs_all_strategies_on_same_instances():
    runner = ExperimentRunner(seeded_strategy_evaluators())

    report = runner.run(
        seeds=[1, 2, 3, 4, 5],
        generator=generate_scenario2_instance,
    )

    assert report.seeds == (1, 2, 3, 4, 5)

    assert len(report.results) == 15
    assert len(report.aggregates) == 3

    for seed in report.seeds:
        seed_results = [
            result
            for result in report.results
            if result.seed == seed
        ]

        assert len(seed_results) == 3

        instance_ids = {
            result.instance_id
            for result in seed_results
        }

        assert len(instance_ids) == 1


def test_experiment_produces_expected_strategy_aggregates():
    runner = ExperimentRunner(seeded_strategy_evaluators())

    report = runner.run(
        seeds=[1, 2, 3, 4, 5],
        generator=generate_scenario2_instance,
    )

    aggregates = {
        aggregate.strategy: aggregate
        for aggregate in report.aggregates
    }

    assert set(aggregates) == {
        "baseline",
        "memory",
        "belief_graph",
    }

    assert all(
        aggregate.instances == 5
        for aggregate in aggregates.values()
    )

    belief_graph_metrics = {
        metric.metric: metric
        for metric in aggregates["belief_graph"].metrics
    }

    assert belief_graph_metrics["task_success"].mean == 1.0
    assert belief_graph_metrics["preservation_ratio"].mean == 0.5
    assert belief_graph_metrics["preservation_ratio"].population_std == 0.0


def test_experiment_report_can_be_serialized():
    runner = ExperimentRunner(seeded_strategy_evaluators())

    report = runner.run(
        seeds=[1, 2],
        generator=generate_scenario2_instance,
    )

    serialized = runner.report_to_dict(report)

    assert serialized["seeds"] == [1, 2]
    assert len(serialized["results"]) == 6
    assert len(serialized["aggregates"]) == 3