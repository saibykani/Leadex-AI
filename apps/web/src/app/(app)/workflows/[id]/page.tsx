"use client";
import { useCallback, useEffect, useMemo, useState, type DragEvent } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ReactFlow, ReactFlowProvider, Background, Controls, addEdge, useEdgesState, useNodesState, useReactFlow,
  type Connection, type Edge, type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ArrowLeft } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Button } from "@/components/ui";
import {
  BRANCH_LABELS, NODE_TYPES, STATUS_COLOR, TRIGGERS, workflows,
  type ExecEvent, type Execution, type Graph, type Workflow,
} from "@/lib/workflows";

type NodeData = { type: string; config: Record<string, unknown>; label: string; status?: string };

const toFlow = (g: Graph | null): { nodes: Node<NodeData>[]; edges: Edge[] } => ({
  nodes: (g?.nodes ?? []).map((n, i) => ({
    id: n.id, position: n.position ?? { x: 80 + i * 220, y: 120 },
    data: { type: n.type, config: n.config ?? {}, label: NODE_TYPES.find((t) => t.type === n.type)?.label ?? n.type },
  })),
  edges: (g?.edges ?? []).map((e, i) => ({ id: `e${i}-${e.source}-${e.target}`, source: e.source, target: e.target, label: e.label })),
});

const toGraph = (nodes: Node<NodeData>[], edges: Edge[]): Graph => ({
  nodes: nodes.map((n) => ({ id: n.id, type: n.data.type, config: n.data.config, position: n.position })),
  edges: edges.map((e) => ({ source: e.source, target: e.target, ...(e.label ? { label: String(e.label) } : {}) })),
});

export default function Page() {
  return <ReactFlowProvider><Builder /></ReactFlowProvider>;
}

function Builder() {
  const { id } = useParams<{ id: string }>();
  const { can } = useSession();
  const editable = can("workflows:write");
  const { screenToFlowPosition } = useReactFlow();
  const [wf, setWf] = useState<Workflow | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selNode, setSelNode] = useState<string | null>(null);
  const [selEdge, setSelEdge] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [execs, setExecs] = useState<Execution[]>([]);
  const [activeExec, setActiveExec] = useState<string | null>(null);
  const [events, setEvents] = useState<ExecEvent[]>([]);
  const [payload, setPayload] = useState("{}");

  useEffect(() => {
    workflows.get(id).then((w) => {
      setWf(w);
      const f = toFlow(w.draft_graph);
      setNodes(f.nodes); setEdges(f.edges);
    }).catch((e) => setMsg({ ok: false, text: e.message }));
    workflows.executions(id).then((p) => setExecs(p.items)).catch(() => {});
  }, [id, setNodes, setEdges]);

  // per-node status coloring from the selected execution
  const statusByNode = useMemo(() => {
    const m: Record<string, string> = {};
    for (const e of events) if (e.node_key) m[e.node_key] = e.event;
    return m;
  }, [events]);
  const styledNodes = useMemo(() => nodes.map((n) => {
    const st = statusByNode[n.id];
    return {
      ...n,
      data: { ...n.data, label: `${n.data.label}${st ? ` · ${st}` : ""}` },
      style: {
        borderRadius: 14, padding: 10, fontSize: 12, background: "#fff",
        border: `2px solid ${st ? STATUS_COLOR[st] ?? "#e5e5ea" : n.id === selNode ? "#0071e3" : "#e5e5ea"}`,
        boxShadow: "0 1px 2px rgba(0,0,0,.04), 0 4px 16px rgba(0,0,0,.04)",
      },
    };
  }), [nodes, statusByNode, selNode]);

  const onConnect = useCallback((c: Connection) => {
    const src = nodes.find((n) => n.id === c.source);
    const label = src ? BRANCH_LABELS[src.data.type]?.[0] : undefined;
    setEdges((es) => addEdge({ ...c, label }, es));
  }, [nodes, setEdges]);

  const onDrop = (ev: DragEvent) => {
    ev.preventDefault();
    const type = ev.dataTransfer.getData("application/leadex-node");
    const def = NODE_TYPES.find((t) => t.type === type);
    if (!def || !editable) return;
    const nid = `${type}_${Math.random().toString(36).slice(2, 7)}`;
    setNodes((ns) => ns.concat({
      id: nid, position: screenToFlowPosition({ x: ev.clientX, y: ev.clientY }),
      data: { type, config: { ...def.defaults }, label: def.label },
    }));
    setSelNode(nid);
  };

  const graph = () => toGraph(nodes, edges);
  const act = async (fn: () => Promise<string>) => {
    try { setMsg({ ok: true, text: await fn() }); } catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
  };
  const validate = () => act(async () => {
    const r = await workflows.validate(graph());
    if (!r.valid) throw new Error(r.errors.join("; "));
    return "Graph is valid";
  });
  const saveDraft = () => act(async () => { await workflows.update(id, { graph: graph() }); return "Draft saved"; });
  const publish = () => act(async () => {
    const v = await workflows.publish(id, graph());
    setWf(await workflows.get(id));
    return `Published version ${v.version}`;
  });
  const showExec = async (eid: string) => { setActiveExec(eid); setEvents(await workflows.events(eid)); };
  const run = () => act(async () => {
    let p: Record<string, unknown>;
    try { p = JSON.parse(payload || "{}"); } catch { throw new Error("Payload must be valid JSON"); }
    let ex = await workflows.execute(id, p, crypto.randomUUID());
    // Runs are executed by the background worker: poll until the run leaves queued/running (max ~30s).
    for (let i = 0; i < 30; i++) {
      const items = (await workflows.executions(id)).items;
      setExecs(items);
      ex = items.find((x) => x.id === ex.id) ?? ex;
      await showExec(ex.id);
      if (!["queued", "running"].includes(ex.status)) break;
      await new Promise((r) => setTimeout(r, 1000));
    }
    return `Run ${ex.status}${ex.error ? `: ${ex.error}` : ""}`;
  });

  const node = nodes.find((n) => n.id === selNode);
  const edge = edges.find((e) => e.id === selEdge);
  const setConfig = (key: string, value: unknown) =>
    setNodes((ns) => ns.map((n) => n.id === selNode ? { ...n, data: { ...n.data, config: { ...n.data.config, [key]: value } } } : n));

  if (!wf) return <div className="text-sm text-muted">{msg?.text ?? "Loading…"}</div>;
  const groups = Array.from(new Set(NODE_TYPES.map((t) => t.group)));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/workflows" className="rounded-full p-2 hover:bg-raised"><ArrowLeft className="h-4 w-4" /></Link>
          <div>
            <h1 className="text-xl font-semibold">{wf.name}</h1>
            <p className="text-xs text-muted">Status {wf.status} · trigger {wf.trigger_type ?? "—"}</p>
          </div>
        </div>
        {editable && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="h-9 px-4" onClick={validate}>Validate</Button>
            <Button variant="outline" className="h-9 px-4" onClick={saveDraft}>Save draft</Button>
            <Button className="h-9 px-4" onClick={publish}>Save version</Button>
          </div>
        )}
      </div>
      {msg && (msg.ok
        ? <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">{msg.text}</div>
        : <Alert>{msg.text}</Alert>)}

      <div className="grid gap-4 lg:grid-cols-[180px_1fr_280px]">
        <div className="card space-y-3 p-3">
          {groups.map((g) => (
            <div key={g}>
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted">{g}</div>
              {NODE_TYPES.filter((t) => t.group === g).map((t) => (
                <div key={t.type} draggable={editable}
                  onDragStart={(e) => { e.dataTransfer.setData("application/leadex-node", t.type); e.dataTransfer.effectAllowed = "move"; }}
                  className="mb-1 cursor-grab rounded-lg border border-line bg-white px-2 py-1.5 text-xs hover:border-accent">
                  {t.label}
                </div>
              ))}
            </div>
          ))}
        </div>

        <div className="card h-[560px] overflow-hidden" onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDrop={onDrop}>
          <ReactFlow
            nodes={styledNodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect} nodesDraggable={editable} nodesConnectable={editable}
            onNodeClick={(_, n) => { setSelNode(n.id); setSelEdge(null); }}
            onEdgeClick={(_, e) => { setSelEdge(e.id); setSelNode(null); }}
            onPaneClick={() => { setSelNode(null); setSelEdge(null); }}
            fitView
          >
            <Background gap={20} color="#e5e5ea" />
            <Controls />
          </ReactFlow>
        </div>

        <div className="card space-y-3 p-4 text-sm">
          {node ? (
            <>
              <div className="font-medium">{node.data.label} <span className="text-xs text-muted">({node.id})</span></div>
              {node.data.type === "trigger" && (
                <label className="block text-xs text-muted">Trigger type
                  <select className="mt-1 h-9 w-full rounded-lg border border-line bg-white px-2 text-sm text-neutral-900"
                    value={String(node.data.config.trigger_type ?? "manual")} onChange={(e) => setConfig("trigger_type", e.target.value)}>
                    {TRIGGERS.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </label>
              )}
              {Object.entries(node.data.config).filter(([k]) => k !== "trigger_type").map(([k, v]) => (
                <label key={k} className="block text-xs text-muted">{k}
                  <input className="mt-1 h-9 w-full rounded-lg border border-line px-2 text-sm text-neutral-900" disabled={!editable}
                    value={typeof v === "object" ? JSON.stringify(v) : String(v ?? "")}
                    onChange={(e) => {
                      const raw = e.target.value;
                      const num = Number(raw);
                      setConfig(k, raw !== "" && !Number.isNaN(num) && typeof v === "number" ? num : raw);
                    }} />
                </label>
              ))}
              {editable && <AddField onAdd={(k) => setConfig(k, "")} />}
              {["email", "whatsapp", "voice_call"].includes(node.data.type) && (
                <p className="rounded-lg bg-raised p-2 text-xs text-muted">This step never sends directly. It records an OutreachGate decision (blocked / simulated) for the lead in the trigger payload.</p>
              )}
              {editable && node.data.type !== "trigger" && (
                <Button variant="outline" className="h-9 w-full" onClick={() => {
                  setNodes((ns) => ns.filter((n) => n.id !== node.id));
                  setEdges((es) => es.filter((e) => e.source !== node.id && e.target !== node.id));
                  setSelNode(null);
                }}>Delete node</Button>
              )}
            </>
          ) : edge ? (
            <>
              <div className="font-medium">Edge {edge.source} → {edge.target}</div>
              <label className="block text-xs text-muted">Branch label (empty = always)
                <input className="mt-1 h-9 w-full rounded-lg border border-line px-2 text-sm text-neutral-900" disabled={!editable}
                  value={String(edge.label ?? "")}
                  onChange={(e) => setEdges((es) => es.map((x) => x.id === edge.id ? { ...x, label: e.target.value || undefined } : x))} />
              </label>
              {editable && <Button variant="outline" className="h-9 w-full" onClick={() => { setEdges((es) => es.filter((x) => x.id !== edge.id)); setSelEdge(null); }}>Delete edge</Button>}
            </>
          ) : (
            <p className="text-muted">Drag steps from the palette, connect them, and click a node or edge to configure it.</p>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-3 p-4">
          <h2 className="text-sm font-medium">Run</h2>
          <textarea className="h-24 w-full rounded-xl border border-line p-3 font-mono text-xs" value={payload}
            onChange={(e) => setPayload(e.target.value)} placeholder='{"lead_id": "..."}' />
          {editable && <Button className="h-9 px-4" onClick={run} disabled={!wf.current_version_id}>Run published version</Button>}
          <ul className="divide-y divide-line text-sm">
            {execs.map((x) => (
              <li key={x.id}>
                <button className={`flex w-full items-center justify-between py-2 text-left ${activeExec === x.id ? "font-medium" : ""}`} onClick={() => showExec(x.id)}>
                  <span>{new Date(x.created_at).toLocaleString()} · {x.trigger_type}</span>
                  <span className="text-xs" style={{ color: STATUS_COLOR[x.status] }}>{x.status}</span>
                </button>
                {activeExec === x.id && x.status === "waiting" && x.resume_at && editable && (
                  <Button variant="ghost" className="h-8 px-3 text-xs" onClick={() => act(async () => {
                    const r = await workflows.resume(x.id); setExecs((await workflows.executions(id)).items); await showExec(x.id); return `Resumed: ${r.status}`;
                  })}>Resume delay</Button>
                )}
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-medium">Execution log</h2>
          {events.length === 0 ? <p className="text-sm text-muted">Select a run to see per-node events.</p> : (
            <ol className="space-y-1 font-mono text-xs">
              {events.map((e) => (
                <li key={e.id} className="flex gap-2">
                  <span className="w-6 text-muted">{e.seq}</span>
                  <span className="w-28 truncate">{e.node_key}</span>
                  <span style={{ color: STATUS_COLOR[e.event] ?? "#1d1d1f" }}>{e.event}{e.attempt > 1 ? ` #${e.attempt}` : ""}</span>
                  <span className="truncate text-muted">{e.error ?? (e.output ? JSON.stringify(e.output) : "")}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

function AddField({ onAdd }: { onAdd: (k: string) => void }) {
  const [k, setK] = useState("");
  return (
    <div className="flex gap-2">
      <input className="h-8 flex-1 rounded-lg border border-line px-2 text-xs" placeholder="add config key" value={k} onChange={(e) => setK(e.target.value)} />
      <button className="text-xs text-accent" onClick={() => { if (k.trim()) { onAdd(k.trim()); setK(""); } }}>Add</button>
    </div>
  );
}
