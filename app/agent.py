from .graph import BeliefGraph
from .models import (
    BeliefNode,
    Evidence,
    NodeType,
    NodeStatus,
    DependencyType
)


class AgentRuntime:

    def __init__(self):
        self.graph = BeliefGraph()

    def create_belief(
        self,
        belief_id: str,
        content: str,
        value=None,
        confidence: float = 1.0,
        source: str | None = None
    ):
        belief = BeliefNode(
            id=belief_id,
            node_type=NodeType.BELIEF,
            content=content,
            value=value,
            confidence=confidence,
            source=source
        )

        self.graph.add_node(belief)
        return belief

    def create_node(
        self,
        node_id: str,
        node_type: NodeType,
        content: str,
        value=None,
        confidence: float = 1.0,
        source: str | None = None
    ):
        node = BeliefNode(
            id=node_id,
            node_type=node_type,
            content=content,
            value=value,
            confidence=confidence,
            source=source
        )

        self.graph.add_node(node)

        return node

    def observe(
        self,
        evidence_id: str,
        content: str,
        source: str,
        confidence: float = 1.0
    ):
        evidence = Evidence(
            id=evidence_id,
            content=content,
            source=source,
            confidence=confidence
        )

        self.graph.add_evidence(evidence)
        return evidence

    def support_belief(
        self,
        evidence_id: str,
        belief_id: str
    ):
        self.graph.link_evidence(
            evidence_id,
            belief_id,
            DependencyType.SUPPORTS
        )

    def detect_contradiction(
        self,
        evidence_id: str,
        belief_id: str
    ):
        return self.graph.detect_conflict(
            evidence_id,
            belief_id
        )

    def revise(
        self,
        conflict_id: str,
        new_belief: BeliefNode
    ):
        return self.graph.resolve_conflict(
            conflict_id,
            new_belief
        )

    def get_belief_status(
        self,
        belief_id: str
    ):
        belief = self.graph.get_node(belief_id)
        return belief.status

    def execute_api_action(
        self,
        environment,
        belief_id: str,
        action_id: str | None = None
    ):
        belief = self.graph.get_node(belief_id)

        if belief.node_type != NodeType.BELIEF:
            raise ValueError(
                "The supplied node must be a belief."
            )

        if belief.status != NodeStatus.ACTIVE:
            return {
                "success": False,
                "error": "INVALID_BELIEF",
                "belief_id": belief_id,
                "action_id": action_id,
                "status": belief.status
            }

        result = environment.call_api(
            belief.value
        )

        return {
            "belief_id": belief_id,
            "action_id": action_id,
            "assumed_version": belief.value,
            "environment_result": result
        }

    def create_evidence_from_action_result(
        self,
        evidence_id: str,
        action_result: dict,
        source: str = "environment"
    ):
        environment_result = action_result[
            "environment_result"
        ]

        if environment_result["success"]:
            return None

        evidence = self.observe(
            evidence_id=evidence_id,
            content=(
                f"Environment reports API version "
                f"{environment_result['expected']}, "
                f"but agent used "
                f"{environment_result['received']}."
            ),
            source=source,
            confidence=1.0
        )

        evidence.metadata["expected_version"] = (
            environment_result["expected"]
        )

        belief_id = action_result["belief_id"]

        conflict = self.detect_contradiction(
            evidence_id,
            belief_id
        )

        return {
            "evidence": evidence,
            "conflict": conflict
        }

    def revise_from_action_failure(
        self,
        conflict_id: str,
        new_belief_id: str
    ):
        conflict = self.graph.get_conflict(
            conflict_id
        )

        evidence = self.graph.get_evidence(
            conflict.evidence_id
        )

        new_value = evidence.metadata.get(
            "expected_version"
        )

        new_belief = BeliefNode(
            id=new_belief_id,
            node_type=NodeType.BELIEF,
            content=(
                f"API version is {new_value}"
            ),
            value=new_value,
            confidence=evidence.confidence,
            source=evidence.source
        )

        # Action failure is direct environment evidence.
        # Unlike ordinary evidence, it should force revision even when
        # confidence is equal to the old belief's confidence.
        impact = self.graph.revise_belief(
            conflict.belief_id,
            new_belief
        )

        conflict.resolved = True

        return {
            "status": "revised",
            "old_belief": conflict.belief_id,
            "new_belief": new_belief.id,
            "evidence": evidence.id,
            "impact": impact
        }

    def add_dependency(
        self,
        source_id: str,
        target_id: str,
        dependency_type: DependencyType
    ):
        self.graph.add_dependency(
            source_id,
            target_id,
            dependency_type
        )

    # --------------------------------------------------
    # CAUSAL RECOVERY PLANNING
    # --------------------------------------------------

    def create_recovery_plan(
        self,
        impact: dict,
        changed_nodes: list[str] | None = None
    ):
        """
        Convert dependency impact analysis into a
        selective recovery plan.

        Categories:

        - changed_nodes:
            Original beliefs/nodes that triggered recovery.

        - affected_nodes:
            Downstream nodes whose predicted state changed.

        - replan_nodes:
            PLAN/ACTION nodes requiring recovery.

        - preserved_nodes:
            Nodes outside both the changed and affected
            regions.

        - causes:
            Changed beliefs responsible for each affected node.
        """

        changed_nodes = list(
            dict.fromkeys(
                changed_nodes or []
            )
        )

        affected_nodes = []
        replan_nodes = []
        causes = {}

        # --------------------------------------------------
        # 1. Identify affected nodes
        # --------------------------------------------------

        for node_id, details in impact.items():

            # Ignore metadata entries.
            if not isinstance(details, dict):
                continue

            if "impact" not in details:
                continue

            affected_nodes.append(node_id)

            causes[node_id] = list(
                details.get(
                    "affected_by",
                    []
                )
            )

            # --------------------------------------------------
            # 2. Identify nodes requiring replanning
            # --------------------------------------------------

            if node_id not in self.graph.graph:
                continue

            node = self.graph.get_node(
                node_id
            )

            predicted_status = details[
                "impact"
            ]

            if node.node_type in {
                NodeType.PLAN,
                NodeType.ACTION
            }:
                if predicted_status in {
                    NodeStatus.INVALID,
                    NodeStatus.REQUIRES_REEVALUATION,
                    NodeStatus.UNCERTAIN
                }:
                    replan_nodes.append(
                        node_id
                    )

        # --------------------------------------------------
        # 3. Identify preserved nodes
        # --------------------------------------------------

        excluded_nodes = (
            set(affected_nodes)
            | set(changed_nodes)
        )

        # A recovery graph can contain non-reasoning artifacts such as
        # evidence nodes, as well as newly introduced replacement beliefs.
        # Preserved nodes should describe the original reasoning state, not
        # artifacts created during this recovery cycle.
        reasoning_node_types = {
            NodeType.BELIEF,
            NodeType.CONCLUSION,
            NodeType.PLAN,
            NodeType.ACTION
        }

        # A revised belief is the target of an old belief's
        # ``superseded_by`` pointer. It participates in recovery, but it is
        # not a preserved part of the pre-change state.
        revised_nodes = set()
        for node_id in self.graph.graph.nodes:
            node_data = self.graph.graph.nodes[node_id].get("data")
            if node_data is None:
                continue
            if node_data.superseded_by is not None:
                revised_nodes.add(node_data.superseded_by)

        excluded_nodes |= revised_nodes

        preserved_nodes = []
        for node_id in self.graph.graph.nodes:
            if node_id in excluded_nodes:
                continue

            node_data = self.graph.graph.nodes[node_id].get("data")
            if node_data is None:
                continue

            if node_data.node_type not in reasoning_node_types:
                continue

            preserved_nodes.append(node_id)

        # --------------------------------------------------
        # 4. Return structured recovery plan
        # --------------------------------------------------

        return {
            "changed_nodes": sorted(
                changed_nodes
            ),
            "affected_nodes": sorted(
                affected_nodes
            ),
            "replan_nodes": sorted(
                replan_nodes
            ),
            "preserved_nodes": sorted(
                preserved_nodes
            ),
            "causes": causes
        }
