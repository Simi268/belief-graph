import json
from pathlib import Path


def main():
    graph_dir = Path("data/graphs")
    files = list(graph_dir.glob("*.json"))

    if not files:
        print("No saved graph files found.")
        raise SystemExit(1)

    for file in files:
        with file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"\nGraph: {data.get('name')}")
        print(f"Graph ID: {data.get('graph_id')}")
        print(f"Nodes: {len(data.get('nodes', []))}")
        print(f"Edges: {len(data.get('edges', []))}")
        print(f"Evidence entries: {len(data.get('evidence', {}))}")
        print(f"Conflict entries: {len(data.get('conflicts', {}))}")


if __name__ == "__main__":
    main()