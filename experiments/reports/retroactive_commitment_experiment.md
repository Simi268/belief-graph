# Retroactive Commitment Reconciliation: Final Go/No-Go Experiment

## Question

Can BeliefGraph use its existing belief/dependency and commitment components to handle a correction that arrives **after an agent has already completed external actions**, while preserving unrelated commitments and avoiding unsafe compensation?

This is a deterministic component-level experiment, not a production benchmark and not a claim of research novelty.

## Scenario

An order workflow completed under the belief that a customer was eligible. Later, an authoritative correction establishes that the customer was not eligible. The simulated external system already contains these effects:

- A refund that is known to be compensable.
- A customer notice that cannot be retracted.
- An external audit effect whose reversibility is unknown.
- An unrelated shipment reservation that remains valid.

The expected safe outcome is to cancel and verify the refund, route the irreversible and unknown effects to human review, and leave the shipment reservation untouched.

## Strategies

1. **Dependency-only:** recompute the affected semantic nodes but do not track or reconcile already-completed external commitments.
2. **Full restart:** recompute every registered semantic conclusion/plan and use the same commitment policy as BeliefGraph.
3. **BeliefGraph selective:** recompute only the affected semantic conclusions/plans and use the existing commitment resolver, impact analyzer, and reconciler.

The full-restart strategy uses the same commitment policy as BeliefGraph. This avoids making the safety baseline artificially weak. Dependency-only is deliberately a limited baseline without commitment tracking; it is not a reproduction of REVISE, DART, or another published system.

## Results

| Metric | Dependency-only | Full restart | BeliefGraph selective |
|---|---:|---:|---:|
| Semantic nodes recomputed | 2 | 4 | 2 |
| Commitment-registry record visits, including duplicate-processing check | 0 | 16 | 16 |
| Refund canceled and verified against simulated external state | No | Yes | Yes |
| Irreversible notice routed to review | No | Yes | Yes |
| Unknown-reversibility effect routed to review | No | Yes | Yes |
| Unrelated shipment preserved | Yes | Yes | Yes |
| Duplicate compensation prevented | No commitment mechanism | Yes | Yes |
| Scenario safety checks | Fail | Pass | Pass |

BeliefGraph selective recomputation processes **2 of 4 semantic nodes**, a **50% reduction in semantic-node evaluations** relative to the full-restart baseline in this specific graph. Both commitment-aware strategies scan the full commitment registry during resolution and analysis, so the experiment does **not** show a reduction in commitment-registry scan work.

The dependency-only baseline identifies the affected reasoning path but leaves the completed refund unhandled and does not flag the irreversible/unknown effects. This demonstrates why dependency invalidation alone is insufficient for the particular simulated scenario; it does not establish that published recovery systems lack commitment handling.

## Checks covered

- An old belief is corrected after its dependent actions have completed.
- The correction propagates through downstream reasoning nodes to associated commitments.
- An unrelated commitment remains active and its external state is unchanged.
- An approved compensable effect is changed and verified against simulated external state.
- Irreversible and unknown-reversibility effects are routed to review, not automatically compensated.
- Repeating impact analysis and reconciliation does not execute the same refund compensation twice.
- Semantic evaluators update the affected branch while preserving correct values in the unaffected branch.

## Implementation limitations exposed

- The experiment orchestrates existing graph and commitment components directly. `RecoveryEngine` does not currently expose a dedicated public entry point for retroactive correction after successful completion.
- The commitment registry is in-memory; persistence across process restarts is not established by this experiment.
- The reconciler trusts the compensation callback's verification evidence. The simulated adapter independently checks the external state, but a production adapter must do this too.
- The registry is scanned in full during impact resolution and analysis; selective semantic recomputation does not currently reduce that scan cost.
- The experiment has not been run against REVISE or DART implementations and is not a head-to-head comparison against published work.

## Go/no-go verdict

**Technical feasibility: PASS for this deterministic scenario.** The existing components can be composed to route affected commitments, compensate a known compensable effect, require review for unsafe effects, preserve an unrelated effect, and avoid duplicate compensation.

**Differentiation against existing approaches: NOT ESTABLISHED.** The experiment demonstrates a result against a deliberately limited dependency-only baseline and a full-restart baseline. It does not establish superiority over prior systems that already address dependency-aware recovery and committed effects.

Under the project's strict condition—continue only if a specific problem is shown to be better addressed than existing approaches—this is **not yet a go**. Do not add production features based on this result alone. The responsible next choice is to either perform a direct capability-level comparison against the relevant published systems or pivot to a problem that can be shown to be distinct.

## Prior work reviewed

- Qi et al., [REVISE: Validity-Guided Recovery for Online Revisions in Agent Workflows](https://arxiv.org/abs/2609.00643), 2026.
- Yang et al., [DART: Semantic Recoverability for Structured Tool Agents](https://arxiv.org/abs/2605.23311), 2026.
- [Corollary — belief-based agent runtime](https://github.com/gabe-santana/corollary).
- [UndoBench — recovery capability and side-effect safety benchmark](https://github.com/tradertanmay/undobench).

This short review is not an exhaustive literature survey or a claim that these systems are identical.
