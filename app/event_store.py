from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class EventStore:
    """Append-only, per-graph event history with optional graph snapshots."""

    def __init__(self, storage_dir: str = "data/events") -> None:
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, graph_id: str) -> Path:
        if not graph_id or Path(graph_id).name != graph_id:
            raise ValueError("Invalid graph ID")
        return self.storage_dir / f"{graph_id}.json"

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            return {str(k): EventStore._jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [EventStore._jsonable(v) for v in value]
        if hasattr(value, "model_dump"):
            return EventStore._jsonable(value.model_dump(mode="json"))
        if hasattr(value, "value"):
            return EventStore._jsonable(value.value)
        return str(value)

    def append(
        self,
        graph_id: str,
        event_type: str,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a real event and the optional post-event graph snapshot."""
        path = self._file_path(graph_id)
        events = self.list_events(graph_id)
        event = {
            "event_id": str(uuid4()),
            "graph_id": graph_id,
            "sequence": len(events) + 1,
            "event_type": event_type,
            "summary": summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": self._jsonable(details or {}),
            "snapshot": self._jsonable(snapshot) if snapshot is not None else None,
        }
        events.append(event)

        fd, temp_path = tempfile.mkstemp(dir=str(self.storage_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(events, file, indent=2, ensure_ascii=False)
            os.replace(temp_path, path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
        return event

    def list_events(self, graph_id: str) -> list[dict[str, Any]]:
        path = self._file_path(graph_id)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as file:
            events = json.load(file)
        if not isinstance(events, list):
            raise ValueError("Event history must be a JSON list")
        return events

    def get_event(self, graph_id: str, event_id: str) -> dict[str, Any] | None:
        return next(
            (event for event in self.list_events(graph_id)
             if event.get("event_id") == event_id),
            None,
        )
