from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

import networkx as nx
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent import AgentRuntime
from app.commitments import CommitmentRegistry
from app.models import DependencyType, NodeType
from app.recovery import RecoveryEngine
from app.sdk import BeliefGraphSDK


# ============================================================
# APP CONFIGURATION
# ============================================================

app = FastAPI(
    title="Belief-Graph API",
    description=(
        "Dependency-aware belief revision, impact analysis, "
        "and selective recovery for AI agents."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# IN-MEMORY GRAPH SESSIONS
# Each graph has its own runtime and recovery engine.
# ============================================================

graphs: dict[str, BeliefGraphSDK] = {}
graph_names: dict[str, str] = {}
agents: dict[str, AgentRuntime] = {}
recovery_engines: dict[str, RecoveryEngine] = {}


# ============================================================
# REQUEST MODELS
# ============================================================

class CreateGraphRequest(BaseModel):
    name: str = Field(default="Untitled Graph", min_length=1, max_length=150)


class CreateNodeRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=100)
    node_type: NodeType
    content: str = Field(min_length=1, max_length=5000)
    value: Any = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str | None = None


class CreateDependencyRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=100)
    target_id: str = Field(min_length=1, max_length=100)
    dependency_type: DependencyType = DependencyType.REQUIRES


class AnalyzeImpactRequest(BaseModel):
    changed_node_ids: list[str] = Field(min_length=1)


class RecoverFromFailureRequest(BaseModel):
    action_id: str = Field(min_length=1, max_length=100)
    evidence_id: str = Field(min_length=1, max_length=100)
    new_belief_id: str = Field(min_length=1, max_length=100)
    new_action_id: str = Field(min_length=1, max_length=100)
    action_result: dict[str, Any]


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def to_jsonable(value: Any) -> Any:
    """Convert graph objects and analysis results into JSON-safe data."""

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="python"))

    if is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): to_jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if hasattr(value, "__dict__"):
        return to_jsonable(vars(value))

    return str(value)


def get_sdk(graph_id: str) -> BeliefGraphSDK:
    """Return a graph session or raise 404."""

    sdk = graphs.get(graph_id)

    if sdk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Graph '{graph_id}' was not found.",
        )

    return sdk


def get_agent(graph_id: str) -> AgentRuntime:
    agent = agents.get(graph_id)

    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runtime for graph '{graph_id}' was not found.",
        )

    return agent


def get_recovery_engine(graph_id: str) -> RecoveryEngine:
    engine = recovery_engines.get(graph_id)

    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recovery engine for graph '{graph_id}' was not found.",
        )

    return engine


def graph_snapshot(graph_id: str) -> dict[str, Any]:
    """Build a serializable snapshot of a graph."""

    sdk = get_sdk(graph_id)
    graph = sdk.graph
    underlying_graph = graph.graph

    nodes = []

    for node_id, attributes in underlying_graph.nodes(data=True):
        node_data = attributes.get("data")

        if node_data is not None:
            serialized_node = to_jsonable(node_data)
        else:
            serialized_node = to_jsonable(attributes)

        if isinstance(serialized_node, dict):
            serialized_node.setdefault("id", node_id)
        else:
            serialized_node = {
                "id": node_id,
                "data": serialized_node,
            }

        nodes.append(serialized_node)

    edges = []

    for source_id, target_id, attributes in underlying_graph.edges(data=True):
        edges.append(
            {
                "source": source_id,
                "target": target_id,
                "dependency_type": to_jsonable(
                    attributes.get("dependency_type")
                ),
                "attributes": to_jsonable(attributes),
            }
        )

    return {
        "graph_id": graph_id,
        "name": graph_names.get(graph_id, "Untitled Graph"),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


def ensure_node_exists(sdk: BeliefGraphSDK, node_id: str) -> None:
    if node_id not in sdk.graph.graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' was not found in this graph.",
        )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health", tags=["System"])
def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "Belief-Graph API",
        "version": app.version,
        "active_graphs": len(graphs),
    }


# ============================================================
# GRAPH MANAGEMENT
# ============================================================

@app.post(
    "/graphs",
    status_code=status.HTTP_201_CREATED,
    tags=["Graphs"],
)
def create_graph(request: CreateGraphRequest) -> dict[str, Any]:
    graph_id = str(uuid4())

    # One runtime per graph keeps sessions isolated.
    agent = AgentRuntime()
    sdk = BeliefGraphSDK(runtime=agent)
    commitment_registry = CommitmentRegistry()
    recovery_engine = RecoveryEngine(
        agent=agent,
        commitment_registry=commitment_registry,
    )

    graphs[graph_id] = sdk
    graph_names[graph_id] = request.name
    agents[graph_id] = agent
    recovery_engines[graph_id] = recovery_engine

    return graph_snapshot(graph_id)


@app.get("/graphs", tags=["Graphs"])
def list_graphs() -> dict[str, Any]:
    return {
        "count": len(graphs),
        "graphs": [
            {
                "graph_id": graph_id,
                "name": graph_names.get(graph_id, "Untitled Graph"),
                "node_count": len(sdk.graph.graph.nodes),
                "edge_count": len(sdk.graph.graph.edges),
            }
            for graph_id, sdk in graphs.items()
        ],
    }


@app.get("/graphs/{graph_id}", tags=["Graphs"])
def get_graph(graph_id: str) -> dict[str, Any]:
    return graph_snapshot(graph_id)


# ============================================================
# NODE MANAGEMENT
# ============================================================

@app.post(
    "/graphs/{graph_id}/nodes",
    status_code=status.HTTP_201_CREATED,
    tags=["Nodes"],
)
def create_node(
    graph_id: str,
    request: CreateNodeRequest,
) -> dict[str, Any]:
    sdk = get_sdk(graph_id)

    if request.node_id in sdk.graph.graph:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Node '{request.node_id}' already exists.",
        )

    try:
        sdk.node(
            node_id=request.node_id,
            node_type=request.node_type,
            content=request.content,
            value=request.value,
            confidence=request.confidence,
            source=request.source,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "message": "Node created successfully.",
        "node_id": request.node_id,
        "graph": graph_snapshot(graph_id),
    }


# ============================================================
# DEPENDENCY MANAGEMENT
# ============================================================

@app.post(
    "/graphs/{graph_id}/dependencies",
    status_code=status.HTTP_201_CREATED,
    tags=["Dependencies"],
)
def create_dependency(
    graph_id: str,
    request: CreateDependencyRequest,
) -> dict[str, Any]:
    sdk = get_sdk(graph_id)

    ensure_node_exists(sdk, request.source_id)
    ensure_node_exists(sdk, request.target_id)

    try:
        sdk.depends_on(
            source_id=request.source_id,
            target_id=request.target_id,
            dependency_type=request.dependency_type,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "message": "Dependency created successfully.",
        "source_id": request.source_id,
        "target_id": request.target_id,
        "dependency_type": request.dependency_type.value,
        "graph": graph_snapshot(graph_id),
    }


# ============================================================
# IMPACT ANALYSIS
# ============================================================

@app.post(
    "/graphs/{graph_id}/analyze-impact",
    tags=["Analysis"],
)
def analyze_impact(
    graph_id: str,
    request: AnalyzeImpactRequest,
) -> dict[str, Any]:
    sdk = get_sdk(graph_id)

    missing_nodes = [
        node_id
        for node_id in request.changed_node_ids
        if node_id not in sdk.graph.graph
    ]

    if missing_nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "One or more changed nodes were not found.",
                "missing_node_ids": missing_nodes,
            },
        )

    try:
        impact = sdk.analyze_impact(
            changed_node_ids=request.changed_node_ids
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "graph_id": graph_id,
        "changed_node_ids": request.changed_node_ids,
        "impact": to_jsonable(impact),
    }


# ============================================================
# SELECTIVE RECOVERY
# ============================================================

@app.post(
    "/graphs/{graph_id}/recover",
    tags=["Recovery"],
)
def recover_from_failure(
    graph_id: str,
    request: RecoverFromFailureRequest,
) -> dict[str, Any]:
    """
    Process an action failure, revise the affected belief,
    and create a selective recovery plan.
    """

    sdk = get_sdk(graph_id)
    agent = get_agent(graph_id)
    recovery_engine = get_recovery_engine(graph_id)

    # The failed action must already exist in this graph.
    ensure_node_exists(sdk, request.action_id)

    # Avoid collisions with existing graph nodes.
    existing_ids = set(sdk.graph.graph.nodes)

    proposed_ids = [
        request.new_belief_id,
        request.new_action_id,
    ]

    if len(set(proposed_ids)) != len(proposed_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The new belief ID and new action ID must be different.",
        )

    collisions = [
        node_id for node_id in proposed_ids
        if node_id in existing_ids
    ]

    if collisions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "A proposed recovery node ID already exists.",
                "conflicting_node_ids": collisions,
            },
        )

    # Confirm the supplied node is an action.
    node_attributes = sdk.graph.graph.nodes[request.action_id]
    node_data = node_attributes.get("data")

    node_type = getattr(node_data, "node_type", None)

    if node_type is None and isinstance(node_data, dict):
        node_type = node_data.get("node_type")

    if node_type is not None:
        node_type_value = (
            node_type.value if isinstance(node_type, Enum) else node_type
        )

        if node_type_value != NodeType.ACTION.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Node '{request.action_id}' is not an action node.",
            )

    # Preserve the caller's action result and attach the action ID
    # required by RecoveryEngine for selective replanning.
    action_result = dict(request.action_result)
    action_result["action_id"] = request.action_id

    try:
        result = recovery_engine.recover_from_action_failure(
            action_result=action_result,
            evidence_id=request.evidence_id,
            new_belief_id=request.new_belief_id,
            new_action_id=request.new_action_id,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "graph_id": graph_id,
        "result": to_jsonable(result),
        "graph": graph_snapshot(graph_id),
    }


# ============================================================
# GRAPH EXPORT
# ============================================================

@app.get(
    "/graphs/{graph_id}/export",
    tags=["Export"],
)
def export_graph(graph_id: str) -> dict[str, Any]:
    return graph_snapshot(graph_id)