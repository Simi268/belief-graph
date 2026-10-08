from dataclasses import dataclass

from .agent import AgentRuntime
from .environment import DynamicAPIEnvironment
from .models import (
    NodeType,
    DependencyType,
    NodeStatus
)
from .recovery import RecoveryEngine


@dataclass
class ScenarioResult:
    scenario_id: str

    initial_belief: str
    revised_belief: str

    old_action: str
    new_action: str

    recovery_successful: bool

    invalidated_nodes: list[str]

    impact_states: dict[str, str]

    propagation_depth: int

    recovery_steps: int

    total_nodes: int

    initial_node_ids: list[str]


class APIVersionChangeScenario:

    def run(self):

        agent = AgentRuntime()
        environment = DynamicAPIEnvironment()

        # ==================================================
        # BRANCH 1 — API VERSION KNOWLEDGE
        # ==================================================

        agent.create_belief(
            belief_id="B1",
            content="API version is v1",
            value="v1",
            confidence=0.90,
            source="initial-knowledge"
        )

        agent.create_node(
            node_id="C1",
            node_type=NodeType.CONCLUSION,
            content="Customer API can be called using v1"
        )

        agent.create_node(
            node_id="P1",
            node_type=NodeType.PLAN,
            content="Fetch customer data using the customer API"
        )

        agent.create_node(
            node_id="A1",
            node_type=NodeType.ACTION,
            content="Call customer API using v1",
            value="v1"
        )

        agent.add_dependency(
            "B1",
            "C1",
            DependencyType.REQUIRES
        )

        agent.add_dependency(
            "C1",
            "P1",
            DependencyType.REQUIRES
        )

        agent.add_dependency(
            "P1",
            "A1",
            DependencyType.REQUIRES
        )

        # ==================================================
        # BRANCH 2 — SUPPORTING KNOWLEDGE
        # ==================================================

        agent.create_node(
            node_id="C2",
            node_type=NodeType.CONCLUSION,
            content=(
                "Customer data retrieval is supported "
                "by API availability"
            )
        )

        agent.create_node(
            node_id="P2",
            node_type=NodeType.PLAN,
            content=(
                "Continue customer-data retrieval workflow"
            )
        )

        agent.create_node(
            node_id="A2",
            node_type=NodeType.ACTION,
            content="Process retrieved customer data"
        )

        agent.add_dependency(
            "C1",
            "C2",
            DependencyType.SUPPORTS
        )

        agent.add_dependency(
            "C2",
            "P2",
            DependencyType.REQUIRES
        )

        agent.add_dependency(
            "P2",
            "A2",
            DependencyType.REQUIRES
        )

        # ==================================================
        # UNRELATED BRANCH
        # ==================================================

        agent.create_belief(
            belief_id="B3",
            content="Authentication token is valid",
            value=True,
            confidence=0.95,
            source="authentication-service"
        )

        agent.create_node(
            node_id="C3",
            node_type=NodeType.CONCLUSION,
            content=(
                "Authenticated requests can be executed"
            )
        )

        agent.create_node(
            node_id="P3",
            node_type=NodeType.PLAN,
            content="Prepare authenticated request"
        )

        agent.add_dependency(
            "B3",
            "C3",
            DependencyType.REQUIRES
        )

        agent.add_dependency(
            "C3",
            "P3",
            DependencyType.REQUIRES
        )

        # ==================================================
        # CAPTURE ORIGINAL REASONING POPULATION
        # ==================================================

        initial_node_ids = list(
            agent.graph.graph.nodes
        )

        # ==================================================
        # ENVIRONMENT CHANGE
        # ==================================================

        environment.set_api_version("v2")

        action_result = agent.execute_api_action(
            environment,
            belief_id="B1",
            action_id="A1"
        )

        # ==================================================
        # RECOVERY
        # ==================================================

        recovery = RecoveryEngine(agent)

        result = recovery.recover_from_action_failure(
            action_result=action_result,
            evidence_id="E1",
            new_belief_id="B2",
            new_action_id="A4"
        )

        event = result["event"]

        # ==================================================
        # RECOVERY VALIDATION
        # ==================================================

        recovery_successful = (
            result["status"] == "recovered"
            and agent.graph.get_node(
                "B2"
            ).status == NodeStatus.ACTIVE
            and agent.graph.get_node(
                "A4"
            ).status == NodeStatus.ACTIVE
        )

        # ==================================================
        # EXTRACT IMPACT STATES
        # ==================================================

        impact_states = {}

        for node_id, details in (
            result["revision"]["impact"].items()
        ):

            if (
                isinstance(details, dict)
                and "impact" in details
            ):

                impact_states[node_id] = (
                    details["impact"].value
                )

        impact_states["B1"] = (
            NodeStatus.INVALID.value
        )

        # ==================================================
        # PROPAGATION DEPTH
        # ==================================================

        propagation_depth = max(
            (
                details["depth"]
                for details
                in result["revision"]["impact"].values()
                if (
                    isinstance(details, dict)
                    and "depth" in details
                )
            ),
            default=0
        )

        # ==================================================
        # TOTAL GRAPH SIZE AFTER RECOVERY
        # ==================================================

        total_nodes = (
            agent.graph.graph.number_of_nodes()
        )

        return ScenarioResult(
            scenario_id="api-version-change",

            initial_belief="B1",
            revised_belief="B2",

            old_action="A1",
            new_action="A4",

            recovery_successful=recovery_successful,

            invalidated_nodes=(
                event.invalidated_nodes
            ),

            impact_states=impact_states,

            propagation_depth=propagation_depth,

            recovery_steps=4,

            total_nodes=total_nodes,

            initial_node_ids=initial_node_ids
        )