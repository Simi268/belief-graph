from datetime import datetime, timezone

from pydantic import BaseModel, Field


class RevisionEvent(BaseModel):
    event_id: str

    conflict_id: str

    old_belief_id: str
    new_belief_id: str

    old_action_id: str | None = None
    new_action_id: str | None = None

    # Nodes affected in any way by the revision
    affected_nodes: list[str] = Field(
        default_factory=list
    )

    # Nodes whose previous state is no longer valid
    invalidated_nodes: list[str] = Field(
        default_factory=list
    )

    # Nodes whose state may still be usable,
    # but whose reasoning must be checked again
    reevaluation_nodes: list[str] = Field(
        default_factory=list
    )

    # Nodes whose reasoning is no longer fully certain
    uncertain_nodes: list[str] = Field(
        default_factory=list
    )

    reason: str

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )