import { Fragment, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Brain,
  CheckCircle2,
  CircleDot,
  GitBranch,
  Layers3,
  Network,
  RefreshCw,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const API_BASE = "http://127.0.0.1:8000";

type GraphSummary = {
  graph_id: string;
  name: string;
  node_count: number;
  edge_count: number;
};

type GraphNode = {
  id: string;
  node_type?: string;
  content?: string;
  value?: unknown;
  status?: string;
  confidence?: number;
};

type GraphSnapshot = {
  graph_id: string;
  name: string;
  node_count: number;
  edge_count: number;
  nodes: GraphNode[];
  edges: {
    source: string;
    target: string;
    dependency_type?: string;
  }[];
};

type Health = {
  status: string;
  service: string;
  version: string;
  active_graphs: number;
};

const navigation = [
  { label: "Overview", icon: Layers3 },
  { label: "Belief Graph", icon: Network },
  { label: "Impact Analysis", icon: GitBranch },
  { label: "Recovery", icon: RefreshCw },
];

function statusColor(status?: string) {
  switch (status?.toLowerCase()) {
    case "invalid":
      return "#f87171";
    case "uncertain":
      return "#fbbf24";
    case "requires_reevaluation":
      return "#fb923c";
    default:
      return "#34d399";
  }
}

function nextUnusedId(prefix: string, existingIds: Set<string>): string {
  let index = 1;
  let candidate = `${prefix}_${index}`;
  while (existingIds.has(candidate)) {
    index += 1;
    candidate = `${prefix}_${index}`;
  }
  return candidate;
}

function freshEvidenceId(): string {
  return `E_MISMATCH_${Date.now().toString(36).toUpperCase()}`;
}

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [graphs, setGraphs] = useState<GraphSummary[]>([]);
  const [selectedGraphId, setSelectedGraphId] = useState("");
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [activePage, setActivePage] = useState("Overview");
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [showCreateGraph, setShowCreateGraph] = useState(false);
  const [newGraphName, setNewGraphName] = useState("");
  const [creatingGraph, setCreatingGraph] = useState(false);
  const [showAddNode, setShowAddNode] = useState(false);
  const [showConnectNodes, setShowConnectNodes] = useState(false);
  const [savingNode, setSavingNode] = useState(false);
  const [savingDependency, setSavingDependency] = useState(false);
  const [nodeForm, setNodeForm] = useState({
    node_id: "",
    node_type: "belief",
    content: "",
    value: "",
    confidence: "1",
    source: "frontend",
  });
  const [dependencyForm, setDependencyForm] = useState({
    source_id: "",
    target_id: "",
    dependency_type: "requires",
  });
  const [recoveryForm, setRecoveryForm] = useState({
    action_id: "",
    belief_id: "",
    evidence_id: "E_API_MISMATCH",
    new_belief_id: "B_API_V2",
    new_action_id: "A_API_RETRY",
    environment_version: "v2",
    agent_version: "v1",
  });
  const [recoverySubmitting, setRecoverySubmitting] = useState(false);
  const [recoveryResult, setRecoveryResult] = useState<Record<string, unknown> | null>(null);

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, init);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = body?.detail;
      throw new Error(
        typeof detail === "string"
          ? detail
          : detail
            ? JSON.stringify(detail)
            : `API request failed (${response.status})`,
      );
    }
    return response.json() as Promise<T>;
  }

  async function refreshDashboard(preferredGraphId?: string) {
    setLoading(true);
    setError("");
    try {
      const [healthData, graphData] = await Promise.all([
        request<Health>("/health"),
        request<{ graphs: GraphSummary[] }>("/graphs"),
      ]);
      setHealth(healthData);
      setGraphs(graphData.graphs);

      const desiredId = preferredGraphId ?? selectedGraphId;
      const availableGraphId = graphData.graphs.some(
        (graph) => graph.graph_id === desiredId,
      )
        ? desiredId
        : graphData.graphs[0]?.graph_id ?? "";

      setSelectedGraphId(availableGraphId);
      if (availableGraphId) {
        const graph = await request<GraphSnapshot>(
          `/graphs/${availableGraphId}`,
        );
        setSnapshot(graph);
      } else {
        setSnapshot(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to the API.");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshDashboard("");
    // Initial load only; manual refresh is available in the toolbar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep recovery IDs unique as graphs are selected or refreshed. The API
  // remains the final authority and also validates collisions server-side.
  useEffect(() => {
    if (!snapshot) return;
    const existingIds = new Set(snapshot.nodes.map((node) => node.id));
    setRecoveryForm((current) => ({
      ...current,
      evidence_id: freshEvidenceId(),
      new_belief_id: nextUnusedId("B_REVISED", existingIds),
      new_action_id: nextUnusedId("A_RETRY", existingIds),
    }));
  }, [snapshot?.graph_id, snapshot?.nodes]);

  async function selectGraph(graphId: string) {
    setSelectedGraphId(graphId);
    setSelectedNodeId("");
    setError("");
    if (!graphId) {
      setSnapshot(null);
      return;
    }
    try {
      setSnapshot(await request<GraphSnapshot>(`/graphs/${graphId}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load graph.");
    }
  }

  async function submitRecovery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedGraphId || !snapshot) {
      setError("Select a graph before running recovery.");
      return;
    }
    if (!recoveryForm.action_id || !recoveryForm.belief_id) {
      setError("Select the failed action and the belief it relied on.");
      return;
    }
    const existingIds = new Set(snapshot.nodes.map((node) => node.id));
    const submittedBeliefId = recoveryForm.new_belief_id.trim();
    const submittedActionId = recoveryForm.new_action_id.trim();
    const safeBeliefId = existingIds.has(submittedBeliefId)
      ? nextUnusedId("B_REVISED", existingIds)
      : submittedBeliefId;
    const idsWithBelief = new Set(existingIds);
    idsWithBelief.add(safeBeliefId);
    const safeActionId = idsWithBelief.has(submittedActionId)
      ? nextUnusedId("A_RETRY", idsWithBelief)
      : submittedActionId;

    if (safeBeliefId === safeActionId) {
      setError("The replacement belief ID and action ID must be different.");
      return;
    }

    // Show the collision-free IDs that will be submitted.
    setRecoveryForm((current) => ({
      ...current,
      evidence_id: current.evidence_id.trim() || freshEvidenceId(),
      new_belief_id: safeBeliefId,
      new_action_id: safeActionId,
    }));

    setRecoverySubmitting(true);
    setError("");
    setSuccessMessage("");
    setRecoveryResult(null);
    try {
      const payload = await request<{
        graph_id: string;
        result: Record<string, unknown>;
        graph: GraphSnapshot;
      }>(`/graphs/${selectedGraphId}/recover`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_id: recoveryForm.action_id,
          evidence_id: recoveryForm.evidence_id.trim() || freshEvidenceId(),
          new_belief_id: safeBeliefId,
          new_action_id: safeActionId,
          action_result: {
            belief_id: recoveryForm.belief_id,
            action_id: recoveryForm.action_id,
            assumed_version: recoveryForm.agent_version.trim(),
            environment_result: {
              success: false,
              expected: recoveryForm.environment_version.trim(),
              received: recoveryForm.agent_version.trim(),
              error: "API version mismatch",
            },
          },
        }),
      });
      setRecoveryResult(payload.result);
      setSnapshot(payload.graph);
      setSuccessMessage("Recovery workflow completed. Review the revision and selective recovery plan below.");
      await refreshDashboard(selectedGraphId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recovery request failed.");
    } finally {
      setRecoverySubmitting(false);
    }
  }

  async function createGraph() {
    const name = newGraphName.trim();
    if (!name) {
      setError("Please enter a graph name.");
      return;
    }
    setCreatingGraph(true);
    setError("");
    setSuccessMessage("");
    try {
      const response = await fetch(`${API_BASE}/graphs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Unable to create graph.",
        );
      }
      setNewGraphName("");
      setShowCreateGraph(false);
      setSelectedNodeId("");
      await refreshDashboard(data.graph_id);
      setSuccessMessage(`Graph "${name}" created successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create graph.");
    } finally {
      setCreatingGraph(false);
    }
  }

  async function createNode() {
    if (!selectedGraphId) {
      setError("Create or select a graph first.");
      return;
    }
    if (!nodeForm.node_id.trim() || !nodeForm.content.trim()) {
      setError("Node ID and content are required.");
      return;
    }
    setSavingNode(true);
    setError("");
    setSuccessMessage("");
    try {
      const response = await fetch(`${API_BASE}/graphs/${selectedGraphId}/nodes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: nodeForm.node_id.trim(),
          node_type: nodeForm.node_type,
          content: nodeForm.content.trim(),
          value: nodeForm.value.trim() || null,
          confidence: Number(nodeForm.confidence),
          source: nodeForm.source.trim() || "frontend",
        }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : `Node creation failed (${response.status}).`);
      }
      const createdId = nodeForm.node_id.trim();
      setNodeForm({ node_id: "", node_type: "belief", content: "", value: "", confidence: "1", source: "frontend" });
      setShowAddNode(false);
      await refreshDashboard(selectedGraphId);
      setSuccessMessage(`Node ${createdId} added successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create node.");
    } finally {
      setSavingNode(false);
    }
  }

  async function createDependency() {
    if (!selectedGraphId) {
      setError("Create or select a graph first.");
      return;
    }
    if (!dependencyForm.source_id || !dependencyForm.target_id) {
      setError("Select both a source and a target node.");
      return;
    }
    if (dependencyForm.source_id === dependencyForm.target_id) {
      setError("A node cannot depend on itself.");
      return;
    }
    setSavingDependency(true);
    setError("");
    setSuccessMessage("");
    try {
      const response = await fetch(`${API_BASE}/graphs/${selectedGraphId}/dependencies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(dependencyForm),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : `Dependency creation failed (${response.status}).`);
      }
      const source = dependencyForm.source_id;
      const target = dependencyForm.target_id;
      setShowConnectNodes(false);
      setDependencyForm({ source_id: "", target_id: "", dependency_type: "requires" });
      await refreshDashboard(selectedGraphId);
      setSuccessMessage(`Dependency ${source} → ${target} created successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create dependency.");
    } finally {
      setSavingDependency(false);
    }
  }

  // Trace downstream dependencies from the selected node. This is visual
  // guidance only; backend impact classifications remain authoritative.
  const tracedNodeIds = useMemo(() => {
    const reached = new Set<string>();
    if (!snapshot || !selectedNodeId) return reached;
    const queue = [selectedNodeId];
    while (queue.length) {
      const current = queue.shift()!;
      for (const edge of snapshot.edges) {
        if (edge.source !== current || reached.has(edge.target) || edge.target === selectedNodeId) continue;
        reached.add(edge.target);
        queue.push(edge.target);
      }
    }
    return reached;
  }, [snapshot, selectedNodeId]);

  const flowNodes: Node[] = useMemo(() => {
    if (!snapshot) return [];
    return snapshot.nodes.map((node, index) => {
      const isSelected = node.id === selectedNodeId;
      const isTraced = tracedNodeIds.has(node.id);
      const isDimmed = Boolean(selectedNodeId) && !isSelected && !isTraced;
      const baseColor = statusColor(node.status);
      return {
        id: node.id,
        position: { x: (index % 3) * 280, y: Math.floor(index / 3) * 150 },
        data: {
          label: (
            <div className="node-content">
              <div className="node-heading">
                <span>{node.node_type ?? "Node"}</span>
                <span className="node-status" style={{ color: baseColor }}>{node.status ?? "unknown"}</span>
              </div>
              <strong>{node.id}</strong>
              <p>{node.content ?? "No description available"}</p>
              {isSelected && <small style={{ color: "#6ee7b7" }}>Selected · trace root</small>}
              {!isSelected && isTraced && <small style={{ color: "#fbbf24" }}>Downstream dependency</small>}
            </div>
          ),
        },
        style: {
          width: 235,
          padding: 12,
          borderRadius: 12,
          background: isSelected ? "#15352f" : "#171e29",
          color: "#e5e7eb",
          opacity: isDimmed ? 0.38 : 1,
          border: `2px solid ${isSelected ? "#34d399" : isTraced ? "#fbbf24" : `${baseColor}66`}`,
          boxShadow: isSelected ? "0 0 0 3px #34d39922" : "none",
        },
      };
    });
  }, [snapshot, selectedNodeId, tracedNodeIds]);

  const flowEdges: Edge[] = useMemo(
    () => (snapshot?.edges ?? []).map((edge, index) => {
      const isTraceEdge = Boolean(selectedNodeId) &&
        (edge.source === selectedNodeId || tracedNodeIds.has(edge.source)) &&
        tracedNodeIds.has(edge.target);
      return {
        id: `${edge.source}-${edge.target}-${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.dependency_type ?? "",
        animated: isTraceEdge,
        style: {
          stroke: isTraceEdge ? "#fbbf24" : "#64748b",
          strokeWidth: isTraceEdge ? 2.6 : 1.5,
          opacity: selectedNodeId && !isTraceEdge ? 0.2 : 1,
        },
        labelStyle: { fill: isTraceEdge ? "#fbbf24" : "#cbd5e1", fontSize: 10 },
      };
    }),
    [snapshot, selectedNodeId, tracedNodeIds],
  );

  const selectedNode = snapshot?.nodes.find((node) => node.id === selectedNodeId);

  return (
    <div className="app-shell">
      {showCreateGraph && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !creatingGraph) {
              setShowCreateGraph(false);
            }
          }}
        >
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="create-graph-title">
            <div className="modal-title-row">
              <div className="modal-icon"><Network size={20} /></div>
              <button
                className="icon-button modal-close"
                aria-label="Close dialog"
                onClick={() => setShowCreateGraph(false)}
                disabled={creatingGraph}
              >
                <X size={17} />
              </button>
            </div>
            <h3 id="create-graph-title">Create a new graph</h3>
            <p>Start a workspace for beliefs, dependencies, and recovery analysis.</p>
            <label htmlFor="new-graph-name">Graph name</label>
            <input
              id="new-graph-name"
              autoFocus
              maxLength={150}
              placeholder="e.g. API Failure Recovery"
              value={newGraphName}
              onChange={(event) => setNewGraphName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !creatingGraph) void createGraph();
                if (event.key === "Escape" && !creatingGraph) setShowCreateGraph(false);
              }}
            />
            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setShowCreateGraph(false)} disabled={creatingGraph}>
                Cancel
              </button>
              <button className="primary-button" onClick={() => void createGraph()} disabled={creatingGraph || !newGraphName.trim()}>
                {creatingGraph ? "Creating…" : "Create Graph"}
                {!creatingGraph && <ArrowRight size={15} />}
              </button>
            </div>
          </div>
        </div>
      )}

      {showAddNode && (
        <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !savingNode) setShowAddNode(false); }}>
          <div className="modal form-modal" role="dialog" aria-modal="true" aria-labelledby="add-node-title">
            <div className="modal-title-row"><div className="modal-icon"><GitBranch size={20} /></div><button className="icon-button modal-close" aria-label="Close dialog" onClick={() => setShowAddNode(false)} disabled={savingNode}><X size={17} /></button></div>
            <h3 id="add-node-title">Add a graph node</h3>
            <p>Create a belief, conclusion, plan, or action in the selected graph.</p>
            <div className="form-grid">
              <div className="form-field"><label htmlFor="node-id">Node ID *</label><input id="node-id" maxLength={100} placeholder="e.g. B2" value={nodeForm.node_id} onChange={(event) => setNodeForm({ ...nodeForm, node_id: event.target.value })} /></div>
              <div className="form-field"><label htmlFor="node-type">Node type *</label><select id="node-type" value={nodeForm.node_type} onChange={(event) => setNodeForm({ ...nodeForm, node_type: event.target.value })}><option value="belief">Belief</option><option value="conclusion">Conclusion</option><option value="plan">Plan</option><option value="action">Action</option></select></div>
              <div className="form-field full-field"><label htmlFor="node-content">Description *</label><textarea id="node-content" rows={3} maxLength={1000} placeholder="Describe what this node represents" value={nodeForm.content} onChange={(event) => setNodeForm({ ...nodeForm, content: event.target.value })} /></div>
              <div className="form-field"><label htmlFor="node-value">Value (optional)</label><input id="node-value" maxLength={250} placeholder="e.g. v2" value={nodeForm.value} onChange={(event) => setNodeForm({ ...nodeForm, value: event.target.value })} /></div>
              <div className="form-field"><label htmlFor="node-confidence">Confidence (0–1)</label><input id="node-confidence" type="number" min="0" max="1" step="0.05" value={nodeForm.confidence} onChange={(event) => setNodeForm({ ...nodeForm, confidence: event.target.value })} /></div>
              <div className="form-field full-field"><label htmlFor="node-source">Source</label><input id="node-source" maxLength={100} value={nodeForm.source} onChange={(event) => setNodeForm({ ...nodeForm, source: event.target.value })} /></div>
            </div>
            <div className="modal-actions"><button className="secondary-button" onClick={() => setShowAddNode(false)} disabled={savingNode}>Cancel</button><button className="primary-button" onClick={() => void createNode()} disabled={savingNode || !nodeForm.node_id.trim() || !nodeForm.content.trim() || Number(nodeForm.confidence) < 0 || Number(nodeForm.confidence) > 1}>{savingNode ? "Adding…" : "Add Node"}<ArrowRight size={15} /></button></div>
          </div>
        </div>
      )}

      {showConnectNodes && (
        <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !savingDependency) setShowConnectNodes(false); }}>
          <div className="modal form-modal" role="dialog" aria-modal="true" aria-labelledby="connect-nodes-title">
            <div className="modal-title-row"><div className="modal-icon"><Network size={20} /></div><button className="icon-button modal-close" aria-label="Close dialog" onClick={() => setShowConnectNodes(false)} disabled={savingDependency}><X size={17} /></button></div>
            <h3 id="connect-nodes-title">Connect nodes</h3>
            <p>Define how one node relates to another. The source points toward the target.</p>
            <div className="form-grid">
              <div className="form-field"><label htmlFor="dependency-source">Source node *</label><select id="dependency-source" value={dependencyForm.source_id} onChange={(event) => setDependencyForm({ ...dependencyForm, source_id: event.target.value })}><option value="">Select source</option>{(snapshot?.nodes ?? []).map((node) => <option key={node.id} value={node.id}>{node.id} — {node.content ?? node.node_type ?? "Node"}</option>)}</select></div>
              <div className="form-field"><label htmlFor="dependency-target">Target node *</label><select id="dependency-target" value={dependencyForm.target_id} onChange={(event) => setDependencyForm({ ...dependencyForm, target_id: event.target.value })}><option value="">Select target</option>{(snapshot?.nodes ?? []).map((node) => <option key={node.id} value={node.id}>{node.id} — {node.content ?? node.node_type ?? "Node"}</option>)}</select></div>
              <div className="form-field full-field"><label htmlFor="dependency-type">Relationship type *</label><select id="dependency-type" value={dependencyForm.dependency_type} onChange={(event) => setDependencyForm({ ...dependencyForm, dependency_type: event.target.value })}><option value="requires">Requires</option><option value="supports">Supports</option><option value="context">Context</option><option value="derived_from">Derived from</option><option value="contradicts">Contradicts</option></select></div>
            </div>
            <div className="dependency-preview">{dependencyForm.source_id || "Source"} <ArrowRight size={15} /> <span>{dependencyForm.dependency_type}</span> <ArrowRight size={15} /> {dependencyForm.target_id || "Target"}</div>
            <div className="modal-actions"><button className="secondary-button" onClick={() => setShowConnectNodes(false)} disabled={savingDependency}>Cancel</button><button className="primary-button" onClick={() => void createDependency()} disabled={savingDependency || !dependencyForm.source_id || !dependencyForm.target_id || dependencyForm.source_id === dependencyForm.target_id}>{savingDependency ? "Connecting…" : "Connect Nodes"}<ArrowRight size={15} /></button></div>
          </div>
        </div>
      )}

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Brain size={22} /></div>
          <div><h1>Belief-Graph</h1><span>Agent intelligence platform</span></div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="navigation">
          {navigation.map(({ label, icon: Icon }) => (
            <button key={label} className={`nav-item ${activePage === label ? "active" : ""}`} onClick={() => setActivePage(label)}>
              <Icon size={18} /><span>{label}</span>{activePage === label && <span className="active-indicator" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection-indicator">
            <span className={`connection-dot ${health?.status === "healthy" ? "online" : ""}`} />
            <div><strong>Backend connection</strong><span>{health?.status === "healthy" ? "Connected" : "Disconnected"}</span></div>
          </div>
          <p>Belief-Graph · v0.2.0</p>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><ArrowRight size={14} /><strong>{activePage}</strong></div>
          <div className="topbar-actions">
            <span className="environment-badge"><CircleDot size={12} />Local environment</span>
            <button className="icon-button" onClick={() => void refreshDashboard()} title="Refresh dashboard"><RefreshCw size={17} /></button>
          </div>
        </header>

        <div className="page-container">
          <section className="page-heading">
            <div>
              <div className="eyebrow"><Workflow size={14} />AI AGENT OBSERVABILITY</div>
              <h2>{activePage}</h2>
              <p>Understand belief changes, dependency impact, and selective recovery.</p>
            </div>
            <div className="graph-actions">
              <div className="graph-selector">
                <label htmlFor="graph-select">Graph session</label>
                <select id="graph-select" value={selectedGraphId} onChange={(event) => void selectGraph(event.target.value)}>
                  <option value="">Select a graph</option>
                  {graphs.map((graph) => <option key={graph.graph_id} value={graph.graph_id}>{graph.name}</option>)}
                </select>
              </div>
              <button className="secondary-button" disabled={!selectedGraphId} onClick={() => { setError(""); setSuccessMessage(""); setShowAddNode(true); }}>
                + Add Node
              </button>
              <button className="secondary-button" disabled={!selectedGraphId || (snapshot?.nodes.length ?? 0) < 2} onClick={() => { setError(""); setSuccessMessage(""); setShowConnectNodes(true); }}>
                Connect Nodes
              </button>
              <button className="primary-button" onClick={() => { setError(""); setSuccessMessage(""); setNewGraphName(""); setShowCreateGraph(true); }}>
                + Create Graph
              </button>
            </div>
          </section>

          {error && <div className="alert alert-error"><AlertTriangle size={18} /><div><strong>Unable to complete request</strong><p>{error}</p><span>Check that the FastAPI server is running, then try again.</span></div><button className="text-button" onClick={() => setError("")}>Dismiss</button></div>}
          {successMessage && <div className="success-banner"><CheckCircle2 size={18} /><span>{successMessage}</span><button className="text-button" onClick={() => setSuccessMessage("")}>Dismiss</button></div>}
          {loading && <div className="loading-banner"><Activity size={17} />Connecting to Belief-Graph API…</div>}

          <section className="stats-grid">
            <StatCard icon={<Network size={19} />} label="Graph nodes" value={snapshot?.node_count ?? 0} detail="Current graph session" />
            <StatCard icon={<GitBranch size={19} />} label="Dependencies" value={snapshot?.edge_count ?? 0} detail="Directed relationships" />
            <StatCard icon={<Brain size={19} />} label="Active graphs" value={health?.active_graphs ?? 0} detail="Backend sessions" />
            <StatCard icon={<ShieldCheck size={19} />} label="API status" value={health?.status === "healthy" ? "Healthy" : "Offline"} detail={health?.service ?? "Waiting for backend"} positive={health?.status === "healthy"} />
          </section>

          {activePage === "Overview" && (
            <section className="overview-grid">
              <div className="panel graph-panel">
                <PanelHeading title="Dependency graph" subtitle={snapshot ? snapshot.name : "Create a graph to get started."} icon={<Network size={18} />} />
                {flowNodes.length > 0 ? (
                  <div className="flow-container"><ReactFlow nodes={flowNodes} edges={flowEdges} fitView onNodeClick={(_, node) => setSelectedNodeId(node.id)}><Background color="#334155" gap={24} /><Controls /><MiniMap nodeColor={(node) => statusColor(snapshot?.nodes.find((item) => item.id === node.id)?.status)} /></ReactFlow></div>
                ) : (
                  <EmptyState title="No graph to visualize" description="Create a graph using the button above. Then add nodes and dependencies through the API." />
                )}
                {selectedNode && <SelectedNode node={selectedNode} nodes={snapshot?.nodes ?? []} edges={snapshot?.edges ?? []} onClose={() => setSelectedNodeId("")} onTrace={() => setActivePage("Impact Analysis")} />}
              </div>
              <div className="right-column">
                <div className="panel">
                  <PanelHeading title="System health" subtitle="Live backend connectivity" icon={<Activity size={18} />} />
                  <div className="health-row"><div className="health-icon"><CheckCircle2 size={20} /></div><div className="health-copy"><strong>REST API</strong><span>{health?.status === "healthy" ? "Responding normally" : "Connection unavailable"}</span></div><span className={`status-pill ${health?.status === "healthy" ? "success" : "danger"}`}>{health?.status === "healthy" ? "Online" : "Offline"}</span></div>
                  <div className="health-details"><div><span>Service</span><strong>{health?.service ?? "—"}</strong></div><div><span>API version</span><strong>{health?.version ?? "—"}</strong></div><div><span>Endpoint</span><strong>127.0.0.1:8000</strong></div></div>
                </div>
                <div className="panel">
                  <PanelHeading title="Graph sessions" subtitle="Available in this backend process" icon={<Layers3 size={18} />} />
                  {graphs.length ? <div className="session-list">{graphs.map((graph) => <button key={graph.graph_id} className={`session-item ${selectedGraphId === graph.graph_id ? "selected" : ""}`} onClick={() => void selectGraph(graph.graph_id)}><div className="session-icon"><Network size={17} /></div><div className="session-copy"><strong>{graph.name}</strong><span>{graph.node_count} nodes · {graph.edge_count} edges</span></div><ArrowRight size={15} /></button>)}</div> : <EmptyState title="No sessions found" description="Create your first graph using the button above." />}
                </div>
              </div>
            </section>
          )}

          {activePage === "Belief Graph" && <section className="panel full-panel"><PanelHeading title="Graph explorer" subtitle="Inspect nodes and their directed dependencies" icon={<Network size={18} />} />{flowNodes.length > 0 ? <div className="flow-container large-flow"><ReactFlow nodes={flowNodes} edges={flowEdges} fitView onNodeClick={(_, node) => setSelectedNodeId(node.id)}><Background color="#334155" gap={24} /><Controls /><MiniMap /></ReactFlow></div> : <EmptyState title="No graph selected" description="Create a graph, then add nodes and dependencies through the API." />}{selectedNode && <SelectedNode node={selectedNode} nodes={snapshot?.nodes ?? []} edges={snapshot?.edges ?? []} onClose={() => setSelectedNodeId("")} onTrace={() => setActivePage("Impact Analysis")} />}</section>}
          {activePage === "Impact Analysis" && <ImpactPanel graphId={selectedGraphId} nodes={snapshot?.nodes ?? []} edges={snapshot?.edges ?? []} onError={setError} />}
          {activePage === "Recovery" && (
            <section className="panel full-panel">
              <PanelHeading title="Recovery intelligence" subtitle="Simulate a failure, revise the belief, and inspect the selective recovery plan" icon={<RefreshCw size={18} />} />
              {!selectedGraphId || !snapshot ? (
                <EmptyState title="Select a graph first" description="Choose or create a graph before running the recovery workflow." />
              ) : (
                <>
                  <div className="recovery-intro" style={{ marginBottom: 22 }}>
                    <div className="recovery-icon"><ShieldCheck size={24} /></div>
                    <div>
                      <h3>API version mismatch</h3>
                      <p>Use this guided workflow to submit failure evidence to the real backend. The API revises the old belief, calculates affected nodes, and creates a replacement action when the dependency graph supports it.</p>
                      <p className="muted-note">Choose an existing action and the belief it depends on. New node IDs must not already exist in this graph.</p>
                    </div>
                  </div>
                  <form onSubmit={(event) => void submitRecovery(event)} style={{ display: "grid", gap: 18 }}>
                    <div className="recovery-form-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
                      <label className="form-field">
                        <span>Failed action</span>
                        <select required value={recoveryForm.action_id} onChange={(event) => setRecoveryForm((f) => ({ ...f, action_id: event.target.value }))}>
                          <option value="">Select action node</option>
                          {snapshot.nodes.filter((node) => node.node_type?.toLowerCase() === "action").map((node) => <option key={node.id} value={node.id}>{node.id} — {node.content ?? "Action"}</option>)}
                        </select>
                      </label>
                      <label className="form-field">
                        <span>Belief used by action</span>
                        <select required value={recoveryForm.belief_id} onChange={(event) => setRecoveryForm((f) => ({ ...f, belief_id: event.target.value }))}>
                          <option value="">Select belief node</option>
                          {snapshot.nodes.filter((node) => node.node_type?.toLowerCase() === "belief").map((node) => <option key={node.id} value={node.id}>{node.id} — {node.content ?? "Belief"}</option>)}
                        </select>
                      </label>
                      <label className="form-field">
                        <span>Environment's actual version</span>
                        <input required value={recoveryForm.environment_version} onChange={(event) => setRecoveryForm((f) => ({ ...f, environment_version: event.target.value }))} placeholder="e.g. v2" />
                      </label>
                      <label className="form-field">
                        <span>Version the agent assumed</span>
                        <input required value={recoveryForm.agent_version} onChange={(event) => setRecoveryForm((f) => ({ ...f, agent_version: event.target.value }))} placeholder="e.g. v1" />
                      </label>
                      <label className="form-field">
                        <span>Evidence ID</span>
                        <input required value={recoveryForm.evidence_id} onChange={(event) => setRecoveryForm((f) => ({ ...f, evidence_id: event.target.value }))} />
                      </label>
                      <label className="form-field">
                        <span>Replacement belief ID</span>
                        <input required value={recoveryForm.new_belief_id} onChange={(event) => setRecoveryForm((f) => ({ ...f, new_belief_id: event.target.value }))} />
                      </label>
                      <label className="form-field">
                        <span>Replacement action ID</span>
                        <input required value={recoveryForm.new_action_id} onChange={(event) => setRecoveryForm((f) => ({ ...f, new_action_id: event.target.value }))} />
                      </label>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                      <button type="submit" className="primary-button" disabled={recoverySubmitting || snapshot.nodes.filter((node) => node.node_type?.toLowerCase() === "action").length === 0 || snapshot.nodes.filter((node) => node.node_type?.toLowerCase() === "belief").length === 0}>
                        {recoverySubmitting ? "Running recovery…" : "Run recovery workflow"} <ArrowRight size={15} />
                      </button>
                      <button type="button" className="secondary-button" disabled={recoverySubmitting} onClick={() => { const existingIds = new Set((snapshot?.nodes ?? []).map((node) => node.id)); setRecoveryForm({ action_id: "", belief_id: "", evidence_id: freshEvidenceId(), new_belief_id: nextUnusedId("B_REVISED", existingIds), new_action_id: nextUnusedId("A_RETRY", existingIds), environment_version: "v2", agent_version: "v1" }); setRecoveryResult(null); setError(""); setSuccessMessage(""); }}>
                        Reset form with fresh IDs
                      </button>
                      <span className="muted-note">The selected action should depend on the selected belief for selective replanning.</span>
                    </div>
                  </form>
                  {recoveryResult && (
                    <div style={{ marginTop: 24, display: "grid", gap: 14 }}>
                      <div className={recoveryResult.status === "recovered" ? "success-banner" : "warning-banner"}>
                        {recoveryResult.status === "recovered" ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
                        <span>
                          {recoveryResult.status === "recovered"
                            ? "Recovery verified: the replacement action executed and the environment confirmed success."
                            : recoveryResult.status === "retry_failed"
                              ? "The replacement action executed but failed. Inspect the execution result below."
                              : recoveryResult.status === "recovery_planned"
                                ? "Recovery was planned, but execution has not been verified."
                                : `Recovery result status: ${String(recoveryResult.status ?? "unknown")}. Inspect the details below.`}
                        </span>
                      </div>
                      <div className="panel" style={{ padding: 18 }}>
                        <PanelHeading title="Recovery result" subtitle={`Status: ${String(recoveryResult.status ?? "completed")}`} icon={<ShieldCheck size={18} />} />
                        <pre style={{ margin: "16px 0 0", padding: 16, borderRadius: 10, overflowX: "auto", background: "rgba(15, 23, 42, 0.72)", color: "#dbeafe", fontSize: 12, lineHeight: 1.6, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(recoveryResult, null, 2)}</pre>
                      </div>
                    </div>
                  )}
                </>
              )}
            </section>
          )}

          <footer className="footer"><span><span className="footer-dot" />Belief-Graph developer workspace</span><span>Built for AI agent observability and recovery</span></footer>
        </div>
      </main>
    </div>
  );
}

function StatCard({ icon, label, value, detail, positive }: { icon: ReactNode; label: string; value: string | number; detail: string; positive?: boolean }) {
  return <div className="stat-card"><div className="stat-card-top"><div className="stat-icon">{icon}</div>{positive && <span className="mini-positive"><CheckCircle2 size={12} />Live</span>}</div><span className="stat-label">{label}</span><strong className="stat-value">{value}</strong><span className="stat-detail">{detail}</span></div>;
}

function PanelHeading({ title, subtitle, icon }: { title: string; subtitle: string; icon: ReactNode }) {
  return <div className="panel-heading"><div className="panel-heading-icon">{icon}</div><div><h3>{title}</h3><p>{subtitle}</p></div></div>;
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="empty-state"><div className="empty-icon"><Network size={24} /></div><strong>{title}</strong><p>{description}</p></div>;
}

function SelectedNode({
  node, nodes, edges, onClose, onTrace,
}: {
  node: GraphNode;
  nodes: GraphNode[];
  edges: GraphEdge[];
  onClose: () => void;
  onTrace: () => void;
}) {
  const incoming = edges.filter((edge) => edge.target === node.id);
  const outgoing = edges.filter((edge) => edge.source === node.id);
  const labelFor = (id: string) => {
    const item = nodes.find((candidate) => candidate.id === id);
    return `${id}${item?.node_type ? ` · ${item.node_type}` : ""}`;
  };
  return (
    <div className="selected-node" style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div><span>Selected node</span><strong>{node.id}</strong></div>
        <button className="text-button" onClick={onClose}>Close</button>
      </div>
      <p>{node.content ?? "No description"}</p>
      <div className="causal-detail-grid">
        <div><span>Type</span><strong>{node.node_type ?? "unknown"}</strong></div>
        <div><span>Status</span><strong style={{ color: statusColor(node.status) }}>{node.status ?? "unknown"}</strong></div>
        <div><span>Confidence</span><strong>{typeof node.confidence === "number" ? node.confidence.toFixed(2) : "Not provided"}</strong></div>
        <div><span>Value</span><strong>{node.value === undefined || node.value === null ? "Not provided" : String(node.value)}</strong></div>
      </div>
      <div className="causal-detail-grid">
        <div><span>Incoming dependencies ({incoming.length})</span><strong>{incoming.length ? incoming.map((edge) => `${labelFor(edge.source)} [${edge.dependency_type ?? "dependency"}]`).join(" · ") : "None"}</strong></div>
        <div><span>Outgoing dependencies ({outgoing.length})</span><strong>{outgoing.length ? outgoing.map((edge) => `${labelFor(edge.target)} [${edge.dependency_type ?? "dependency"}]`).join(" · ") : "None"}</strong></div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        <button className="primary-button" onClick={onTrace}><GitBranch size={15} /> Trace failure impact <ArrowRight size={15} /></button>
        <span className="muted-note">Graph highlighting is a dependency trace; backend classifications remain authoritative.</span>
      </div>
    </div>
  );
}

type ImpactDetail = {
  impact?: string;
  affected_by?: string[];
  sources?: string[];
  source?: string;
  depth?: number;
  dependency_type?: string;
  dependency_types?: string[];
  source_status?: string;
};

type GraphEdge = {
  source: string;
  target: string;
  dependency_type?: string;
};

function findCausalPath(
  rootId: string,
  targetId: string,
  edges: GraphEdge[],
): string[] {
  if (rootId === targetId) return [rootId];

  const queue: string[][] = [[rootId]];
  const visited = new Set<string>([rootId]);

  while (queue.length > 0) {
    const path = queue.shift()!;
    const current = path[path.length - 1];

    for (const edge of edges.filter((item) => item.source === current)) {
      if (visited.has(edge.target)) continue;
      const nextPath = [...path, edge.target];
      if (edge.target === targetId) return nextPath;
      visited.add(edge.target);
      queue.push(nextPath);
    }
  }

  return [];
}

function ImpactPanel({
  graphId,
  nodes,
  edges,
  onError,
}: {
  graphId: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  onError: (message: string) => void;
}) {
  const [changedNodeId, setChangedNodeId] = useState("");
  const [impact, setImpact] = useState<Record<string, ImpactDetail> | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [expandedNodeId, setExpandedNodeId] = useState<string | null>(null);

  useEffect(() => {
    setChangedNodeId("");
    setImpact(null);
    setExpandedNodeId(null);
  }, [graphId]);

  async function analyze() {
    if (!graphId || !changedNodeId) {
      onError("Select a graph and a changed node first.");
      return;
    }

    setSubmitting(true);
    onError("");
    setExpandedNodeId(null);

    try {
      const response = await fetch(`${API_BASE}/graphs/${graphId}/analyze-impact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ changed_node_ids: [changedNodeId] }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : `Impact analysis failed (${response.status}).`,
        );
      }
      setImpact(data.impact as Record<string, ImpactDetail>);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Impact analysis failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const impactEntries = Object.entries(impact ?? {}).filter(
    ([, detail]) => detail && typeof detail === "object" && "impact" in detail,
  );

  const changedNode = nodes.find((node) => node.id === changedNodeId);

  return (
    <section className="panel full-panel causal-explorer">
      <PanelHeading
        title="Causal Failure Explorer"
        subtitle="Trace the dependency path from a changed node to each affected node."
        icon={<GitBranch size={18} />}
      />

      <div className="analysis-controls">
        <div className="form-field">
          <label htmlFor="changed-node">Changed node / root cause</label>
          <select
            id="changed-node"
            value={changedNodeId}
            onChange={(event) => {
              setChangedNodeId(event.target.value);
              setImpact(null);
              setExpandedNodeId(null);
            }}
          >
            <option value="">Select a node</option>
            {nodes.map((node) => (
              <option key={node.id} value={node.id}>
                {node.id} — {node.content ?? node.node_type ?? "Node"}
              </option>
            ))}
          </select>
        </div>
        <button
          className="primary-button"
          disabled={submitting || !graphId || !changedNodeId}
          onClick={() => void analyze()}
        >
          {submitting ? "Tracing impact…" : "Trace Causal Impact"}
          <ArrowRight size={15} />
        </button>
      </div>

      {impact ? (
        <>
          <div className="causal-root-card">
            <div className="causal-root-icon"><AlertTriangle size={18} /></div>
            <div>
              <span className="causal-kicker">ANALYSIS ROOT</span>
              <strong>{changedNode?.id ?? changedNodeId} · {changedNode?.node_type ?? "Node"}</strong>
              <p>{changedNode?.content ?? "Selected node"}</p>
            </div>
            <span className="status-pill danger">Change source</span>
          </div>

          <div className="causal-summary-grid">
            <div className="causal-summary-card">
              <span>Affected downstream nodes</span>
              <strong>{impactEntries.length}</strong>
            </div>
            <div className="causal-summary-card">
              <span>Invalidated</span>
              <strong>{impactEntries.filter(([, item]) => item.impact?.toLowerCase() === "invalid").length}</strong>
            </div>
            <div className="causal-summary-card">
              <span>Needs review / uncertain</span>
              <strong>{impactEntries.filter(([, item]) => ["requires_reevaluation", "uncertain"].includes(item.impact?.toLowerCase() ?? "")).length}</strong>
            </div>
          </div>

          <div className="causal-results-heading">
            <div>
              <h4>Why each node is affected</h4>
              <p>Expand a result to inspect its dependency path and backend-provided impact details.</p>
            </div>
            <span>{impactEntries.length} result{impactEntries.length === 1 ? "" : "s"}</span>
          </div>

          {impactEntries.length > 0 ? (
            <div className="causal-result-list">
              {impactEntries
                .sort((a, b) => (a[1].depth ?? 0) - (b[1].depth ?? 0))
                .map(([nodeId, detail]) => {
                  const node = nodes.find((item) => item.id === nodeId);
                  const color = statusColor(detail.impact);
                  const path = findCausalPath(changedNodeId, nodeId, edges);
                  const causeIds = detail.affected_by ?? detail.sources ?? (detail.source ? [detail.source] : []);
                  const isExpanded = expandedNodeId === nodeId;

                  return (
                    <article className="causal-result-card" key={nodeId}>
                      <button
                        className="causal-result-button"
                        onClick={() => setExpandedNodeId(isExpanded ? null : nodeId)}
                        aria-expanded={isExpanded}
                      >
                        <span className="impact-dot" style={{ background: color }} />
                        <span className="causal-result-main">
                          <strong>{nodeId} <span className="causal-node-type">{node?.node_type ?? "Node"}</span></strong>
                          <span>{node?.content ?? "No description available"}</span>
                          <small>
                            {detail.depth !== undefined ? `Depth ${detail.depth}` : "Depth not provided"}
                            {causeIds.length ? ` · Cause: ${causeIds.join(", ")}` : ""}
                          </small>
                        </span>
                        <span
                          className="status-pill"
                          style={{ borderColor: `${color}66`, color }}
                        >
                          {(detail.impact ?? "unknown").replaceAll("_", " ")}
                        </span>
                        <span className="causal-expand">{isExpanded ? "−" : "+"}</span>
                      </button>

                      {isExpanded && (
                        <div className="causal-detail">
                          <h5>Dependency path</h5>
                          {path.length > 1 ? (
                            <div className="causal-path" aria-label={`Causal path to ${nodeId}`}>
                              {path.map((pathNodeId, index) => {
                                const pathNode = nodes.find((item) => item.id === pathNodeId);
                                const connectingEdge = index > 0
                                  ? edges.find((edge) => edge.source === path[index - 1] && edge.target === pathNodeId)
                                  : undefined;
                                return (
                                  <Fragment key={`${pathNodeId}-${index}`}>
                                    {index > 0 && (
                                      <div className="causal-path-edge">
                                        <ArrowRight size={14} />
                                        <span>{connectingEdge?.dependency_type?.replaceAll("_", " ") ?? "dependency"}</span>
                                      </div>
                                    )}
                                    <div className={`causal-path-node ${pathNodeId === changedNodeId ? "root" : pathNodeId === nodeId ? "target" : ""}`}>
                                      <strong>{pathNodeId}</strong>
                                      <span>{pathNode?.node_type ?? "Node"}</span>
                                    </div>
                                  </Fragment>
                                );
                              })}
                            </div>
                          ) : (
                            <p className="causal-note">
                              No complete path was found in the currently loaded graph edges. The impact classification is still shown exactly as returned by the API.
                            </p>
                          )}

                          <h5>Backend impact details</h5>
                          <div className="causal-detail-grid">
                            <div><span>Classification</span><strong>{detail.impact ?? "Not provided"}</strong></div>
                            <div><span>Depth</span><strong>{detail.depth ?? "Not provided"}</strong></div>
                            <div><span>Dependency type</span><strong>{(detail.dependency_type ?? detail.dependency_types?.join(", "))?.replaceAll("_", " ") ?? "Not provided"}</strong></div>
                            <div><span>Reported source</span><strong>{causeIds.join(", ") || "Not provided"}</strong></div>
                          </div>
                          <div className="causal-explanation">
                            <strong>Interpretation</strong>
                            <p>
                              {detail.impact?.toLowerCase() === "invalid"
                                ? `The backend classified ${nodeId} as invalid after analyzing the change originating at ${changedNodeId}. Review this node before relying on it.`
                                : detail.impact?.toLowerCase() === "requires_reevaluation"
                                  ? `The backend marked ${nodeId} for reevaluation. Recheck its assumptions before continuing.`
                                  : detail.impact?.toLowerCase() === "uncertain"
                                    ? `The backend marked ${nodeId} as uncertain. Additional evidence is needed before deciding whether to preserve or invalidate it.`
                                    : `The backend returned the classification "${detail.impact ?? "unknown"}" for ${nodeId}. Inspect the dependency path and node state before deciding on recovery.`}
                            </p>
                            <span>Recommendation is guidance only; no node is changed and no recovery action is executed by this analysis.</span>
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
            </div>
          ) : (
            <EmptyState
              title="No downstream impact"
              description="The API returned no affected downstream nodes for this selection."
            />
          )}

          <div className="causal-footnote">
            <ShieldCheck size={16} />
            <span>Impact classifications come from the backend. Dependency paths are reconstructed from the currently loaded graph edges.</span>
          </div>
        </>
      ) : (
        <EmptyState
          title="Ready to trace causality"
          description="Select a changed node and run the analysis to inspect affected nodes, dependency paths, and the backend's classifications."
        />
      )}
    </section>
  );
}

export default App;
