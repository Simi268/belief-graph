from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    BELIEF = "belief"
    CONCLUSION = "conclusion"
    PLAN = "plan"
    ACTION = "action"


class NodeStatus(str, Enum):
    ACTIVE = "active"
    INVALID = "invalid"
    UNCERTAIN = "uncertain"
    REQUIRES_REEVALUATION = "requires_reevaluation"


class DependencyType(str, Enum):
    REQUIRES = "requires"
    SUPPORTS = "supports"
    CONTEXT = "context"
    DERIVED_FROM = "derived_from"
    CONTRADICTS = "contradicts"


class ConflictSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BeliefNode(BaseModel):
    id: str
    node_type: NodeType
    content: str
    value: Any = None

    source: str | None = None
    confidence: float = 1.0

    status: NodeStatus = NodeStatus.ACTIVE

    version: int = 1
    superseded_by: str | None = None


class Evidence(BaseModel):
    id: str
    content: str
    source: str

    confidence: float = 1.0

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class Conflict(BaseModel):
    id: str

    evidence_id: str
    belief_id: str

    reason: str

    severity: ConflictSeverity = (
        ConflictSeverity.MEDIUM
    )

    resolved: bool = False