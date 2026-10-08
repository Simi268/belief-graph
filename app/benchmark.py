from dataclasses import dataclass, asdict, field
from typing import Any

import networkx as nx

from .agent import AgentRuntime
from .environment import DynamicAPIEnvironment
from .models import NodeType, DependencyType
from .recovery import RecoveryEngine
from .scenario2 import MultiBranchBeliefRevisionScenario
from .scenario3 import DatabaseSchemaChangeScenario
from .scenario4 import PolicyChangeScenario
from app.scenario6 import ToolUnavailableScenario
from app.ground_truth import (
    SCENARIO_6_GROUND_TRUTH,
    SCENARIO_7_GROUND_TRUTH,
)
from app.scenario7 import StaleInformationScenario
from .ground_truth import (
    SCENARIO_1_GROUND_TRUTH,
    SCENARIO_2_GROUND_TRUTH,
    SCENARIO_3_GROUND_TRUTH,
    SCENARIO_4_GROUND_TRUTH,
)


@dataclass
class BenchmarkResult:
    """Structured result for one benchmark run."""

    strategy: str
    scenario_id: str

    task_success: bool
    stale_actions: int
    invalid_plans: int

    recovery_success: bool
    unnecessary_invalidation: int

    propagation_depth: int
    recovery_steps: int
    tool_calls: int
    stale_plans: int = 0

    # Normalized recovery/selectivity metrics.
    affected_node_count: int = 0
    invalidated_node_count: int = 0
    recomputed_node_count: int = 0
    unnecessary_recomputation: int = 0
    preserved_node_count: int = 0
    preservation_ratio: float = 0.0

    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BenchmarkRunner:
    """Controlled benchmark suite.

    Scenario 1:
        API version changes from v1 -> v2.

    Scenario 2:
        One shared belief changes and feeds multiple
        reasoning branches with different dependency types.

    Strategies:
        1. Baseline
        2. Conventional memory
        3. Belief-Graph
    """

    def __init__(self):
        self.scenario_id = SCENARIO_1_GROUND_TRUTH.scenario_id
        self.scenario2_id = SCENARIO_2_GROUND_TRUTH.scenario_id
        self.scenario3_id = SCENARIO_3_GROUND_TRUTH.scenario_id
        self.scenario4_id = SCENARIO_4_GROUND_TRUTH.scenario_id
        self.scenario7_id = SCENARIO_7_GROUND_TRUTH.scenario_id

    # ==========================================================
    # SCENARIO 1 — BASELINE
    # ==========================================================

    def run_baseline(self) -> BenchmarkResult:
        """Baseline agent continues using its original assumption."""

        environment = DynamicAPIEnvironment()
        believed_version = "v1"

        environment.set_api_version("v2")

        tool_result = environment.call_api(believed_version)

        stale_actions = 0
        if not tool_result["success"]:
            stale_actions = 1

        return BenchmarkResult(
            strategy="baseline",
            scenario_id=self.scenario_id,
            task_success=tool_result["success"],
            stale_actions=stale_actions,
            invalid_plans=0,
            recovery_success=False,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=0,
            tool_calls=1,
            stale_plans=1 if stale_actions else 0,
            affected_node_count=stale_actions,
            invalidated_node_count=0,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=0,
            preservation_ratio=0.0,
            details={
                "believed_version": believed_version,
                "actual_version": environment.get_api_version(),
                "environment_result": tool_result,
            },
        )

    # ==========================================================
    # SCENARIO 1 — MEMORY BASELINE
    # ==========================================================

    def run_memory_agent(self) -> BenchmarkResult:
        """Conventional-memory baseline without dependency tracking."""

        environment = DynamicAPIEnvironment()
        believed_version = "v1"

        environment.set_api_version("v2")

        first_result = environment.call_api(believed_version)

        stale_actions = 0

        if not first_result["success"]:
            stale_actions = 1
            believed_version = environment.get_api_version()

        second_result = environment.call_api(believed_version)
        task_success = second_result["success"]

        return BenchmarkResult(
            strategy="memory",
            scenario_id=self.scenario_id,
            task_success=task_success,
            stale_actions=stale_actions,
            invalid_plans=0,
            recovery_success=task_success,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=1 if task_success else 0,
            tool_calls=2,
            stale_plans=0,
            affected_node_count=stale_actions,
            invalidated_node_count=0,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=0,
            preservation_ratio=0.0,
            details={
                "initial_belief": "v1",
                "revised_belief": believed_version,
                "first_attempt": first_result,
                "second_attempt": second_result,
            },
        )

    # ==========================================================
    # SCENARIO 1 — BELIEF-GRAPH
    # ==========================================================

    def run_belief_graph(self) -> BenchmarkResult:
        """Run the actual Scenario 1 Belief-Graph recovery pipeline."""

        agent = AgentRuntime()
        environment = DynamicAPIEnvironment()

        agent.create_belief(
            belief_id="B1",
            content="API version is v1",
            value="v1",
            confidence=0.90,
            source="initial-knowledge",
        )

        agent.create_node(
            node_id="C1",
            node_type=NodeType.CONCLUSION,
            content="Customer data can be retrieved",
        )

        agent.create_node(
            node_id="P1",
            node_type=NodeType.PLAN,
            content="Retrieve customer data",
        )

        agent.create_node(
            node_id="A1",
            node_type=NodeType.ACTION,
            content="Call customer API using v1",
            value="v1",
        )

        agent.add_dependency("B1", "C1", DependencyType.REQUIRES)
        agent.add_dependency("C1", "P1", DependencyType.REQUIRES)
        agent.add_dependency("P1", "A1", DependencyType.REQUIRES)

        agent.create_belief(
            belief_id="B3",
            content="Reporting database is available",
            value=True,
            confidence=0.90,
            source="initial-knowledge",
        )

        agent.create_node(
            node_id="C3",
            node_type=NodeType.CONCLUSION,
            content="Reporting data can be generated",
        )

        agent.create_node(
            node_id="P3",
            node_type=NodeType.PLAN,
            content="Generate reporting data",
        )

        agent.add_dependency("B3", "C3", DependencyType.REQUIRES)
        agent.add_dependency("C3", "P3", DependencyType.REQUIRES)

        original_reasoning_nodes = {
            "B1",
            "C1",
            "P1",
            "A1",
            "B3",
            "C3",
            "P3",
        }

        environment.set_api_version("v2")

        first_result = agent.execute_api_action(
            environment=environment,
            belief_id="B1",
            action_id="A1",
        )

        stale_actions = 0
        if not first_result["environment_result"]["success"]:
            stale_actions = 1

        recovery = RecoveryEngine(agent)

        recovery_result = recovery.recover_from_action_failure(
            action_result=first_result,
            evidence_id="E1",
            new_belief_id="B2",
            new_action_id="A2",
        )

        recovery_plan = recovery_result["recovery_plan"]
        event = recovery_result["event"]

        invalidated_nodes = event.invalidated_nodes
        reevaluation_nodes = event.reevaluation_nodes
        uncertain_nodes = event.uncertain_nodes

        expected_affected_nodes = {
            "B1",
            "C1",
            "P1",
            "A1",
        }

        actual_affected_original_nodes = (
            set(event.affected_nodes) & expected_affected_nodes
        )

        unnecessary_invalidation = len(
            set(invalidated_nodes) - expected_affected_nodes
        )

        new_action = recovery_result.get("new_action")

        recovery_success = False
        second_result = None

        if new_action is not None:
            second_result = agent.execute_api_action(
                environment=environment,
                belief_id="B2",
                action_id=new_action.id,
            )
            recovery_success = (
                second_result["environment_result"]["success"]
            )

        propagation_depth = 0
        changed_belief_id = "B1"

        for node_id in actual_affected_original_nodes:
            try:
                path_length = nx.shortest_path_length(
                    agent.graph.graph,
                    source=changed_belief_id,
                    target=node_id,
                )
                propagation_depth = max(
                    propagation_depth,
                    path_length,
                )
            except nx.NetworkXNoPath:
                continue

        invalid_plans = len(
            [
                node_id
                for node_id in invalidated_nodes
                if node_id == "P1"
            ]
        )

        recovery_steps = 0

        if recovery_result.get("revision") is not None:
            recovery_steps += 1

        if recovery_plan:
            recovery_steps += 1

        if new_action is not None:
            recovery_steps += 1

        affected_node_count = len(actual_affected_original_nodes)

        preserved_nodes = set(
            recovery_plan.get("preserved_nodes", [])
        )

        preserved_original_nodes = (
            preserved_nodes & original_reasoning_nodes
        )

        preserved_node_count = len(preserved_original_nodes)

        preservation_ratio = (
            preserved_node_count / len(original_reasoning_nodes)
            if original_reasoning_nodes
            else 0.0
        )

        revision_count = 1

        replan_count = len(
            recovery_plan.get("replan_nodes", [])
        )

        return BenchmarkResult(
            strategy="belief_graph",
            scenario_id=self.scenario_id,
            task_success=recovery_success,
            stale_actions=stale_actions,
            invalid_plans=invalid_plans,
            recovery_success=recovery_success,
            unnecessary_invalidation=unnecessary_invalidation,
            propagation_depth=propagation_depth,
            recovery_steps=recovery_steps,
            tool_calls=2,
            stale_plans=0,
            affected_node_count=affected_node_count,
            invalidated_node_count=len(invalidated_nodes),
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=preserved_node_count,
            preservation_ratio=preservation_ratio,
            details={
                "initial_belief": "v1",
                "revised_belief": (
                    agent.graph.get_node("B2").value
                    if "B2" in agent.graph.graph.nodes
                    else None
                ),
                "first_attempt": first_result,
                "second_attempt": second_result,
                "affected_node_count": affected_node_count,
                "preserved_node_count": preserved_node_count,
                "preservation_ratio": preservation_ratio,
                "revision_count": revision_count,
                "replan_count": replan_count,
                "propagation_depth": propagation_depth,
                "affected_nodes": sorted(actual_affected_original_nodes),
                "invalidated_nodes": sorted(invalidated_nodes),
                "reevaluation_nodes": sorted(reevaluation_nodes),
                "uncertain_nodes": sorted(uncertain_nodes),
                "preserved_nodes": sorted(preserved_original_nodes),
                "replan_nodes": sorted(
                    recovery_plan.get("replan_nodes", [])
                ),
                "new_action_id": (
                    new_action.id
                    if new_action is not None
                    else None
                ),
            },
        )

    # ==========================================================
    # SCENARIO 2 — BASELINE
    # ==========================================================

    def run_scenario2_baseline(self) -> BenchmarkResult:
        """Scenario 2 blind baseline.

        The baseline has no dependency-aware revision mechanism.
        Its formal impact region is kept separate from the actions
        that would actually be executed with stale assumptions.
        """

        ground_truth = SCENARIO_2_GROUND_TRUTH

        original_nodes = sorted(ground_truth.original_node_ids)
        unrelated_nodes = set(ground_truth.unrelated_nodes)

        downstream_nodes = [
            node_id
            for node_id in original_nodes
            if node_id != ground_truth.changed_node
            and node_id not in unrelated_nodes
        ]

        # Formal downstream/affected inventory.
        stale_nodes = set(downstream_nodes)

        # IMPORTANT:
        # Stale executable actions are a separate benchmark concept.
        # A2/A3 are preserved by Belief-Graph's state-aware propagation,
        # but a blind baseline would still execute them using stale
        # assumptions.
        stale_action_ids = set(
            ground_truth.expected_stale_actions
        )
        stale_actions = len(stale_action_ids)

        stale_plan_count = sum(
            1
            for node_id in downstream_nodes
            if node_id.startswith("P")
        )

        return BenchmarkResult(
            strategy="baseline",
            scenario_id=self.scenario2_id,
            task_success=False,
            stale_actions=stale_actions,
            invalid_plans=0,
            recovery_success=False,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=0,
            tool_calls=0,
            stale_plans=stale_plan_count,
            affected_node_count=len(stale_nodes),
            invalidated_node_count=0,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=len(unrelated_nodes),
            preservation_ratio=(
                len(unrelated_nodes) / len(original_nodes)
                if original_nodes
                else 0.0
            ),
            details={
                "changed_belief": ground_truth.changed_node,
                "stale_nodes": sorted(stale_nodes),
                "stale_action_ids": sorted(stale_action_ids),
                "original_node_count": len(original_nodes),
                "preserved_nodes": sorted(unrelated_nodes),
                "strategy_behavior": "leave_downstream_state_unchanged",
                "dependency_tracking": False,
            },
        )

    # ==========================================================
    # SCENARIO 2 — MEMORY BASELINE
    # ==========================================================

    def run_scenario2_memory(self) -> BenchmarkResult:
        """Scenario 2 conventional-memory baseline.

        Memory can update the changed fact but has no dependency graph,
        so recovery uses a conservative full restart.
        """

        ground_truth = SCENARIO_2_GROUND_TRUTH
        original_nodes = sorted(ground_truth.original_node_ids)

        revised_belief = "v2"
        recomputed_nodes = set(original_nodes)
        invalidated_nodes = set()
        preserved_nodes = set()
        unrelated_nodes = set(ground_truth.unrelated_nodes)

        stale_actions = 0
        invalid_plans = 0

        recomputed_plans = sum(
            1
            for node in recomputed_nodes
            if node.startswith("P")
        )

        return BenchmarkResult(
            strategy="memory",
            scenario_id=self.scenario2_id,
            task_success=True,
            stale_actions=stale_actions,
            invalid_plans=invalid_plans,
            recovery_success=True,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=2,
            tool_calls=3,
            stale_plans=0,
            affected_node_count=len(recomputed_nodes),
            invalidated_node_count=0,
            recomputed_node_count=len(recomputed_nodes),
            unnecessary_recomputation=len(
                recomputed_nodes & unrelated_nodes
            ),
            preserved_node_count=len(preserved_nodes),
            preservation_ratio=(
                len(preserved_nodes) / len(original_nodes)
                if original_nodes
                else 0.0
            ),
            details={
                "initial_belief": "v1",
                "revised_belief": revised_belief,
                "invalidated_nodes": sorted(invalidated_nodes),
                "recomputed_nodes": sorted(recomputed_nodes),
                "recomputed_plan_count": recomputed_plans,
                "preserved_nodes": sorted(preserved_nodes),
                "original_node_count": len(original_nodes),
                "dependency_tracking": False,
                "recovery_policy": "full_restart",
                "reason": (
                    "Memory updates the changed fact but cannot identify "
                    "the minimal dependency region, so recovery restarts "
                    "the reasoning state conservatively."
                ),
            },
        )

    # ==========================================================
    # SCENARIO 2 — BELIEF-GRAPH
    # ==========================================================

    def run_scenario2_belief_graph(self) -> BenchmarkResult:
        """Run the actual Scenario 2 Belief-Graph pipeline."""

        scenario = MultiBranchBeliefRevisionScenario()
        result = scenario.run()

        ground_truth = SCENARIO_2_GROUND_TRUTH
        expected_preserved = set(ground_truth.expected_preserved)
        actual_preserved = set(result.preserved_nodes)

        unnecessary_invalidation = len(
            expected_preserved - actual_preserved
        )

        expected_invalidated = set(
            ground_truth.expected_invalidated
        )
        expected_reevaluation = set(
            ground_truth.expected_reevaluation
        )
        expected_uncertain = set(
            ground_truth.expected_uncertain
        )

        recovery_success = (
            set(result.invalidated_nodes) == expected_invalidated
            and set(result.reevaluation_nodes) == expected_reevaluation
            and set(result.uncertain_nodes) == expected_uncertain
            and expected_preserved.issubset(actual_preserved)
        )

        return BenchmarkResult(
            strategy="belief_graph",
            scenario_id=self.scenario2_id,
            task_success=recovery_success,
            stale_actions=0,
            invalid_plans=sum(
                1
                for node_id in result.invalidated_nodes
                if node_id.startswith("P")
            ),
            recovery_success=recovery_success,
            unnecessary_invalidation=unnecessary_invalidation,
            propagation_depth=result.propagation_depth,
            recovery_steps=1,
            tool_calls=0,
            stale_plans=0,
            affected_node_count=result.affected_node_count,
            invalidated_node_count=result.invalidated_node_count,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=result.preserved_node_count,
            preservation_ratio=result.preservation_ratio,
            details={
                "changed_belief": result.changed_belief,
                "affected_nodes": result.affected_nodes,
                "invalidated_nodes": result.invalidated_nodes,
                "reevaluation_nodes": result.reevaluation_nodes,
                "uncertain_nodes": result.uncertain_nodes,
                "preserved_nodes": result.preserved_nodes,
                "affected_node_count": result.affected_node_count,
                "invalidated_node_count": result.invalidated_node_count,
                "reevaluation_node_count": result.reevaluation_node_count,
                "uncertain_node_count": result.uncertain_node_count,
                "preserved_node_count": result.preserved_node_count,
                "preservation_ratio": result.preservation_ratio,
                "affected_branch_count": result.affected_branch_count,
                "revision_count": result.revision_count,
                "propagation_depth": result.propagation_depth,
                "total_original_nodes": result.total_original_nodes,
                "ground_truth": {
                    "changed_node": ground_truth.changed_node,
                    "expected_invalidated": sorted(
                        ground_truth.expected_invalidated
                    ),
                    "expected_reevaluation": sorted(
                        ground_truth.expected_reevaluation
                    ),
                    "expected_uncertain": sorted(
                        ground_truth.expected_uncertain
                    ),
                    "expected_preserved": sorted(
                        ground_truth.expected_preserved
                    ),
                    "expected_stale_actions": sorted(
                        ground_truth.expected_stale_actions
                    ),
                },
                "metric_definitions": {
                    "affected_node_count": (
                        "nodes whose state is changed, invalidated, "
                        "or requires review"
                    ),
                    "invalidated_node_count": (
                        "nodes explicitly classified as invalid"
                    ),
                    "recomputed_node_count": (
                        "nodes rebuilt by the strategy"
                    ),
                    "unnecessary_recomputation": (
                        "recomputed nodes outside the true affected region"
                    ),
                    "preserved_node_count": (
                        "original nodes left untouched"
                    ),
                    "preservation_ratio": (
                        "preserved original nodes divided by "
                        "original node count"
                    ),
                    "stale_actions": (
                        "actions that a strategy would execute using "
                        "stale assumptions"
                    ),
                },
            },
        )

    # ==========================================================
    # SCENARIO 3 — BASELINE
    # ==========================================================

    def run_scenario3_baseline(self) -> BenchmarkResult:
        """Scenario 3 blind baseline.

        The baseline has no dependency-aware revision mechanism.
        It continues using the old schema assumption, so the action
        depending on the removed email column becomes stale.
        """

        ground_truth = SCENARIO_3_GROUND_TRUTH
        original_nodes = sorted(ground_truth.original_node_ids)
        stale_action_ids = set(ground_truth.expected_stale_actions)
        stale_nodes = set(ground_truth.expected_invalidated)
        stale_actions = len(stale_action_ids)

        stale_plan_count = sum(
            1
            for node_id in stale_nodes
            if node_id.startswith("P")
        )

        return BenchmarkResult(
            strategy="baseline",
            scenario_id=self.scenario3_id,
            task_success=False,
            stale_actions=stale_actions,
            invalid_plans=0,
            recovery_success=False,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=0,
            tool_calls=0,
            stale_plans=stale_plan_count,
            affected_node_count=len(stale_nodes),
            invalidated_node_count=0,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=len(ground_truth.expected_preserved),
            preservation_ratio=(
                len(ground_truth.expected_preserved) / len(original_nodes)
                if original_nodes
                else 0.0
            ),
            details={
                "changed_belief": ground_truth.changed_node,
                "stale_nodes": sorted(stale_nodes),
                "stale_action_ids": sorted(stale_action_ids),
                "original_node_count": len(original_nodes),
                "preserved_nodes": sorted(ground_truth.expected_preserved),
                "strategy_behavior": "continue_using_stale_database_schema",
                "dependency_tracking": False,
            },
        )

    # ==========================================================
    # SCENARIO 3 — MEMORY BASELINE
    # ==========================================================

    def run_scenario3_memory(self) -> BenchmarkResult:
        """Scenario 3 conventional-memory baseline.

        Memory can observe that the schema changed, but without
        dependency tracking it conservatively rebuilds the complete
        reasoning state.
        """

        ground_truth = SCENARIO_3_GROUND_TRUTH
        original_nodes = sorted(ground_truth.original_node_ids)
        unrelated_nodes = set(ground_truth.expected_preserved)
        recomputed_nodes = set(original_nodes)

        recomputed_plans = sum(
            1
            for node_id in recomputed_nodes
            if node_id.startswith("P")
        )

        unnecessary_recomputation = len(
            recomputed_nodes & unrelated_nodes
        )

        return BenchmarkResult(
            strategy="memory",
            scenario_id=self.scenario3_id,
            task_success=True,
            stale_actions=0,
            invalid_plans=0,
            recovery_success=True,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=2,
            tool_calls=3,
            stale_plans=0,
            affected_node_count=len(recomputed_nodes),
            invalidated_node_count=0,
            recomputed_node_count=len(recomputed_nodes),
            unnecessary_recomputation=unnecessary_recomputation,
            preserved_node_count=0,
            preservation_ratio=0.0,
            details={
                "changed_belief": ground_truth.changed_node,
                "recomputed_nodes": sorted(recomputed_nodes),
                "recomputed_plan_count": recomputed_plans,
                "preserved_nodes": [],
                "original_node_count": len(original_nodes),
                "dependency_tracking": False,
                "recovery_policy": "full_restart",
                "reason": (
                    "Memory recognizes the schema change but cannot "
                    "identify the minimal dependency region, so it "
                    "recomputes the complete reasoning state."
                ),
            },
        )

    # ==========================================================
    # SCENARIO 3 — BELIEF-GRAPH
    # ==========================================================

    def run_scenario3_belief_graph(self) -> BenchmarkResult:
        """Run the actual Scenario 3 Belief-Graph pipeline."""

        scenario = DatabaseSchemaChangeScenario()
        result = scenario.run()
        ground_truth = SCENARIO_3_GROUND_TRUTH

        expected_invalidated = set(ground_truth.expected_invalidated)
        expected_reevaluation = set(ground_truth.expected_reevaluation)
        expected_uncertain = set(ground_truth.expected_uncertain)
        expected_preserved = set(ground_truth.expected_preserved)

        actual_invalidated = set(result.invalidated_nodes)
        actual_reevaluation = set(result.reevaluation_nodes)
        actual_uncertain = set(result.uncertain_nodes)
        actual_preserved = set(result.preserved_nodes)

        recovery_success = (
            actual_invalidated == expected_invalidated
            and actual_reevaluation == expected_reevaluation
            and actual_uncertain == expected_uncertain
            and actual_preserved == expected_preserved
        )

        unnecessary_invalidation = len(
            expected_preserved - actual_preserved
        )

        invalid_plans = sum(
            1
            for node_id in actual_invalidated
            if node_id.startswith("P")
        )

        affected_nodes = (
            actual_invalidated
            | actual_reevaluation
            | actual_uncertain
        )

        return BenchmarkResult(
            strategy="belief_graph",
            scenario_id=self.scenario3_id,
            task_success=recovery_success,
            stale_actions=0,
            invalid_plans=invalid_plans,
            recovery_success=recovery_success,
            unnecessary_invalidation=unnecessary_invalidation,
            propagation_depth=result.propagation_depth,
            recovery_steps=1,
            tool_calls=0,
            stale_plans=0,
            affected_node_count=result.affected_node_count,
            invalidated_node_count=result.invalidated_node_count,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=result.preserved_node_count,
            preservation_ratio=result.preservation_ratio,
            details={
                "changed_belief": result.changed_belief,
                "affected_nodes": sorted(affected_nodes),
                "invalidated_nodes": sorted(actual_invalidated),
                "reevaluation_nodes": sorted(actual_reevaluation),
                "uncertain_nodes": sorted(actual_uncertain),
                "preserved_nodes": sorted(actual_preserved),
                "affected_node_count": result.affected_node_count,
                "invalidated_node_count": result.invalidated_node_count,
                "reevaluation_node_count": len(actual_reevaluation),
                "uncertain_node_count": len(actual_uncertain),
                "preserved_node_count": result.preserved_node_count,
                "preservation_ratio": result.preservation_ratio,
                "propagation_depth": result.propagation_depth,
                "total_original_nodes": result.total_original_nodes,
                "direct_graph_execution": True,
                "ground_truth": {
                    "changed_node": ground_truth.changed_node,
                    "expected_invalidated": sorted(expected_invalidated),
                    "expected_reevaluation": sorted(expected_reevaluation),
                    "expected_uncertain": sorted(expected_uncertain),
                    "expected_preserved": sorted(expected_preserved),
                    "expected_stale_actions": sorted(
                        ground_truth.expected_stale_actions
                    ),
                },
            },
        )

    # ==========================================================
    # SCENARIO 3 — RUN ALL
    # ==========================================================

    def run_scenario3_all(self) -> list[BenchmarkResult]:
        """Run all Scenario 3 benchmark strategies."""

        return [
            self.run_scenario3_baseline(),
            self.run_scenario3_memory(),
            self.run_scenario3_belief_graph(),
        ]

    def run_scenario3_as_dicts(self) -> list[dict[str, Any]]:
        """Return Scenario 3 results as JSON-friendly dictionaries."""

        return [
            result.to_dict()
            for result in self.run_scenario3_all()
        ]

    # ==========================================================
    # SCENARIO 4 — BASELINE
    # ==========================================================

    def run_scenario4_baseline(self) -> BenchmarkResult:
        """Scenario 4 blind baseline without dependency tracking."""
        ground_truth = SCENARIO_4_GROUND_TRUTH
        original_nodes = sorted(ground_truth.original_node_ids)
        stale_nodes = set(ground_truth.expected_invalidated)
        stale_action_ids = set(ground_truth.expected_stale_actions)
        stale_plan_count = sum(1 for node_id in stale_nodes if node_id.startswith("P"))

        return BenchmarkResult(
            strategy="baseline",
            scenario_id=self.scenario4_id,
            task_success=False,
            stale_actions=len(stale_action_ids),
            invalid_plans=0,
            recovery_success=False,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=0,
            tool_calls=0,
            stale_plans=stale_plan_count,
            affected_node_count=len(stale_nodes),
            invalidated_node_count=0,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=len(ground_truth.expected_preserved),
            preservation_ratio=(len(ground_truth.expected_preserved) / len(original_nodes) if original_nodes else 0.0),
            details={
                "changed_belief": ground_truth.changed_node,
                "stale_nodes": sorted(stale_nodes),
                "stale_action_ids": sorted(stale_action_ids),
                "original_node_count": len(original_nodes),
                "preserved_nodes": sorted(ground_truth.expected_preserved),
                "strategy_behavior": "continue_using_superseded_policy",
                "dependency_tracking": False,
            },
        )

    # ==========================================================
    # SCENARIO 4 — MEMORY BASELINE
    # ==========================================================

    def run_scenario4_memory(self) -> BenchmarkResult:
        """Scenario 4 memory baseline using conservative full restart."""
        ground_truth = SCENARIO_4_GROUND_TRUTH
        original_nodes = sorted(ground_truth.original_node_ids)
        unrelated_nodes = set(ground_truth.expected_preserved)
        recomputed_nodes = set(original_nodes)
        recomputed_plans = sum(1 for node_id in recomputed_nodes if node_id.startswith("P"))

        return BenchmarkResult(
            strategy="memory",
            scenario_id=self.scenario4_id,
            task_success=True,
            stale_actions=0,
            invalid_plans=0,
            recovery_success=True,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=2,
            tool_calls=3,
            stale_plans=0,
            affected_node_count=len(recomputed_nodes),
            invalidated_node_count=0,
            recomputed_node_count=len(recomputed_nodes),
            unnecessary_recomputation=len(recomputed_nodes & unrelated_nodes),
            preserved_node_count=0,
            preservation_ratio=0.0,
            details={
                "changed_belief": ground_truth.changed_node,
                "recomputed_nodes": sorted(recomputed_nodes),
                "recomputed_plan_count": recomputed_plans,
                "preserved_nodes": [],
                "original_node_count": len(original_nodes),
                "dependency_tracking": False,
                "recovery_policy": "full_restart",
                "reason": "Memory recognizes the policy change but cannot identify the minimal dependency region, so it recomputes the complete reasoning state.",
            },
        )

    # ==========================================================
    # SCENARIO 4 — BELIEF-GRAPH
    # ==========================================================

    def run_scenario4_belief_graph(self) -> BenchmarkResult:
        """Run the actual Scenario 4 Belief-Graph pipeline."""
        scenario = PolicyChangeScenario()
        result = scenario.run()
        ground_truth = SCENARIO_4_GROUND_TRUTH

        expected_invalidated = set(ground_truth.expected_invalidated)
        expected_reevaluation = set(ground_truth.expected_reevaluation)
        expected_uncertain = set(ground_truth.expected_uncertain)
        expected_preserved = set(ground_truth.expected_preserved)

        actual_invalidated = set(result.invalidated_nodes)
        actual_reevaluation = set(result.reevaluation_nodes)
        actual_uncertain = set(result.uncertain_nodes)
        actual_preserved = set(result.preserved_nodes)

        recovery_success = (
            actual_invalidated == expected_invalidated
            and actual_reevaluation == expected_reevaluation
            and actual_uncertain == expected_uncertain
            and actual_preserved == expected_preserved
        )

        affected_nodes = actual_invalidated | actual_reevaluation | actual_uncertain
        invalid_plans = sum(1 for node_id in actual_invalidated if node_id.startswith("P"))

        return BenchmarkResult(
            strategy="belief_graph",
            scenario_id=self.scenario4_id,
            task_success=recovery_success,
            stale_actions=0,
            invalid_plans=invalid_plans,
            recovery_success=recovery_success,
            unnecessary_invalidation=len(expected_preserved - actual_preserved),
            propagation_depth=result.propagation_depth,
            recovery_steps=1,
            tool_calls=0,
            stale_plans=0,
            affected_node_count=result.affected_node_count,
            invalidated_node_count=result.invalidated_node_count,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=result.preserved_node_count,
            preservation_ratio=result.preservation_ratio,
            details={
                "changed_belief": result.changed_belief,
                "affected_nodes": sorted(affected_nodes),
                "invalidated_nodes": sorted(actual_invalidated),
                "reevaluation_nodes": sorted(actual_reevaluation),
                "uncertain_nodes": sorted(actual_uncertain),
                "preserved_nodes": sorted(actual_preserved),
                "affected_node_count": result.affected_node_count,
                "invalidated_node_count": result.invalidated_node_count,
                "reevaluation_node_count": len(actual_reevaluation),
                "uncertain_node_count": len(actual_uncertain),
                "preserved_node_count": result.preserved_node_count,
                "preservation_ratio": result.preservation_ratio,
                "propagation_depth": result.propagation_depth,
                "total_original_nodes": result.total_original_nodes,
                "direct_graph_execution": True,
                "ground_truth": {
                    "changed_node": ground_truth.changed_node,
                    "expected_invalidated": sorted(expected_invalidated),
                    "expected_reevaluation": sorted(expected_reevaluation),
                    "expected_uncertain": sorted(expected_uncertain),
                    "expected_preserved": sorted(expected_preserved),
                    "expected_stale_actions": sorted(ground_truth.expected_stale_actions),
                },
            },
        )

    # ==========================================================
    # SCENARIO 4 — RUN ALL
    # ==========================================================

    def run_scenario4_all(self) -> list[BenchmarkResult]:
        """Run all Scenario 4 benchmark strategies."""
        return [
            self.run_scenario4_baseline(),
            self.run_scenario4_memory(),
            self.run_scenario4_belief_graph(),
        ]

    def run_scenario4_as_dicts(self) -> list[dict[str, Any]]:
        """Return Scenario 4 results as JSON-friendly dictionaries."""
        return [result.to_dict() for result in self.run_scenario4_all()]

# ==========================================================
    # SCENARIO 6 — TOOL UNAVAILABLE
    # ==========================================================

    def run_scenario6_baseline(self) -> BenchmarkResult:
        """
        Baseline agent:
        attempts to use the unavailable tool and fails.
        """

        gt = SCENARIO_6_GROUND_TRUTH

        stale_actions = len(gt.expected_stale_actions)

        return BenchmarkResult(
            strategy="baseline",
            scenario_id=gt.scenario_id,
            task_success=False,
            stale_actions=stale_actions,
            invalid_plans=0,
            recovery_success=False,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=0,
            tool_calls=1,
            stale_plans=1,
            affected_node_count=0,
            invalidated_node_count=0,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=len(gt.expected_preserved),
            preservation_ratio=(
                len(gt.expected_preserved) / len(gt.original_node_ids)
            ),
            details={
                "ground_truth_affected_node_count": len(
                    gt.expected_impact
                ),
                "ground_truth_affected_nodes": sorted(
                    gt.expected_impact
                ),
                "strategy_detected_affected_nodes": [],
                "metric_note": (
                    "Baseline does not perform dependency-aware "
                    "impact analysis; ground-truth affected region "
                    "is reported separately."
                ),
            },
        )

    def run_scenario6_memory(self) -> BenchmarkResult:
        """
        Conventional memory strategy:
        after tool failure, broadly recomputes the task state.
        """

        gt = SCENARIO_6_GROUND_TRUTH

        original_node_count = len(gt.original_node_ids)
        unnecessary = len(gt.expected_preserved)

        return BenchmarkResult(
            strategy="memory",
            scenario_id=gt.scenario_id,
            task_success=True,
            stale_actions=0,
            invalid_plans=0,
            recovery_success=True,
            unnecessary_invalidation=0,
            propagation_depth=0,
            recovery_steps=2,
            tool_calls=3,
            stale_plans=0,
            affected_node_count=original_node_count,
            invalidated_node_count=0,
            recomputed_node_count=original_node_count,
            unnecessary_recomputation=unnecessary,
            preserved_node_count=0,
            preservation_ratio=0.0,
            details={
                "ground_truth_affected_node_count": len(
                    gt.expected_impact
                ),
                "recomputed_nodes": sorted(
                    gt.original_node_ids
                ),
                "unnecessary_recomputed_nodes": sorted(
                    gt.expected_preserved
                ),
            },
        )

    def run_scenario6_belief_graph(self) -> BenchmarkResult:
        """
        Belief-Graph:
        detects that Tool T1 is unavailable, invalidates only the
        dependent reasoning branch, and preserves unrelated work.
        """

        gt = SCENARIO_6_GROUND_TRUTH
        result = ToolUnavailableScenario().run()

        expected_impact = gt.expected_impact

        invalidated = set(result.invalidated_nodes)
        preserved = set(result.preserved_nodes)

        expected_invalidated = set(gt.expected_invalidated)
        expected_preserved = set(gt.expected_preserved)

        if invalidated != expected_invalidated:
            raise AssertionError(
                "Scenario 6 invalidation does not match ground truth: "
                f"expected={sorted(expected_invalidated)}, "
                f"actual={sorted(invalidated)}"
            )

        if preserved != expected_preserved:
            raise AssertionError(
                "Scenario 6 preservation does not match ground truth: "
                f"expected={sorted(expected_preserved)}, "
                f"actual={sorted(preserved)}"
            )

        affected_count = len(result.affected_nodes)

        return BenchmarkResult(
            strategy="belief_graph",
            scenario_id=gt.scenario_id,
            task_success=True,
            stale_actions=0,
            invalid_plans=sum(
                1
                for node in gt.original_nodes
                if node.id in invalidated
                and node.node_type == NodeType.PLAN
                ),
            recovery_success=True,
            unnecessary_invalidation=0,
            propagation_depth=result.propagation_depth,
            recovery_steps=1,
            tool_calls=1,
            stale_plans=0,
            affected_node_count=affected_count,
            invalidated_node_count=result.invalidated_node_count,
            recomputed_node_count=0,
            unnecessary_recomputation=0,
            preserved_node_count=result.preserved_node_count,
            preservation_ratio=result.preservation_ratio,
            details={
                "ground_truth_affected_nodes": sorted(
                    expected_impact
                ),
                "detected_affected_nodes": sorted(
                    result.affected_nodes
                ),
                "preserved_nodes": sorted(
                    result.preserved_nodes
                ),
                "tool_id": result.tool_id,
                "tool_available_before": result.tool_available_before,
                "tool_available_after": result.tool_available_after,
                "revision_count": result.revision_count,
                "metric_note": (
                    "Belief-Graph directly executes the dependency "
                    "impact-analysis layer; full LLM replanning "
                    "runtime is evaluated separately."
                ),
            },
        )

    def run_scenario6_all(self) -> list[BenchmarkResult]:
        """Run all Scenario 6 benchmark strategies."""

        return [
            self.run_scenario6_baseline(),
            self.run_scenario6_memory(),
            self.run_scenario6_belief_graph(),
        ]

    def run_scenario6_as_dicts(self) -> list[dict[str, Any]]:
        """Return Scenario 6 results as JSON-friendly dictionaries."""

        return [
            result.to_dict()
            for result in self.run_scenario6_all()
        ]

    # ==========================================================
    # SCENARIO 7 — STALE INFORMATION
    # ==========================================================

    def run_scenario7_baseline(self) -> BenchmarkResult:
        """Scenario 7 blind baseline using stale information."""
        gt = SCENARIO_7_GROUND_TRUTH
        original_nodes = sorted(gt.original_node_ids)
        stale_nodes = set(gt.expected_invalidated)
        stale_action_ids = set(gt.expected_stale_actions)
        stale_plan_count = sum(1 for node in gt.original_nodes if node.id in stale_nodes and node.node_type == NodeType.PLAN)
        return BenchmarkResult(
            strategy="baseline", scenario_id=self.scenario7_id, task_success=False,
            stale_actions=len(stale_action_ids), invalid_plans=0, recovery_success=False,
            unnecessary_invalidation=0, propagation_depth=0, recovery_steps=0, tool_calls=1,
            stale_plans=stale_plan_count, affected_node_count=0, invalidated_node_count=0,
            recomputed_node_count=0, unnecessary_recomputation=0,
            preserved_node_count=len(gt.expected_preserved),
            preservation_ratio=len(gt.expected_preserved) / len(original_nodes) if original_nodes else 0.0,
            details={
                "changed_belief": gt.changed_node, "stale_nodes": sorted(stale_nodes),
                "stale_action_ids": sorted(stale_action_ids),
                "strategy_detected_affected_nodes": [],
                "ground_truth_affected_nodes": sorted(gt.expected_impact),
                "original_node_count": len(original_nodes),
                "strategy_behavior": "continue_using_stale_information",
                "dependency_tracking": False,
                "metric_note": "Baseline does not perform dependency-aware impact analysis; ground-truth affected region is reported separately.",
            },
        )

    def run_scenario7_memory(self) -> BenchmarkResult:
        """Scenario 7 conventional-memory baseline."""
        gt = SCENARIO_7_GROUND_TRUTH
        original_nodes = sorted(gt.original_node_ids)
        recomputed_nodes = set(original_nodes)
        unrelated_nodes = set(gt.expected_preserved)
        return BenchmarkResult(
            strategy="memory", scenario_id=self.scenario7_id, task_success=True,
            stale_actions=0, invalid_plans=0, recovery_success=True,
            unnecessary_invalidation=0, propagation_depth=0, recovery_steps=2, tool_calls=3,
            stale_plans=0, affected_node_count=len(recomputed_nodes), invalidated_node_count=0,
            recomputed_node_count=len(recomputed_nodes),
            unnecessary_recomputation=len(recomputed_nodes & unrelated_nodes),
            preserved_node_count=0, preservation_ratio=0.0,
            details={
                "changed_belief": gt.changed_node, "recomputed_nodes": sorted(recomputed_nodes),
                "unnecessary_recomputed_nodes": sorted(recomputed_nodes & unrelated_nodes),
                "preserved_nodes": [], "original_node_count": len(original_nodes),
                "dependency_tracking": False, "recovery_policy": "full_restart",
                "reason": "Memory recognizes stale information but cannot identify the minimal dependency region, so it recomputes the complete reasoning state.",
            },
        )

    def run_scenario7_belief_graph(self) -> BenchmarkResult:
        """Run the actual Scenario 7 Belief-Graph pipeline."""
        result = StaleInformationScenario().run()
        gt = SCENARIO_7_GROUND_TRUTH
        expected_invalidated = set(gt.expected_invalidated)
        expected_reevaluation = set(gt.expected_reevaluation)
        expected_uncertain = set(gt.expected_uncertain)
        expected_preserved = set(gt.expected_preserved)
        actual_invalidated = set(result.invalidated_nodes)
        actual_reevaluation = set(result.reevaluation_nodes)
        actual_uncertain = set(result.uncertain_nodes)
        actual_preserved = set(result.preserved_nodes)
        recovery_success = (
            actual_invalidated == expected_invalidated
            and actual_reevaluation == expected_reevaluation
            and actual_uncertain == expected_uncertain
            and actual_preserved == expected_preserved
        )
        affected_nodes = actual_invalidated | actual_reevaluation | actual_uncertain
        invalid_plans = sum(1 for node in gt.original_nodes if node.id in actual_invalidated and node.node_type == NodeType.PLAN)
        return BenchmarkResult(
            strategy="belief_graph", scenario_id=self.scenario7_id, task_success=recovery_success,
            stale_actions=0, invalid_plans=invalid_plans, recovery_success=recovery_success,
            unnecessary_invalidation=len(expected_preserved - actual_preserved),
            propagation_depth=result.propagation_depth, recovery_steps=1, tool_calls=0, stale_plans=0,
            affected_node_count=len(affected_nodes), invalidated_node_count=len(actual_invalidated),
            recomputed_node_count=0, unnecessary_recomputation=0,
            preserved_node_count=len(actual_preserved), preservation_ratio=result.preservation_ratio,
            details={
                "changed_belief": result.changed_belief, "information_source": result.information_source,
                "information_was_fresh": result.information_was_fresh, "information_is_stale": result.information_is_stale,
                "affected_nodes": sorted(affected_nodes), "invalidated_nodes": sorted(actual_invalidated),
                "reevaluation_nodes": sorted(actual_reevaluation), "uncertain_nodes": sorted(actual_uncertain),
                "preserved_nodes": sorted(actual_preserved), "propagation_depth": result.propagation_depth,
                "total_original_nodes": result.total_original_nodes, "revision_count": result.revision_count,
                "direct_graph_execution": True,
                "ground_truth": {
                    "changed_node": gt.changed_node,
                    "expected_invalidated": sorted(expected_invalidated),
                    "expected_reevaluation": sorted(expected_reevaluation),
                    "expected_uncertain": sorted(expected_uncertain),
                    "expected_preserved": sorted(expected_preserved),
                    "expected_stale_actions": sorted(gt.expected_stale_actions),
                },
                "metric_note": "Belief-Graph directly executes the dependency impact-analysis layer; full LLM replanning runtime is evaluated separately.",
            },
        )

    def run_scenario7_all(self) -> list[BenchmarkResult]:
        """Run all Scenario 7 benchmark strategies."""
        return [self.run_scenario7_baseline(), self.run_scenario7_memory(), self.run_scenario7_belief_graph()]

    def run_scenario7_as_dicts(self) -> list[dict[str, Any]]:
        """Return Scenario 7 results as JSON-friendly dictionaries."""
        return [result.to_dict() for result in self.run_scenario7_all()]

    # ==========================================================
    # SCENARIO 1 — RUN ALL
    # ==========================================================

    def run_all(self) -> list[BenchmarkResult]:
        """Run all Scenario 1 benchmark strategies."""

        return [
            self.run_baseline(),
            self.run_memory_agent(),
            self.run_belief_graph(),
        ]

    # ==========================================================
    # SCENARIO 2 — RUN ALL
    # ==========================================================

    def run_scenario2_all(self) -> list[BenchmarkResult]:
        """Run all Scenario 2 benchmark strategies."""

        return [
            self.run_scenario2_baseline(),
            self.run_scenario2_memory(),
            self.run_scenario2_belief_graph(),
        ]

    # ==========================================================
    # SCENARIO 1 — JSON RESULTS
    # ==========================================================

    def run_all_as_dicts(self) -> list[dict[str, Any]]:
        """Return Scenario 1 results as JSON-friendly dictionaries."""

        return [
            result.to_dict()
            for result in self.run_all()
        ]

    # ==========================================================
    # SCENARIO 2 — JSON RESULTS
    # ==========================================================

    def run_scenario2_as_dicts(self) -> list[dict[str, Any]]:
        """Return Scenario 2 results as JSON-friendly dictionaries."""

        return [
            result.to_dict()
            for result in self.run_scenario2_all()
        ]


# ==============================================================
# SCRIPT ENTRY POINT
# ==============================================================

if __name__ == "__main__":

    runner = BenchmarkRunner()

    print("\n" + "=" * 70)
    print("SCENARIO 1 — API VERSION CHANGE")
    print("=" * 70)

    results_v1 = runner.run_all_as_dicts()

    for result in results_v1:
        print(result)

    print("\n" + "=" * 70)
    print("SCENARIO 2 — MULTI-BRANCH BELIEF REVISION")
    print("=" * 70)

    results_v2 = runner.run_scenario2_as_dicts()

    for result in results_v2:
        print(result)

    print("\n" + "=" * 70)
    print("SCENARIO 3 — DATABASE SCHEMA CHANGE")
    print("=" * 70)

    results_v3 = runner.run_scenario3_as_dicts()

    for result in results_v3:
        print(result)

    print("\n" + "=" * 70)
    print("SCENARIO 4 — POLICY CHANGE")
    print("=" * 70)

    results_v4 = runner.run_scenario4_as_dicts()

    for result in results_v4:
        print(result)

    print("\n" + "=" * 70)
    print("SCENARIO 7 — STALE INFORMATION")
    print("=" * 70)

    results_v7 = runner.run_scenario7_as_dicts()

    for result in results_v7:
        print(result)
    