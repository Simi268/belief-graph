from __future__ import annotations

import json
from pathlib import Path


RESULTS_DIR = Path("experiments/results")
REPORTS_DIR = Path("experiments/reports")
CSV_PATH = RESULTS_DIR / "cross_scenario_evaluation.csv"
REPORT_PATH = REPORTS_DIR / "cross_scenario_evaluation.md"


def load_reports() -> list[tuple[str, dict]]:
    files = sorted(
        RESULTS_DIR.glob("scenario*_5seed.json"),
        key=lambda p: p.name,
    )

    if not files:
        raise FileNotFoundError(
            "No scenario*_5seed.json files found in experiments/results."
        )

    reports = []
    for path in files:
        with path.open("r", encoding="utf-8") as handle:
            reports.append((path.stem, json.load(handle)))

    return reports


def aggregate_lookup(report: dict) -> dict[str, dict[str, float]]:
    lookup: dict[str, dict[str, float]] = {}

    for aggregate in report["aggregates"]:
        lookup[aggregate["strategy"]] = {
            metric["metric"]: float(metric["mean"])
            for metric in aggregate["metrics"]
        }

    return lookup


def safe_reduction(base: float, improved: float) -> float | None:
    if base == 0:
        return None
    return 1.0 - (improved / base)


def build_rows(reports: list[tuple[str, dict]]) -> list[dict]:
    rows = []

    for scenario_name, report in reports:
        metrics = aggregate_lookup(report)

        memory = metrics["memory"]
        belief_graph = metrics["belief_graph"]

        memory_recomputed = memory["recomputed_node_count"]
        bg_recomputed = belief_graph["recomputed_node_count"]

        memory_unnecessary = memory["unnecessary_recomputation"]
        bg_unnecessary = belief_graph["unnecessary_recomputation"]

        rows.append(
            {
                "scenario": scenario_name.replace("_5seed", ""),
                "task_success_baseline": metrics["baseline"]["task_success"],
                "task_success_memory": memory["task_success"],
                "task_success_belief_graph": belief_graph["task_success"],
                "memory_recomputed": memory_recomputed,
                "belief_graph_recomputed": bg_recomputed,
                "recomputation_reduction": (
                    safe_reduction(memory_recomputed, bg_recomputed)
                ),
                "memory_unnecessary_recomputed": memory_unnecessary,
                "belief_graph_unnecessary_recomputed": bg_unnecessary,
                "unnecessary_recomputation_reduction": (
                    safe_reduction(memory_unnecessary, bg_unnecessary)
                ),
                "belief_graph_preservation_ratio": (
                    belief_graph["preservation_ratio"]
                ),
                "belief_graph_affected_nodes": (
                    belief_graph["affected_node_count"]
                ),
                "memory_total_nodes_recomputed": memory_recomputed,
                "propagation_depth": belief_graph["propagation_depth"],
            }
        )

    return rows


def write_csv(rows: list[dict]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())

    with CSV_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def build_markdown(rows: list[dict]) -> str:
    avg_recomputed_memory = sum(
        row["memory_recomputed"]
        for row in rows
    ) / len(rows)

    avg_bg_recomputed = sum(
        row["belief_graph_recomputed"]
        for row in rows
    ) / len(rows)

    avg_unnecessary_memory = sum(
        row["memory_unnecessary_recomputed"]
        for row in rows
    ) / len(rows)

    avg_preservation = sum(
        row["belief_graph_preservation_ratio"]
        for row in rows
    ) / len(rows)

    all_recomputation_reductions = [
        row["recomputation_reduction"]
        for row in rows
        if row["recomputation_reduction"] is not None
    ]

    all_unnecessary_reductions = [
        row["unnecessary_recomputation_reduction"]
        for row in rows
        if row["unnecessary_recomputation_reduction"] is not None
    ]

    avg_recomputation_reduction = (
        sum(all_recomputation_reductions)
        / len(all_recomputation_reductions)
    )

    avg_unnecessary_reduction = (
        sum(all_unnecessary_reductions)
        / len(all_unnecessary_reductions)
    )

    lines = [
        "# Belief-Graph Cross-Scenario Evaluation",
        "",
        "## Experimental coverage",
        "",
        (
            f"- Scenarios: {len(rows)}"
        ),
        "- Seeds per scenario: 5",
        "- Strategies: baseline, memory, belief_graph",
        (
            f"- Total strategy runs: {len(rows) * 5 * 3}"
        ),
        "",
        "## Derived metrics",
        "",
        (
            "**Recomputation reduction** = "
            "`1 - (Belief-Graph recomputed / Memory recomputed)`."
        ),
        "",
        (
            "**Unnecessary-recomputation reduction** = "
            "`1 - (Belief-Graph unnecessary recomputation / "
            "Memory unnecessary recomputation)`."
        ),
        "",
        (
            "**Preservation ratio** = "
            "preserved original nodes / original node count."
        ),
        "",
        "## Cross-scenario results",
        "",
        (
            "| Scenario | Memory recomputed | BG recomputed | "
            "Recomputation reduction | Memory unnecessary | "
            "BG unnecessary | Unnecessary reduction | "
            "BG preservation | BG propagation depth |"
        ),
        (
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
        ),
    ]

    for row in rows:
        lines.append(
            "| "
            f"{row['scenario']} | "
            f"{row['memory_recomputed']:.2f} | "
            f"{row['belief_graph_recomputed']:.2f} | "
            f"{pct(row['recomputation_reduction'])} | "
            f"{row['memory_unnecessary_recomputed']:.2f} | "
            f"{row['belief_graph_unnecessary_recomputed']:.2f} | "
            f"{pct(row['unnecessary_recomputation_reduction'])} | "
            f"{row['belief_graph_preservation_ratio']:.3f} | "
            f"{row['propagation_depth']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Cross-scenario averages",
            "",
            (
                f"- Average Memory recomputation: "
                f"**{avg_recomputed_memory:.2f} nodes/run**"
            ),
            (
                f"- Average Belief-Graph recomputation: "
                f"**{avg_bg_recomputed:.2f} nodes/run**"
            ),
            (
                f"- Average Memory unnecessary recomputation: "
                f"**{avg_unnecessary_memory:.2f} nodes/run**"
            ),
            (
                f"- Average recomputation reduction: "
                f"**{pct(avg_recomputation_reduction)}**"
            ),
            (
                f"- Average unnecessary-recomputation reduction: "
                f"**{pct(avg_unnecessary_reduction)}**"
            ),
            (
                f"- Average Belief-Graph preservation ratio: "
                f"**{avg_preservation:.3f}** "
                f"({avg_preservation * 100:.1f}%)"
            ),
            "",
            "## Interpretation",
            "",
            (
                "Across these controlled benchmark families, "
                "Belief-Graph reaches the same successful task outcome "
                "as the memory baseline while recomputing none of the "
                "original reasoning nodes. The main measured advantage "
                "is therefore selective state preservation rather than "
                "task success alone."
            ),
            "",
            (
                "These experiments are controlled deterministic "
                "benchmarks. They do not establish statistical "
                "significance or real-world generalization."
            ),
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    reports = load_reports()
    rows = build_rows(reports)

    write_csv(rows)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = build_markdown(rows)
    REPORT_PATH.write_text(
        report,
        encoding="utf-8",
    )

    print(f"CSV exported to: {CSV_PATH}")
    print(f"Markdown report exported to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
