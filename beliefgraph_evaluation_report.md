# BeliefGraph Evaluation Report

**Status:** Initial reproducible integration experiment\
**Project:** BeliefGraph --- dependency-aware selective recovery after
changed beliefs

## 1. Objective

Evaluate whether BeliefGraph can recover from a tool/API-version failure
by updating the affected dependency path while preserving an independent
branch. The experiment also demonstrates an LLM-backed agent using the
actual tool failure to select a replacement API version, with that
decision checked against tool evidence.

This is a small-scale integration experiment, not evidence that
BeliefGraph is faster or better than replanning in general.

## 2. Hypothesis

When a tool failure changes a belief that downstream conclusions and
plans depend on, BeliefGraph can identify and recompute affected
semantic nodes while preserving unaffected nodes, rather than rebuilding
the entire graph.

## 3. Experimental scenario

The order-processing agent's cached action uses API version `v1`, while
the tool reports that `v2` is expected.

1.  The agent executes its current action using `v1`.
2.  The tool returns `API_VERSION_MISMATCH`, with `expected: v2` and
    `received: v1`.
3.  The LLM receives the actual failure and proposes retrying
    `create_order` with `v2`.
4.  The example validates the proposed version against tool evidence.
5.  BeliefGraph performs evidence-driven recovery and executes the
    replacement action.
6.  The example checks the replacement result, semantic values, and
    preservation of an independent shipping branch.
7.  A full-restart baseline rebuilds the graph and attempts the order
    action.

## 4. Reported results

### 4.1 End-to-end checks

  -----------------------------------------------------------------------
  Check                               Observed result
  ----------------------------------- -----------------------------------
  Tool failure reproduced             `API_VERSION_MISMATCH` (`v1`
                                      received; `v2` expected)

  LLM recovery decision               Selected `v2`

  LLM decision validated against tool Pass
  evidence                            

  BeliefGraph recovery status         `recovered`

  Replacement action                  Succeeded

  Replacement agrees with tool        Pass
  evidence                            

  Order semantic values correct       Pass

  Independent shipping branch         Pass
  preserved                           

  Full-restart baseline action        Succeeded

  Overall connected workflow          `PASS`
  -----------------------------------------------------------------------

### 4.2 Selective recovery metrics

  Metric                          Reported value
  ----------------------------- ----------------
  Affected node count                          5
  Invalidated node count                       4
  Reevaluation node count                      0
  Uncertain node count                         0
  Recomputed node count                        2
  Successful recomputations                    2
  Failed recomputations                        0
  Replacement planned                        Yes
  Replacement executed                       Yes
  Replacement succeeded                      Yes
  Selective recovery executed                Yes
  Selective recovery duration           0.762 ms
  Recovery duration                     2.297 ms

**Recomputed nodes:** `C_ORDER_ELIGIBLE`, `P_CREATE_ORDER`

**Preserved nodes:** `B_INVENTORY`, `B_PRICING`, `B_SHIPPING_AUTH`,
`C_SHIPPING_READY`, `P_CREATE_SHIPMENT`

### 4.3 Full-restart comparison

  -----------------------------------------------------------------------
  Measurement              BeliefGraph recovery     Full-restart baseline
  ------------------- ------------------------- -------------------------
  Semantic nodes               2 semantic nodes     9 graph nodes rebuilt
  recomputed / graph                 recomputed 
  nodes rebuilt                                 

  Order action                              Yes                       Yes
  succeeded                                     
  -----------------------------------------------------------------------

The reported node-count comparison is `1 - (2 / 9) = 0.777...`, or
approximately **77.8% fewer nodes** in the selective-recovery count
compared with the number of nodes rebuilt by the baseline.

**Interpretation constraint:** these counts describe different
operations---semantic nodes recomputed versus graph nodes rebuilt. Treat
this as a graph-work comparison for this example, not as a universal
reduction in computation or proof of runtime speedup.

The example reports a full-restart build-plus-action time of `0.254 ms`.
That measurement covers a different scope from BeliefGraph's
recovery-engine duration metrics, so the values are not a fair latency
comparison.

## 5. Test and reproducibility status

The project was tested from a fresh clone.

-   Deterministic order-processing recovery example: **PASS**
-   Full test suite: **386 passed**
-   LLM-backed connected workflow: **PASS**

These are the results observed in the reported run. They establish that
the examples and tests passed in that environment, not performance
across other workloads, agents, models, or environments.

## 6. What this experiment supports

The observed run supports these limited conclusions:

-   The example connects an LLM-backed decision step to a tool failure
    and a BeliefGraph recovery workflow.
-   The LLM's proposed API version is checked against tool evidence.
-   In this scenario, BeliefGraph recomputes the two listed semantic
    nodes and preserves the listed independent shipping branch.
-   Both selective recovery and the full-restart baseline complete the
    order action successfully.
-   The repository's reported test suite and examples pass in the tested
    environment.

## 7. Limitations

This is a small integration scenario with a simulated order-processing
tool. Results should not be generalized beyond the tested scenario
without additional experiments.

-   One scenario does not establish performance across graph structures
    or failure types.
-   The node-count comparison uses different categories of work:
    semantic nodes recomputed versus graph nodes rebuilt.
-   The timing measurements cover different scopes and cannot support a
    latency-speedup claim.
-   One successful LLM response does not establish reliability across
    models, prompts, repeated runs, or ambiguous failures.
-   The test count establishes test-suite status, not market viability
    or superiority to existing agent frameworks.

## 8. Next evaluation steps

1.  **Scenario coverage:** test multiple failure types, including
    changed API versions, invalid assumptions, failed actions, and
    changes affecting multiple branches.
2.  **Correctness:** verify whether recovery reaches the expected final
    state and whether unaffected state remains valid.
3.  **Invalidation quality:** measure necessary invalidations,
    unnecessary invalidations, stale nodes preserved, and nodes
    correctly preserved.
4.  **Work performed:** count graph nodes rebuilt, semantic nodes
    recomputed, evaluator calls, and action retries separately.
5.  **Repeated runs:** repeat each scenario and report counts and
    distributions instead of relying on one run.
6.  **Comparable timing:** benchmark the same end-to-end scope for
    selective recovery and full restart, with identical workloads and
    timing boundaries.
7.  **LLM variability:** record model, prompt/configuration, trial
    count, decision correctness, and failures. Separate LLM decision
    quality from BeliefGraph recovery correctness.
8.  **Baselines:** define each baseline precisely and ensure it solves
    the same task under the same success criteria.

## 9. Current conclusion

The experiment demonstrates a working example of evidence-checked LLM
decision-making combined with dependency-aware selective recovery. In
this scenario, the replacement action succeeds, two semantic nodes are
recomputed, and the independent shipping branch is preserved.

This is a useful initial demonstration, not yet a broad performance
evaluation. The next step is to expand the scenario set and collect
comparable, repeatable measurements before making general efficiency or
reliability claims.
