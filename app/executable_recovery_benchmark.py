"""Executable, deterministic benchmark for dependency-aware recovery.

Unlike the abstract seeded benchmark, every derived node here has a real
Python computation. The benchmark compares:
- baseline: update the changed belief but leave derived values stale;
- full_recompute: recompute every derived node in topological order;
- belief_graph: recompute only descendants of the changed belief.

This is a controlled correctness/cost experiment, not an end-to-end LLM-agent
benchmark. It uses only the Python standard library.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Callable, Any


ComputeFn = Callable[[dict[str, float]], float]


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    dependencies: tuple[str, ...] = ()
    compute: ComputeFn | None = None

    @property
    def is_belief(self) -> bool:
        return self.compute is None


@dataclass
class ExecutableGraph:
    specs: dict[str, NodeSpec]
    values: dict[str, float]
    dependents: dict[str, set[str]]

    @classmethod
    def create(cls, belief_values: dict[str, float]) -> "ExecutableGraph":
        specs = {
            "price": NodeSpec("price"),
            "quantity": NodeSpec("quantity"),
            "tax_rate": NodeSpec("tax_rate"),
            "discount": NodeSpec("discount"),
            "shipping_rate": NodeSpec("shipping_rate"),
            "service_fee": NodeSpec("service_fee"),
            "spare_belief": NodeSpec("spare_belief"),
            "subtotal": NodeSpec(
                "subtotal", ("price", "quantity"),
                lambda v: v["price"] * v["quantity"],
            ),
            "tax": NodeSpec(
                "tax", ("subtotal", "tax_rate"),
                lambda v: v["subtotal"] * v["tax_rate"],
            ),
            "shipping": NodeSpec(
                "shipping", ("quantity", "shipping_rate"),
                lambda v: v["quantity"] * v["shipping_rate"],
            ),
            "service_cost": NodeSpec(
                "service_cost", ("service_fee", "quantity"),
                lambda v: v["service_fee"] * v["quantity"],
            ),
            "total": NodeSpec(
                "total", ("subtotal", "tax", "shipping", "service_cost"),
                lambda v: v["subtotal"] + v["tax"] + v["shipping"] + v["service_cost"],
            ),
            "discounted_total": NodeSpec(
                "discounted_total", ("total", "discount"),
                lambda v: max(0.0, v["total"] - v["discount"]),
            ),
            "spare_metric": NodeSpec(
                "spare_metric", ("spare_belief",),
                lambda v: v["spare_belief"] * 3.0,
            ),
        }
        missing = set(specs) - set(belief_values) - {
            node_id for node_id, spec in specs.items() if not spec.is_belief
        }
        if missing:
            raise ValueError(f"Missing initial belief values: {sorted(missing)}")

        dependents: dict[str, set[str]] = defaultdict(set)
        for node_id, spec in specs.items():
            for dependency in spec.dependencies:
                if dependency not in specs:
                    raise ValueError(
                        f"Node {node_id!r} depends on unknown node {dependency!r}"
                    )
                dependents[dependency].add(node_id)

        graph = cls(
            specs=specs,
            values={key: float(value) for key, value in belief_values.items()},
            dependents=dict(dependents),
        )
        graph.recompute_all()
        return graph

    def clone(self) -> "ExecutableGraph":
        return deepcopy(self)

    def topological_order(self, subset: set[str] | None = None) -> list[str]:
        selected = set(self.specs) if subset is None else set(subset)
        indegree = {
            node_id: sum(
                dependency in selected
                for dependency in self.specs[node_id].dependencies
            )
            for node_id in selected
        }
        queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
        ordered: list[str] = []
        while queue:
            node_id = queue.popleft()
            ordered.append(node_id)
            for child in sorted(self.dependents.get(node_id, set()) & selected):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if len(ordered) != len(selected):
            raise ValueError("Dependency graph contains a cycle.")
        return ordered

    def descendants(self, node_id: str) -> set[str]:
        if node_id not in self.specs:
            raise ValueError(f"Unknown node: {node_id}")
        found: set[str] = set()
        queue = deque(self.dependents.get(node_id, set()))
        while queue:
            current = queue.popleft()
            if current in found:
                continue
            found.add(current)
            queue.extend(self.dependents.get(current, set()))
        return found

    def recompute_node(self, node_id: str) -> None:
        spec = self.specs[node_id]
        if spec.compute is None:
            raise ValueError(f"Belief/input node {node_id!r} cannot be recomputed.")
        self.values[node_id] = float(spec.compute(self.values))

    def recompute_nodes(self, node_ids: set[str]) -> list[str]:
        ordered = [
            node_id
            for node_id in self.topological_order(node_ids)
            if not self.specs[node_id].is_belief
        ]
        for node_id in ordered:
            self.recompute_node(node_id)
        return ordered

    def recompute_all(self) -> list[str]:
        derived = {
            node_id for node_id, spec in self.specs.items()
            if not spec.is_belief
        }
        return self.recompute_nodes(derived)


BELIEF_BASE_VALUES: dict[str, float] = {
    "price": 25.0,
    "quantity": 3.0,
    "tax_rate": 0.08,
    "discount": 4.0,
    "shipping_rate": 2.5,
    "service_fee": 1.25,
    "spare_belief": 7.0,
}

SCENARIO_CHANGED_BELIEFS: dict[str, str] = {
    "price_change": "price",
    "quantity_change": "quantity",
    "tax_rate_change": "tax_rate",
    "discount_change": "discount",
    "shipping_rate_change": "shipping_rate",
    "service_fee_change": "service_fee",
    "disconnected_belief_change": "spare_belief",
}


def _changed_value(old_value: float, seed: int) -> float:
    """Produce a deterministic, non-zero change for each seed."""
    return old_value + (seed * 0.75) + 1.0


def _new_graph(seed: int) -> ExecutableGraph:
    values = dict(BELIEF_BASE_VALUES)
    # Vary inputs by seed without using randomness, so results are reproducible.
    values["price"] += seed * 0.2
    values["quantity"] += (seed % 3) * 0.1
    values["tax_rate"] += seed * 0.001
    return ExecutableGraph.create(values)


def _run_one(
    scenario: str,
    seed: int,
    strategy: str,
) -> dict[str, Any]:
    changed_belief = SCENARIO_CHANGED_BELIEFS[scenario]
    initial = _new_graph(seed)
    changed_value = _changed_value(initial.values[changed_belief], seed)

    # The oracle starts from the same pre-change state and recomputes every
    # derived value after applying the changed belief.
    oracle = initial.clone()
    oracle.values[changed_belief] = changed_value
    oracle.recompute_all()

    graph = initial.clone()
    graph.values[changed_belief] = changed_value

    if strategy == "baseline":
        recomputed: list[str] = []
        mode = "no_recovery"
    elif strategy == "full_recompute":
        recomputed = graph.recompute_all()
        mode = "actual_full_recomputation"
    elif strategy == "belief_graph":
        affected = graph.descendants(changed_belief)
        recomputed = graph.recompute_nodes(affected)
        mode = "actual_selective_recomputation"
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    mismatches = {
        node_id: {
            "actual": graph.values.get(node_id),
            "expected": expected_value,
        }
        for node_id, expected_value in oracle.values.items()
        if graph.values.get(node_id) != expected_value
    }
    changed_descendants = initial.descendants(changed_belief)
    preserved_derived_nodes = {
        node_id
        for node_id, spec in initial.specs.items()
        if not spec.is_belief and node_id not in changed_descendants
    }
    preserved_unchanged = all(
        graph.values[node_id] == initial.values[node_id]
        for node_id in preserved_derived_nodes
    )
    expected_recompute_set = {
        node_id for node_id in changed_descendants
        if not initial.specs[node_id].is_belief
    }
    unnecessary_recomputed = set(recomputed) - expected_recompute_set

    return {
        "scenario": scenario,
        "seed": seed,
        "instance_id": f"{scenario}_S{seed:04d}",
        "strategy": strategy,
        "changed_belief": changed_belief,
        "changed_value": changed_value,
        "recovery_mode": mode,
        "metrics": {
            "output_correct": len(mismatches) == 0,
            "mismatched_node_count": len(mismatches),
            "recomputed_node_count": len(recomputed),
            "expected_affected_derived_node_count": len(expected_recompute_set),
            "preserved_derived_node_count": len(preserved_derived_nodes),
            "preserved_derived_values_unchanged": preserved_unchanged,
            "unnecessary_recomputation": len(unnecessary_recomputed),
            "recovery_success": len(mismatches) == 0 and preserved_unchanged,
        },
        "details": {
            "recomputed_nodes": recomputed,
            "expected_affected_derived_nodes": sorted(expected_recompute_set),
            "preserved_derived_nodes": sorted(preserved_derived_nodes),
            "mismatches": mismatches,
            "final_values": dict(sorted(graph.values.items())),
            "oracle_values": dict(sorted(oracle.values.items())),
        },
    }


def run_experiment(
    scenarios: list[str] | None = None,
    seeds: list[int] | None = None,
) -> list[dict[str, Any]]:
    selected_scenarios = (
        list(SCENARIO_CHANGED_BELIEFS) if scenarios is None else list(scenarios)
    )
    selected_seeds = [1, 2, 3, 4, 5] if seeds is None else list(seeds)
    unknown = set(selected_scenarios) - set(SCENARIO_CHANGED_BELIEFS)
    if unknown:
        raise ValueError(f"Unknown scenarios: {sorted(unknown)}")
    if not selected_scenarios or not selected_seeds:
        raise ValueError("At least one scenario and one seed are required.")

    measurements: list[dict[str, Any]] = []
    for scenario in selected_scenarios:
        for seed in selected_seeds:
            for strategy in ("baseline", "full_recompute", "belief_graph"):
                measurements.append(_run_one(scenario, seed, strategy))
    return measurements


def summarize(measurements: list[dict[str, Any]]) -> dict[str, Any]:
    strategies = sorted({item["strategy"] for item in measurements})
    summary: dict[str, Any] = {}
    metric_names = sorted({
        metric for item in measurements for metric in item["metrics"]
    })
    for strategy in strategies:
        rows = [item for item in measurements if item["strategy"] == strategy]
        metric_summary: dict[str, Any] = {}
        for metric_name in metric_names:
            values = [row["metrics"][metric_name] for row in rows]
            if values and all(isinstance(value, bool) for value in values):
                metric_summary[metric_name] = {
                    "true_count": sum(values),
                    "false_count": len(values) - sum(values),
                    "rate": sum(values) / len(values),
                }
            else:
                numbers = [
                    float(value) for value in values
                    if isinstance(value, (int, float)) and not isinstance(value, bool)
                ]
                if numbers:
                    metric_summary[metric_name] = {
                        "mean": mean(numbers),
                        "median": median(numbers),
                        "min": min(numbers),
                        "max": max(numbers),
                    }
        summary[strategy] = {
            "evaluations": len(rows),
            "metrics": metric_summary,
        }
    return summary


def export_json(
    measurements: list[dict[str, Any]],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    scenarios = sorted({item["scenario"] for item in measurements})
    seeds = sorted({item["seed"] for item in measurements})
    strategies = sorted({item["strategy"] for item in measurements})
    payload = {
        "experiment": "belief_graph_executable_recovery_comparison",
        "measurement_count": len(measurements),
        "design": {
            "scenario_count": len(scenarios),
            "seed_count": len(seeds),
            "strategy_count": len(strategies),
            "expected_measurements": len(scenarios) * len(seeds) * len(strategies),
        },
        "scenarios": scenarios,
        "seeds": seeds,
        "strategies": strategies,
        "interpretation": (
            "Derived nodes execute deterministic Python functions. Full recomputation "
            "is the correctness oracle. BeliefGraph recomputes only graph descendants "
            "of the changed belief. Baseline intentionally leaves derived values stale. "
            "This is a controlled executable DAG benchmark, not an end-to-end agent test."
        ),
        "summary_by_strategy": summarize(measurements),
        "results": measurements,
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return path


def main() -> None:
    measurements = run_experiment()
    output = export_json(
        measurements,
        "experiments/results/executable_recovery_comparison.json",
    )
    print(f"Measurements: {len(measurements)}")
    print(f"Scenarios: {len(SCENARIO_CHANGED_BELIEFS)}")
    print(f"Seeds: {len({item['seed'] for item in measurements})}")
    print("Summary by strategy:")
    print(json.dumps(summarize(measurements), indent=2))
    print(f"JSON exported to: {output}")


if __name__ == "__main__":
    main()
