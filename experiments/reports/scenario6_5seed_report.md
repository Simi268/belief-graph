# Belief-Graph Experiment Report

> Controlled evaluation of dependency-aware belief revision and selective recovery.

## 1. Objective

### Experiment objective

Evaluate whether dependency-aware belief revision can recover from changed beliefs while preserving unaffected reasoning state.

The experiment compares different recovery strategies under controlled belief changes and evaluates whether the system can identify affected reasoning state instead of recomputing everything.

## 2. Experimental Setup

- **Seeds:** 1, 2, 3, 4, 5
- **Strategy runs:** 15
- **Strategies:** baseline, memory, belief_graph
- **Scenario:** Multi-branch belief revision
- **Evaluation:** Dependency-aware impact analysis against explicit ground truth

### Strategy comparison

Strategy comparison

| Strategy | Description |
|---|---|
| baseline | Agent without dependency-aware belief revision |
| memory | Conventional memory strategy using full recomputation |
| belief_graph | Dependency-aware impact analysis with selective revision |

## 3. Key Results

| Metric | baseline | memory | belief_graph |
|---|---:|---:|---:|
| Task success | 0.0% | 100.0% | 100.0% |
| Recovery success | 0.0% | 100.0% | 100.0% |
| Preservation ratio | 0.0% | 0.0% | 66.7% |
| Affected nodes | 0 | 13 | 4 |
| Invalidated nodes | 0 | 0 | 4 |
| Recomputed nodes | 0 | 13 | 0 |
| Unnecessary recomputation | 0 | 9 | 0 |
| Propagation depth | 0 | 0 | 3 |

## 4. Interpretation

In this controlled benchmark, the baseline strategy does not successfully recover from the changed belief and leaves stale downstream state.

The conventional memory strategy successfully recovers, but it recomputes the complete original reasoning state rather than identifying only the affected dependency region.

The Belief-Graph strategy successfully performs dependency-aware impact analysis and selective revision. It preserves 66.7% of the original reasoning state. The affected region contains 4 nodes. 4 nodes are explicitly invalidated. Unnecessary recomputation is 0 nodes.

These results demonstrate the intended selective revision behavior within the controlled benchmark. They should not be interpreted as universal performance or superiority claims.

## 5. Dependency Revision Example

The benchmark models a shared belief with three different dependency relationships:

```text
                 B1
                 │
                 C1
          ┌──────┼──────┐
          │      │      │
       REQUIRES SUPPORTS CONTEXT
          │      │      │
         P1     P2     P3
          │      │      │
         A1     A2     A3

                 B4
                  │
                 C4
                  │
                 P4
                  │
                 A4
```

When B1 becomes invalid, the system does not blindly invalidate every downstream node. Instead, dependency types determine whether a node becomes invalid, requires reevaluation, or becomes uncertain.

This is the core mechanism behind selective recovery.

## 6. Limitations

- The experiment uses a controlled benchmark scenario.
- The reported experiment uses five deterministic seeds.
- The benchmark does not establish universal architecture or performance claims.
- Runtime, token usage, and tool-call measurements depend on the benchmark implementation.
- Additional scenarios and larger workloads are required for broader validation.

## Reproducibility

The reported values are generated from the exported experiment JSON artifact.

The experiment uses deterministic seeded benchmark instances, allowing the same seeds to reproduce the benchmark inputs.

Example:

```text
python run_experiment.py
```

## 8. Raw Metrics

| Strategy | Metric | Mean | Population Std. Dev. |
|---|---|---:|---:|
| baseline | affected_node_count | 0.0000 | 0.0000 |
| baseline | invalid_plans | 0.0000 | 0.0000 |
| baseline | invalidated_node_count | 0.0000 | 0.0000 |
| baseline | preservation_ratio | 0.0000 | 0.0000 |
| baseline | preserved_node_count | 0.0000 | 0.0000 |
| baseline | propagation_depth | 0.0000 | 0.0000 |
| baseline | recomputed_node_count | 0.0000 | 0.0000 |
| baseline | recovery_steps | 0.0000 | 0.0000 |
| baseline | recovery_success | 0.0000 | 0.0000 |
| baseline | stale_actions | 1.0000 | 0.0000 |
| baseline | stale_plans | 1.0000 | 0.0000 |
| baseline | task_success | 0.0000 | 0.0000 |
| baseline | tool_calls | 0.0000 | 0.0000 |
| baseline | unnecessary_invalidation | 0.0000 | 0.0000 |
| baseline | unnecessary_recomputation | 0.0000 | 0.0000 |
| memory | affected_node_count | 12.8000 | 2.9933 |
| memory | invalid_plans | 0.0000 | 0.0000 |
| memory | invalidated_node_count | 0.0000 | 0.0000 |
| memory | preservation_ratio | 0.0000 | 0.0000 |
| memory | preserved_node_count | 0.0000 | 0.0000 |
| memory | propagation_depth | 0.0000 | 0.0000 |
| memory | recomputed_node_count | 12.8000 | 2.9933 |
| memory | recovery_steps | 2.0000 | 0.0000 |
| memory | recovery_success | 1.0000 | 0.0000 |
| memory | stale_actions | 0.0000 | 0.0000 |
| memory | stale_plans | 0.0000 | 0.0000 |
| memory | task_success | 1.0000 | 0.0000 |
| memory | tool_calls | 3.0000 | 0.0000 |
| memory | unnecessary_invalidation | 0.0000 | 0.0000 |
| memory | unnecessary_recomputation | 8.8000 | 2.9933 |
| belief_graph | affected_node_count | 4.0000 | 0.0000 |
| belief_graph | invalid_plans | 1.0000 | 0.0000 |
| belief_graph | invalidated_node_count | 4.0000 | 0.0000 |
| belief_graph | preservation_ratio | 0.6667 | 0.0913 |
| belief_graph | preserved_node_count | 8.8000 | 2.9933 |
| belief_graph | propagation_depth | 3.0000 | 0.0000 |
| belief_graph | recomputed_node_count | 0.0000 | 0.0000 |
| belief_graph | recovery_steps | 1.0000 | 0.0000 |
| belief_graph | recovery_success | 1.0000 | 0.0000 |
| belief_graph | stale_actions | 0.0000 | 0.0000 |
| belief_graph | stale_plans | 0.0000 | 0.0000 |
| belief_graph | task_success | 1.0000 | 0.0000 |
| belief_graph | tool_calls | 0.0000 | 0.0000 |
| belief_graph | unnecessary_invalidation | 0.0000 | 0.0000 |
| belief_graph | unnecessary_recomputation | 0.0000 | 0.0000 |
