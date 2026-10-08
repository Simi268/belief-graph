from dataclasses import dataclass

from .agent import AgentRuntime
from .models import (
    DependencyType,
    NodeStatus,
    NodeType,
)


@dataclass
class MultiBranchScenarioResult:
    """
    Result produced by Scenario #2.

    Scenario:
        One shared belief feeds multiple reasoning branches
        with different dependency semantics.

        B1
        |
        C1
        |
        +---- P1 ---- A1   (REQUIRES)
        |
        +---- P2 ---- A2   (SUPPORTS)
        |
        +---- P3 ---- A3   (CONTEXT)

        B4 ---- C4 ---- P4 ---- A4
        unrelated branch
    """

    scenario_id: str

    changed_belief: str

    affected_nodes: list[str]

    invalidated_nodes: list[str]

    reevaluation_nodes: list[str]

    uncertain_nodes: list[str]

    preserved_nodes: list[str]

    propagation_depth: int

    affected_node_count: int

    invalidated_node_count: int

    reevaluation_node_count: int

    uncertain_node_count: int

    preserved_node_count: int

    preservation_ratio: float

    affected_branch_count: int

    revision_count: int

    total_original_nodes: int


class MultiBranchBeliefRevisionScenario:
    """
    Scenario #2 — Multi-Branch Belief Revision.

    Purpose:

        Test whether a single changed belief can propagate
        different states through multiple dependency branches
        while preserving unrelated reasoning.

    This scenario intentionally uses three dependency types:

        REQUIRES
            -> INVALID

        SUPPORTS
            -> REQUIRES_REEVALUATION

        CONTEXT
            -> UNCERTAIN
    """

    SCENARIO_ID = "multi_branch_belief_revision_v1"

    def run(self) -> MultiBranchScenarioResult:

        agent = AgentRuntime()

        # ======================================================
        # SHARED BELIEF
        # ======================================================

        agent.create_belief(
            belief_id="B1",
            content="API supports version v1",
            value="v1",
            confidence=0.90,
            source="initial-knowledge",
        )

        agent.create_node(
            node_id="C1",
            node_type=NodeType.CONCLUSION,
            content="The customer API can be used",
        )

        agent.add_dependency(
            "B1",
            "C1",
            DependencyType.REQUIRES,
        )

        # ======================================================
        # BRANCH 1 — REQUIRES
        # ======================================================

        agent.create_node(
            node_id="P1",
            node_type=NodeType.PLAN,
            content="Retrieve customer data",
        )

        agent.create_node(
            node_id="A1",
            node_type=NodeType.ACTION,
            content="Call customer API",
        )

        agent.add_dependency(
            "C1",
            "P1",
            DependencyType.REQUIRES,
        )

        agent.add_dependency(
            "P1",
            "A1",
            DependencyType.REQUIRES,
        )

        # ======================================================
        # BRANCH 2 — SUPPORTS
        # ======================================================

        agent.create_node(
            node_id="P2",
            node_type=NodeType.PLAN,
            content="Use API-backed customer workflow",
        )

        agent.create_node(
            node_id="A2",
            node_type=NodeType.ACTION,
            content="Process customer workflow",
        )

        agent.add_dependency(
            "C1",
            "P2",
            DependencyType.SUPPORTS,
        )

        agent.add_dependency(
            "P2",
            "A2",
            DependencyType.REQUIRES,
        )

        # ======================================================
        # BRANCH 3 — CONTEXT
        # ======================================================

        agent.create_node(
            node_id="P3",
            node_type=NodeType.PLAN,
            content="Prepare API request context",
        )

        agent.create_node(
            node_id="A3",
            node_type=NodeType.ACTION,
            content="Execute contextual request",
        )

        agent.add_dependency(
            "C1",
            "P3",
            DependencyType.CONTEXT,
        )

        agent.add_dependency(
            "P3",
            "A3",
            DependencyType.REQUIRES,
        )

        # ======================================================
        # UNRELATED BRANCH
        # ======================================================

        agent.create_belief(
            belief_id="B4",
            content="Authentication token is valid",
            value=True,
            confidence=0.95,
            source="authentication-service",
        )

        agent.create_node(
            node_id="C4",
            node_type=NodeType.CONCLUSION,
            content="Authenticated requests can be executed",
        )

        agent.create_node(
            node_id="P4",
            node_type=NodeType.PLAN,
            content="Prepare authenticated request",
        )

        agent.create_node(
            node_id="A4",
            node_type=NodeType.ACTION,
            content="Send authenticated request",
        )

        agent.add_dependency(
            "B4",
            "C4",
            DependencyType.REQUIRES,
        )

        agent.add_dependency(
            "C4",
            "P4",
            DependencyType.REQUIRES,
        )

        agent.add_dependency(
            "P4",
            "A4",
            DependencyType.REQUIRES,
        )

        # ======================================================
        # ORIGINAL REASONING POPULATION
        # ======================================================

        original_reasoning_nodes = {
            "B1",
            "C1",
            "P1",
            "A1",
            "P2",
            "A2",
            "P3",
            "A3",
            "B4",
            "C4",
            "P4",
            "A4",
        }

        # ======================================================
        # BELIEF REVISION
        # ======================================================

        impact = agent.graph.propagate_state_impact(
            "B1",
            NodeStatus.INVALID,
        )

        # ======================================================
        # CLASSIFY IMPACT
        # ======================================================

        invalidated_nodes = []
        reevaluation_nodes = []
        uncertain_nodes = []

        for node_id, details in impact.items():

            if not isinstance(details, dict):
                continue

            status = details.get("impact")

            if status == NodeStatus.INVALID:
                invalidated_nodes.append(node_id)

            elif (
                status
                == NodeStatus.REQUIRES_REEVALUATION
            ):
                reevaluation_nodes.append(node_id)

            elif status == NodeStatus.UNCERTAIN:
                uncertain_nodes.append(node_id)

        # ======================================================
        # AFFECTED REGION
        # ======================================================

        affected_nodes = sorted(
            set(invalidated_nodes)
            | set(reevaluation_nodes)
            | set(uncertain_nodes)
        )

        # ======================================================
        # PRESERVED REGION
        # ======================================================

        preserved_nodes = sorted(
            original_reasoning_nodes
            - set(affected_nodes)
            - {"B1"}
        )

        # B1 is the changed root, so it is not counted as
        # preserved even though it is not returned by the
        # downstream impact map.
        #
        # The root itself is explicitly part of the affected
        # reasoning region.

        affected_nodes = sorted(
            set(affected_nodes)
            | {"B1"}
        )

        # ======================================================
        # PROPAGATION DEPTH
        # ======================================================

        propagation_depth = max(
            (
                details["depth"]
                for details in impact.values()
                if (
                    isinstance(details, dict)
                    and isinstance(
                        details.get("depth"),
                        int,
                    )
                )
            ),
            default=0,
        )

        # ======================================================
        # AFFECTED BRANCH COUNT
        # ======================================================

        affected_branch_count = 0

        if (
            "P1" in affected_nodes
            or "A1" in affected_nodes
        ):
            affected_branch_count += 1

        if (
            "P2" in affected_nodes
            or "A2" in affected_nodes
        ):
            affected_branch_count += 1

        if (
            "P3" in affected_nodes
            or "A3" in affected_nodes
        ):
            affected_branch_count += 1

        # ======================================================
        # SELECTIVE PRESERVATION
        # ======================================================

        total_original_nodes = len(
            original_reasoning_nodes
        )

        affected_node_count = len(
            affected_nodes
        )

        invalidated_node_count = len(
            invalidated_nodes
        ) + 1  # B1 itself

        reevaluation_node_count = len(
            reevaluation_nodes
        )

        uncertain_node_count = len(
            uncertain_nodes
        )

        preserved_node_count = len(
            preserved_nodes
        )

        preservation_ratio = (
            preserved_node_count
            / total_original_nodes
            if total_original_nodes > 0
            else 0.0
        )

        # ======================================================
        # RETURN RESULT
        # ======================================================

        return MultiBranchScenarioResult(
            scenario_id=self.SCENARIO_ID,

            changed_belief="B1",

            affected_nodes=affected_nodes,

            invalidated_nodes=sorted(
                set(invalidated_nodes)
                | {"B1"}
            ),

            reevaluation_nodes=sorted(
                reevaluation_nodes
            ),

            uncertain_nodes=sorted(
                uncertain_nodes
            ),

            preserved_nodes=preserved_nodes,

            propagation_depth=propagation_depth,

            affected_node_count=(
                affected_node_count
            ),

            invalidated_node_count=(
                invalidated_node_count
            ),

            reevaluation_node_count=(
                reevaluation_node_count
            ),

            uncertain_node_count=(
                uncertain_node_count
            ),

            preserved_node_count=(
                preserved_node_count
            ),

            preservation_ratio=(
                preservation_ratio
            ),

            affected_branch_count=(
                affected_branch_count
            ),

            revision_count=1,

            total_original_nodes=(
                total_original_nodes
            ),
        )