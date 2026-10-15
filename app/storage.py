import json
import os
import tempfile
from pathlib import Path
from typing import Any

import networkx as nx


class GraphStorage:
    """Persist graph sessions as JSON files."""

    def __init__(self, storage_dir: str = "data/graphs"):
        self.storage_dir = Path(storage_dir).resolve()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, graph_id: str) -> Path:
        # Prevent graph IDs from escaping the storage directory.
        if not graph_id or Path(graph_id).name != graph_id:
            raise ValueError("Invalid graph ID")

        return self.storage_dir / f"{graph_id}.json"

    @staticmethod
    def _serialize(value: Any) -> Any:
        """Convert common Python objects into JSON-compatible values."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, dict):
            return {
                str(key): GraphStorage._serialize(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple, set)):
            return [GraphStorage._serialize(item) for item in value]

        if hasattr(value, "model_dump"):
            return GraphStorage._serialize(value.model_dump(mode="json"))

        if hasattr(value, "dict") and callable(value.dict):
            return GraphStorage._serialize(value.dict())

        if hasattr(value, "value"):
            return GraphStorage._serialize(value.value)

        raise TypeError(
            f"Unsupported value for JSON persistence: {type(value).__name__}"
        )

    def save(
        self,
        graph_id: str,
        name: str,
        graph: nx.DiGraph,
        evidence: dict,
        conflicts: dict,
    ) -> None:
        """Atomically save a graph session."""
        path = self._file_path(graph_id)

        payload = {
            "graph_id": graph_id,
            "name": name,
            "nodes": [
                {
                    "id": node_id,
                    "attributes": self._serialize(attributes),
                }
                for node_id, attributes in graph.nodes(data=True)
            ],
            "edges": [
                {
                    "source": source,
                    "target": target,
                    "attributes": self._serialize(attributes),
                }
                for source, target, attributes in graph.edges(data=True)
            ],
            "graph_attributes": self._serialize(graph.graph),
            "evidence": self._serialize(evidence),
            "conflicts": self._serialize(conflicts),
        }

        file_descriptor, temporary_path = tempfile.mkstemp(
            dir=str(self.storage_dir),
            suffix=".tmp",
        )

        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)

            os.replace(temporary_path, path)

        except Exception:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            raise

    def load(self, graph_id: str) -> dict | None:
        """Load a saved graph session without modifying runtime state."""
        path = self._file_path(graph_id)

        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if payload.get("graph_id") != graph_id:
            raise ValueError("Stored graph ID does not match the requested ID")

        return payload

    def list_graphs(self) -> list[dict]:
        """Return metadata for saved sessions."""
        sessions = []

        for path in sorted(self.storage_dir.glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as file:
                    payload = json.load(file)

                sessions.append({
                    "graph_id": payload["graph_id"],
                    "name": payload.get("name", "Untitled graph"),
                    "node_count": len(payload.get("nodes", [])),
                    "edge_count": len(payload.get("edges", [])),
                })

            except (OSError, json.JSONDecodeError, KeyError):
                # Ignore incomplete or malformed session files.
                continue

        return sessions