import networkx as nx

from .models import (
    BeliefNode,
    Conflict,
    ConflictSeverity,
    Evidence,
    NodeStatus,
    DependencyType
)


class BeliefGraph:

    def __init__(self):

        self.graph = nx.DiGraph()

        self.evidence = {}

        self.conflicts = {}

    # --------------------------------------------------
    # NODE MANAGEMENT
    # --------------------------------------------------

    def add_node(
        self,
        node: BeliefNode
    ):

        self.graph.add_node(
            node.id,
            data=node
        )

    def get_node(
        self,
        node_id: str
    ):

        return self.graph.nodes[
            node_id
        ]["data"]

    # --------------------------------------------------
    # EVIDENCE MANAGEMENT
    # --------------------------------------------------

    def add_evidence(
        self,
        evidence: Evidence
    ):

        self.evidence[
            evidence.id
        ] = evidence

    def get_evidence(
        self,
        evidence_id: str
    ):

        return self.evidence[
            evidence_id
        ]

    def link_evidence(
        self,
        evidence_id: str,
        belief_id: str,
        relationship: DependencyType
    ):

        if evidence_id not in self.evidence:

            raise ValueError(
                f"Evidence '{evidence_id}' "
                "does not exist."
            )

        if belief_id not in self.graph:

            raise ValueError(
                f"Belief '{belief_id}' "
                "does not exist."
            )

        self.graph.add_edge(
            evidence_id,
            belief_id,
            dependency_type=relationship
        )

    # --------------------------------------------------
    # DEPENDENCY MANAGEMENT
    # --------------------------------------------------

    def add_dependency(
        self,
        source_id: str,
        target_id: str,
        dependency_type: DependencyType
    ):

        self.graph.add_edge(
            source_id,
            target_id,
            dependency_type=dependency_type
        )

    def get_dependency_type(
        self,
        source_id: str,
        target_id: str
    ):

        return self.graph.edges[
            source_id,
            target_id
        ]["dependency_type"]

    # --------------------------------------------------
    # CONFLICT MANAGEMENT
    # --------------------------------------------------

    def detect_conflict(
        self,
        evidence_id: str,
        belief_id: str
    ):

        if evidence_id not in self.evidence:

            raise ValueError(
                f"Evidence '{evidence_id}' "
                "does not exist."
            )

        if belief_id not in self.graph:

            raise ValueError(
                f"Belief '{belief_id}' "
                "does not exist."
            )

        evidence = self.get_evidence(
            evidence_id
        )

        conflict_id = (
            f"CONFLICT-{evidence_id}-{belief_id}"
        )

        # Prevent duplicate conflicts
        if conflict_id in self.conflicts:

            return self.conflicts[
                conflict_id
            ]

        severity = (
            ConflictSeverity.HIGH
            if evidence.confidence >= 0.9
            else ConflictSeverity.MEDIUM
        )

        conflict = Conflict(
            id=conflict_id,
            evidence_id=evidence_id,
            belief_id=belief_id,
            reason=(
                f"Evidence '{evidence_id}' "
                f"contradicts belief '{belief_id}'."
            ),
            severity=severity
        )

        self.conflicts[
            conflict_id
        ] = conflict

        # Record contradiction in graph
        self.graph.add_edge(
            evidence_id,
            belief_id,
            dependency_type=(
                DependencyType.CONTRADICTS
            )
        )

        return conflict

    def get_conflict(
        self,
        conflict_id: str
    ):

        return self.conflicts[
            conflict_id
        ]

    # --------------------------------------------------
    # CONFLICT RESOLUTION
    # --------------------------------------------------

    def resolve_conflict(
        self,
        conflict_id: str,
        new_belief: BeliefNode
    ):
        """
        Resolve a conflict by comparing the
        confidence of the new evidence with
        the existing belief.

        Stronger evidence:
            → revise belief

        Weaker evidence:
            → reject proposed revision

        Equal confidence:
            → mark belief uncertain
        """

        if conflict_id not in self.conflicts:

            raise ValueError(
                f"Conflict '{conflict_id}' "
                "does not exist."
            )

        conflict = self.get_conflict(
            conflict_id
        )

        evidence = self.get_evidence(
            conflict.evidence_id
        )

        old_belief = self.get_node(
            conflict.belief_id
        )

        # ----------------------------------------------
        # CASE 1: Evidence is stronger
        # ----------------------------------------------

        if (
            evidence.confidence
            > old_belief.confidence
        ):

            impact = self.revise_belief(
                old_belief.id,
                new_belief
            )

            conflict.resolved = True

            return {
                "status": "revised",
                "old_belief": old_belief.id,
                "new_belief": new_belief.id,
                "evidence": evidence.id,
                "impact": impact
            }

        # ----------------------------------------------
        # CASE 2: Evidence is weaker
        # ----------------------------------------------

        if (
            evidence.confidence
            < old_belief.confidence
        ):

            return {
                "status": "rejected",
                "old_belief": old_belief.id,
                "evidence": evidence.id,
                "reason": (
                    "Evidence confidence is lower "
                    "than belief confidence."
                )
            }

        # ----------------------------------------------
        # CASE 3: Equal confidence
        # ----------------------------------------------

        old_belief.status = (
            NodeStatus.UNCERTAIN
        )

        return {
            "status": "uncertain",
            "old_belief": old_belief.id,
            "evidence": evidence.id,
            "reason": (
                "Evidence and belief have equal "
                "confidence."
            )
        }

    # --------------------------------------------------
    # INVALIDATION
    # --------------------------------------------------

    def invalidate(
        self,
        node_id: str
    ):

        affected = nx.descendants(
            self.graph,
            node_id
        )

        affected.add(node_id)

        for affected_id in affected:

            if affected_id not in self.graph.nodes:
                continue

            node_data = self.graph.nodes[
                affected_id
            ].get("data")

            if node_data is not None:

                node_data.status = (
                    NodeStatus.INVALID
                )

        return affected

    # --------------------------------------------------
    # IMPACT ANALYSIS
    # --------------------------------------------------

    def analyze_impact(
        self,
        node_id: str
    ):

        impact = {}

        for dependent_id in self.graph.successors(
            node_id
        ):

            dependency_type = (
                self.get_dependency_type(
                    node_id,
                    dependent_id
                )
            )

            status = self._direct_impact(
                NodeStatus.INVALID,
                dependency_type
            )

            impact[
                dependent_id
            ] = {
                "impact": status,
                "dependency_type": dependency_type
            }

        return impact

    # --------------------------------------------------
    # DIRECT IMPACT RULE
    # --------------------------------------------------

    def _direct_impact(
        self,
        source_status: NodeStatus,
        dependency_type: DependencyType
    ):
        """
        Determine how a dependency is affected
        by the current state of its source.

        INVALID is a hard failure.

        REQUIRES_REEVALUATION and UNCERTAIN are
        soft states and do not automatically cause
        downstream invalidation.
        """

        # ----------------------------------------------
        # HARD INVALIDATION
        # ----------------------------------------------

        if source_status == NodeStatus.INVALID:

            if dependency_type in {
                DependencyType.REQUIRES,
                DependencyType.DERIVED_FROM
            }:

                return NodeStatus.INVALID

            if dependency_type == (
                DependencyType.SUPPORTS
            ):

                return (
                    NodeStatus.REQUIRES_REEVALUATION
                )

            if dependency_type == (
                DependencyType.CONTEXT
            ):

                return NodeStatus.UNCERTAIN

            if dependency_type == (
                DependencyType.CONTRADICTS
            ):

                return (
                    NodeStatus.REQUIRES_REEVALUATION
                )

            return (
                NodeStatus.REQUIRES_REEVALUATION
            )

        # ----------------------------------------------
        # SOFT REEVALUATION
        # ----------------------------------------------

        if (
            source_status
            == NodeStatus.REQUIRES_REEVALUATION
        ):

            if dependency_type in {
                DependencyType.REQUIRES,
                DependencyType.DERIVED_FROM,
                DependencyType.SUPPORTS,
                DependencyType.CONTRADICTS
            }:

                return (
                    NodeStatus.REQUIRES_REEVALUATION
                )

            if dependency_type == (
                DependencyType.CONTEXT
            ):

                return NodeStatus.UNCERTAIN

            return (
                NodeStatus.REQUIRES_REEVALUATION
            )

        # ----------------------------------------------
        # UNCERTAIN SOURCE
        # ----------------------------------------------

        if source_status == NodeStatus.UNCERTAIN:

            if dependency_type in {
                DependencyType.REQUIRES,
                DependencyType.DERIVED_FROM
            }:

                return NodeStatus.UNCERTAIN

            if dependency_type == (
                DependencyType.SUPPORTS
            ):

                return (
                    NodeStatus.REQUIRES_REEVALUATION
                )

            if dependency_type == (
                DependencyType.CONTEXT
            ):

                return NodeStatus.UNCERTAIN

            if dependency_type == (
                DependencyType.CONTRADICTS
            ):

                return (
                    NodeStatus.REQUIRES_REEVALUATION
                )

            return NodeStatus.UNCERTAIN

        # ----------------------------------------------
        # ACTIVE SOURCE
        # ----------------------------------------------

        return NodeStatus.ACTIVE

    # --------------------------------------------------
    # STATE-AWARE IMPACT PROPAGATION
    # --------------------------------------------------

    def propagate_state_impact(
        self,
        node_id: str,
        initial_status: NodeStatus = NodeStatus.INVALID,
        max_depth: int | None = None
    ):
        """
        Propagate impact according to the state of
        each intermediate node.

        Unlike propagate_impact(), this method does
        NOT blindly continue through every edge.

        A node requiring reevaluation or marked
        uncertain becomes a soft boundary.

        Example:

            B1 INVALID
              |
            REQUIRES
              ↓
            C1 INVALID
              |
            SUPPORTS
              ↓
            P1 REQUIRES_REEVALUATION
              |
              X  STOP

        A1 downstream of P1 is therefore not
        automatically invalidated.
        """

        results = {}

        queue = [
            (
                node_id,
                initial_status,
                0
            )
        ]

        visited = set()

        while queue:

            (
                current_id,
                current_status,
                depth
            ) = queue.pop(0)

            if current_id in visited:
                continue

            visited.add(current_id)

            if (
                max_depth is not None
                and depth >= max_depth
            ):
                continue

            for dependent_id in self.graph.successors(
                current_id
            ):

                if dependent_id in visited:
                    continue

                dependency_type = (
                    self.get_dependency_type(
                        current_id,
                        dependent_id
                    )
                )

                target_status = self._direct_impact(
                    current_status,
                    dependency_type
                )

                results[
                    dependent_id
                ] = {
                    "impact": target_status,
                    "dependency_type": (
                        dependency_type
                    ),
                    "depth": depth + 1,
                    "source": current_id,
                    "source_status": current_status
                }

                # --------------------------------------
                # HARD STATE CONTINUES
                # --------------------------------------

                if target_status == (
                    NodeStatus.INVALID
                ):

                    queue.append(
                        (
                            dependent_id,
                            target_status,
                            depth + 1
                        )
                    )

                # --------------------------------------
                # SOFT STATES STOP AUTOMATIC CASCADE
                # --------------------------------------

        return results

    # --------------------------------------------------
    # MULTI-BELIEF IMPACT ANALYSIS
    # --------------------------------------------------

    def analyze_multi_belief_impact(
        self,
        changed_nodes: list[str],
        initial_status: NodeStatus = NodeStatus.INVALID,
        max_depth: int | None = None
    ):
        """
        Analyze the combined impact of multiple changed nodes.

        Impact state and causal attribution are tracked separately.

        A soft path does not independently cascade, but its causal
        contribution is retained when another path has already made
        the shared node a hard-invalid state. This allows downstream
        nodes to preserve the complete causal ancestry.
        """

        if not changed_nodes:
            return {}

        roots = list(dict.fromkeys(changed_nodes))

        for root_id in roots:
            if root_id not in self.graph:
                raise ValueError(
                    f"Node '{root_id}' does not exist."
                )

        state_priority = {
            NodeStatus.ACTIVE: 0,
            NodeStatus.UNCERTAIN: 1,
            NodeStatus.REQUIRES_REEVALUATION: 2,
            NodeStatus.INVALID: 3,
        }

        results = {}

        # Queue entries carry the complete causal ancestry known
        # at the time a node is expanded.
        queue = [
            (
                root_id,
                initial_status,
                0,
                {root_id}
            )
            for root_id in roots
        ]

        # A node may need to be revisited when a new causal source
        # reaches an already-invalid shared dependency.
        expanded_causes = {}

        while queue:
            (
                current_id,
                current_status,
                depth,
                causes
            ) = queue.pop(0)

            if (
                max_depth is not None
                and depth >= max_depth
            ):
                continue

            if current_status != NodeStatus.INVALID:
                continue

            expanded = expanded_causes.setdefault(
                current_id,
                set()
            )

            new_current_causes = causes - expanded

            if not new_current_causes:
                continue

            expanded.update(new_current_causes)

            for dependent_id in self.graph.successors(
                current_id
            ):
                dependency_type = self.get_dependency_type(
                    current_id,
                    dependent_id
                )

                target_status = self._direct_impact(
                    current_status,
                    dependency_type
                )

                target_depth = depth + 1

                if dependent_id not in results:
                    results[dependent_id] = {
                        "impact": target_status,
                        "affected_by": sorted(
                            new_current_causes
                        ),
                        "depth": target_depth,
                        "dependency_types": [
                            dependency_type
                        ],
                        "sources": {
                            current_id
                        }
                    }

                    newly_added_causes = set(
                        new_current_causes
                    )

                else:
                    entry = results[dependent_id]

                    existing_causes = set(
                        entry["affected_by"]
                    )

                    newly_added_causes = (
                        new_current_causes
                        - existing_causes
                    )

                    existing_causes.update(
                        new_current_causes
                    )

                    entry["affected_by"] = sorted(
                        existing_causes
                    )

                    if (
                        state_priority[target_status]
                        > state_priority[entry["impact"]]
                    ):
                        entry["impact"] = target_status

                    entry["depth"] = min(
                        entry["depth"],
                        target_depth
                    )

                    if dependency_type not in entry[
                        "dependency_types"
                    ]:
                        entry["dependency_types"].append(
                            dependency_type
                        )

                    entry["sources"].add(
                        current_id
                    )

                # Hard impact continues normally.
                if target_status == NodeStatus.INVALID:
                    queue.append(
                        (
                            dependent_id,
                            NodeStatus.INVALID,
                            target_depth,
                            set(
                                results[dependent_id]
                                ["affected_by"]
                            )
                        )
                    )

                # If this node was already hard-invalidated by
                # another path, a newly discovered causal source
                # must also be propagated downstream, even when
                # this particular edge only contributes a soft state.
                elif (
                    newly_added_causes
                    and results[dependent_id]["impact"]
                    == NodeStatus.INVALID
                ):
                    queue.append(
                        (
                            dependent_id,
                            NodeStatus.INVALID,
                            results[dependent_id]["depth"],
                            set(
                                results[dependent_id]
                                ["affected_by"]
                            )
                        )
                    )

        for details in results.values():
            details["sources"] = sorted(
                details["sources"]
            )
            details["affected_by"] = sorted(
                details["affected_by"]
            )

        return results


    # --------------------------------------------------
    # APPLY STATE-AWARE IMPACT
    # --------------------------------------------------

    def apply_state_impact(
        self,
        impact: dict
    ):
        """
        Apply a previously computed state-aware
        impact result to the graph.

        This intentionally operates on the output
        of propagate_state_impact() so that impact
        prediction and state mutation remain separate.
        """

        applied = {}

        for node_id, details in impact.items():

            if node_id not in self.graph:
                continue

            node = self.get_node(node_id)

            new_status = details["impact"]

            # Do not overwrite a hard invalid state
            # with a softer state.
            if (
                node.status == NodeStatus.INVALID
                and new_status != NodeStatus.INVALID
            ):
                applied[node_id] = (
                    NodeStatus.INVALID
                )
                continue

            node.status = new_status

            applied[node_id] = new_status

        return applied

    # --------------------------------------------------
    # EXISTING PROPAGATION
    # --------------------------------------------------

    def propagate_impact(
        self,
        node_id: str,
        max_depth: int | None = None
    ):

        results = {}

        queue = [
            (node_id, 0)
        ]

        visited = set()

        while queue:

            current_id, depth = queue.pop(0)

            if current_id in visited:
                continue

            visited.add(current_id)

            if (
                max_depth is not None
                and depth >= max_depth
            ):
                continue

            for dependent_id in self.graph.successors(
                current_id
            ):

                if dependent_id in visited:
                    continue

                dependency_type = (
                    self.get_dependency_type(
                        current_id,
                        dependent_id
                    )
                )

                if dependency_type in {
                    DependencyType.REQUIRES,
                    DependencyType.DERIVED_FROM
                }:

                    impact = NodeStatus.INVALID

                elif (
                    dependency_type
                    == DependencyType.SUPPORTS
                ):

                    impact = (
                        NodeStatus.REQUIRES_REEVALUATION
                    )

                elif (
                    dependency_type
                    == DependencyType.CONTEXT
                ):

                    impact = NodeStatus.UNCERTAIN

                elif (
                    dependency_type
                    == DependencyType.CONTRADICTS
                ):

                    impact = (
                        NodeStatus.REQUIRES_REEVALUATION
                    )

                else:

                    impact = (
                        NodeStatus.REQUIRES_REEVALUATION
                    )

                results[
                    dependent_id
                ] = {
                    "impact": impact,
                    "dependency_type": dependency_type,
                    "depth": depth + 1,
                    "source": current_id
                }

                queue.append(
                    (
                        dependent_id,
                        depth + 1
                    )
                )

        return results

    # --------------------------------------------------
    # BELIEF REVISION
    # --------------------------------------------------

    def revise_belief(
        self,
        old_id: str,
        new_belief: BeliefNode
    ):

        old_belief = self.get_node(
            old_id
        )

        # ----------------------------------------------
        # 1. Invalidate the old belief itself
        # ----------------------------------------------

        old_belief.status = (
            NodeStatus.INVALID
        )

        old_belief.superseded_by = (
            new_belief.id
        )

        # ----------------------------------------------
        # 2. Create the new belief version
        # ----------------------------------------------

        new_belief.version = (
            old_belief.version + 1
        )

        self.add_node(
            new_belief
        )

        # ----------------------------------------------
        # 3. Compute dependency-aware impact
        # ----------------------------------------------

        impact = self.propagate_state_impact(
            old_id,
            initial_status=NodeStatus.INVALID
        )

        # ----------------------------------------------
        # 4. Apply only justified state changes
        # ----------------------------------------------

        applied = self.apply_state_impact(
            impact
        )

        # ----------------------------------------------
        # 5. Preserve compatibility with the
        # existing revision contract
        # ----------------------------------------------

        impact["_applied"] = applied

        impact["_affected"] = {
            old_id,
            *applied.keys()
        }

        return impact