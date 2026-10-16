# Belief-Graph Unified Benchmark Report

- Started (UTC): 2026-10-15T16:06:07.135107+00:00
- Finished (UTC): 2026-10-15T16:06:07.170886+00:00
- Requested runs per scenario: 5
- Scenarios registered: 7
- Result rows: 105
- Failed scenario runs: 0

## Results by scenario and strategy

| Scenario | Strategy | Provenance | Runs | Task success (mean) | Recovery success (mean) | Stale actions (mean) | Recomputed nodes (mean) | Unnecessary recomputation (mean) | Preservation ratio (mean) | Time ms (mean) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| API version change | baseline | executed_simulation | 5 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.738 |
| API version change | belief_graph | executed_recovery_path | 5 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.429 | 0.738 |
| API version change | memory | executed_simulation | 5 | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.738 |
| Multi-branch belief revision | baseline | modelled_baseline | 5 | 0.000 | 0.000 | 3.000 | 0.000 | 0.000 | 0.500 | 0.248 |
| Multi-branch belief revision | belief_graph | scenario_execution | 5 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.500 | 0.248 |
| Multi-branch belief revision | memory | modelled_baseline | 5 | 1.000 | 1.000 | 0.000 | 12.000 | 6.000 | 0.000 | 0.248 |
| Database schema change | baseline | modelled_baseline | 5 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.667 | 0.293 |
| Database schema change | belief_graph | executed_component | 5 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.667 | 0.293 |
| Database schema change | memory | modelled_baseline | 5 | 1.000 | 1.000 | 0.000 | 12.000 | 8.000 | 0.000 | 0.293 |
| Policy change | baseline | modelled_baseline | 5 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.667 | 0.235 |
| Policy change | belief_graph | executed_component | 5 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.667 | 0.235 |
| Policy change | memory | modelled_baseline | 5 | 1.000 | 1.000 | 0.000 | 12.000 | 8.000 | 0.000 | 0.235 |
| Tool unavailable | baseline | modelled_baseline | 5 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.500 | 0.259 |
| Tool unavailable | belief_graph | scenario_execution | 5 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.500 | 0.259 |
| Tool unavailable | memory | modelled_baseline | 5 | 1.000 | 1.000 | 0.000 | 8.000 | 4.000 | 0.000 | 0.259 |
| Stale information | baseline | modelled_baseline | 5 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.500 | 0.215 |
| Stale information | belief_graph | executed_component | 5 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.500 | 0.215 |
| Stale information | memory | modelled_baseline | 5 | 1.000 | 1.000 | 0.000 | 8.000 | 4.000 | 0.000 | 0.215 |
| Simultaneous multiple failures | baseline | modelled_baseline | 5 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.286 | 1.117 |
| Simultaneous multiple failures | belief_graph | scenario_execution | 5 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.286 | 1.117 |
| Simultaneous multiple failures | memory | modelled_baseline | 5 | 1.000 | 1.000 | 0.000 | 14.000 | 4.000 | 0.000 | 1.117 |

## Interpretation cautions

- `modelled_baseline` means the legacy benchmark method constructs a result from assumptions/ground truth rather than executing an independent agent. Do not treat it as measured agent performance.
- `executed_component` means Belief-Graph's impact-analysis component ran; this is not necessarily a full LLM-agent comparison.
- `elapsed_ms` is local Python benchmark-method wall time and is not production latency.
- `tool_calls` and `recovery_steps` measure different things: tool calls count API/tool attempts, while recovery steps count internal recovery stages as encoded by each legacy scenario method.
- `recovery_steps` is not yet normalized to the same event granularity across every strategy/scenario. Do not use it alone to claim lower recovery cost; inspect the scenario implementation and provenance first.
- Repeated deterministic runs are reproducibility checks, not independent statistical trials.
- A task-success mean is the fraction of returned runs marked successful; ground-truth checks are only as strong as the scenario's current assertions.
