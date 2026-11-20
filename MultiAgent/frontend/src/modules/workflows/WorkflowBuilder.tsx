import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeChange,
  type NodeChange,
  type NodeTypes,
} from "@xyflow/react";
import { ChevronLeft, CircleAlert, Copy, Ellipsis, Globe, ListPlus, Maximize2, Play, Plus, Save, ShieldCheck, SlidersHorizontal, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { InputField, Workflow, WorkflowEdge } from "@/lib/types";
import { cn, errMsg } from "@/lib/utils";
import { useAgents, useCatalog, useProviders, useStartRun, useTeams, useTools, useWorkflow } from "@/hooks/useData";
import { useRunStream } from "@/hooks/useRunStream";
import { Badge, Button, Field, PageLoader, Textarea } from "@/components/ui/primitives";
import { ConfirmDialog, Menu, MenuItem, Sheet } from "@/components/ui/overlay";
import { IconTile } from "@/components/ui/icons";
import { InputFieldsDialog } from "./InputFieldsDialog";
import { NodeConfig, TemplateHelp } from "./NodeConfig";
import { LookupCtx, NODE_META, nodeTypes, PALETTE_ORDER, StatusCtx, type FlowNode, type NodeData, type NodeStatus } from "./nodes";
import { RunPanel } from "./RunPanel";

const DND_TYPE = "application/x-agentforge-node";

function styledEdge(e: { id: string; source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null }): Edge {
  const branch = e.sourceHandle === "true" || e.sourceHandle === "false" ? e.sourceHandle : undefined;
  const color = branch === "true" ? "#10b981" : branch === "false" ? "#f43f5e" : undefined;
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? null,
    targetHandle: e.targetHandle ?? null,
    type: "smoothstep",
    label: branch,
    style: color ? { stroke: color, strokeWidth: 1.6 } : { strokeWidth: 1.6 },
    labelStyle: color ? { fill: color, fontWeight: 600, fontSize: 11 } : undefined,
    labelBgStyle: { fill: "var(--surface)" },
    labelBgPadding: [4, 2],
    labelBgBorderRadius: 4,
  };
}

const STARTER_NODES: FlowNode[] = [
  { id: "input_1", type: "input", position: { x: 0, y: 120 }, data: { label: "Input" } },
  { id: "output_1", type: "output", position: { x: 520, y: 120 }, data: { label: "Output", template: "{{ last }}" } },
];
const STARTER_EDGES: Edge[] = [styledEdge({ id: "e_input_1_output_1", source: "input_1", target: "output_1" })];

function Palette({ onAdd, disabled }: { onAdd: (type: string) => void; disabled?: boolean }) {
  return (
    <div className="space-y-1.5 p-3">
      <div className="px-1 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted">Nodes · click or drag</div>
      {PALETTE_ORDER.map((type) => {
        const meta = NODE_META[type];
        return (
          <button
            key={type}
            type="button"
            disabled={disabled}
            draggable={!disabled}
            onDragStart={(e) => {
              e.dataTransfer.setData(DND_TYPE, type);
              e.dataTransfer.effectAllowed = "move";
            }}
            onClick={() => onAdd(type)}
            className="flex w-full cursor-pointer items-center gap-2.5 rounded-xl border border-border bg-surface p-2 text-left transition-colors hover:border-indigo-500/30 hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <IconTile icon={meta.icon} color={meta.color} size="sm" />
            <div className="min-w-0">
              <div className="text-sm font-medium">{meta.label}</div>
              <div className="line-clamp-1 text-[11px] text-muted">{meta.description}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function Builder() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const { can, user } = useAuth();
  const wf = useWorkflow(id);
  const agents = useAgents();
  const teams = useTeams();
  const tools = useTools();
  const catalog = useCatalog();
  const providers = useProviders();
  const rf = useReactFlow();
  const wrapper = useRef<HTMLDivElement>(null);

  const [name, setName] = useState("Untitled workflow");
  const [description, setDescription] = useState("");
  const [nodes, setNodes] = useState<FlowNode[]>(isNew ? STARTER_NODES : []);
  const [edges, setEdges] = useState<Edge[]>(isNew ? STARTER_EDGES : []);
  const [inputFields, setInputFields] = useState<InputField[]>(isNew ? [{ name: "topic", label: "Topic", type: "text", default: "" }] : []);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [panel, setPanel] = useState<"config" | "run" | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [inputsOpen, setInputsOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [dirty, setDirty] = useState(isNew);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const stream = useRunStream(runId);
  const start = useStartRun();

  useEffect(() => {
    if (!wf.data) return;
    setName(wf.data.name);
    setDescription(wf.data.description);
    setNodes((wf.data.graph?.nodes ?? []).map((n) => ({ id: n.id, type: n.type, position: n.position ?? { x: 0, y: 0 }, data: n.data ?? {} })));
    setEdges((wf.data.graph?.edges ?? []).map((e) => styledEdge(e)));
    setInputFields(wf.data.input_fields ?? []);
    setDirty(false);
    const t = setTimeout(() => rf.fitView({ padding: 0.2, maxZoom: 1.1 }), 60);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wf.data]);

  // keep the graph in view when the side panel opens/closes (canvas width changes)
  useEffect(() => {
    const t = setTimeout(() => rf.fitView({ padding: 0.2, maxZoom: 1.1, duration: 200 }), 80);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [panel]);

  const readOnly = !can("member") || (!!wf.data && wf.data.org_id === null && !user?.is_superadmin);
  const lookups = useMemo(
    () => ({
      agents: Object.fromEntries((agents.data ?? []).map((a) => [a.id, a])),
      teams: Object.fromEntries((teams.data ?? []).map((t) => [t.id, t])),
      tools: Object.fromEntries((tools.data ?? []).map((t) => [t.id, t])),
    }),
    [agents.data, teams.data, tools.data],
  );
  const status: Record<string, NodeStatus> = runId ? stream.nodeStatus : {};
  const displayEdges = useMemo(() => edges.map((e) => (status[e.target] === "running" ? { ...e, animated: true } : e)), [edges, status]);
  const selected = nodes.find((n) => n.id === selectedId) ?? null;

  const onNodesChange = useCallback((changes: NodeChange<FlowNode>[]) => {
    setNodes((ns) => applyNodeChanges(changes, ns));
    if (changes.some((c) => c.type === "position" || c.type === "remove" || c.type === "add")) setDirty(true);
    for (const c of changes) if (c.type === "remove") setSelectedId((s) => (s === c.id ? null : s));
  }, []);
  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setEdges((es) => applyEdgeChanges(changes, es));
    if (changes.some((c) => c.type === "remove" || c.type === "add")) setDirty(true);
  }, []);
  const onConnect = useCallback((c: Connection) => {
    if (c.source === c.target) return;
    setEdges((es) => {
      const exists = es.some((e) => e.source === c.source && e.target === c.target && (e.sourceHandle ?? null) === (c.sourceHandle ?? null));
      if (exists) return es;
      return addEdge(styledEdge({ ...c, id: `e_${c.source}_${c.sourceHandle ?? "o"}_${c.target}_${Date.now().toString(36)}` }), es);
    });
    setDirty(true);
  }, []);

  const nextId = (type: string) => {
    const nums = nodes.filter((n) => n.id.startsWith(`${type}_`)).map((n) => Number(n.id.slice(type.length + 1)) || 0);
    return `${type}_${(nums.length ? Math.max(...nums) : 0) + 1}`;
  };

  const addNode = (type: string, position?: { x: number; y: number }) => {
    if (readOnly) return;
    let pos = position;
    if (!pos) {
      const r = wrapper.current?.getBoundingClientRect();
      const center = r ? { x: r.left + r.width / 2, y: r.top + r.height / 2.4 } : { x: 300, y: 200 };
      pos = rf.screenToFlowPosition(center);
      pos = { x: pos.x - 110 + (nodes.length % 4) * 24, y: pos.y - 40 + (nodes.length % 4) * 24 };
    }
    const nid = nextId(type);
    setNodes((ns) => [...ns.map((n) => ({ ...n, selected: false })), { id: nid, type, position: pos!, data: { ...NODE_META[type].defaults }, selected: true }]);
    setSelectedId(nid);
    setPanel("config");
    setPaletteOpen(false);
    setDirty(true);
  };

  const updateData = (nid: string, data: NodeData) => {
    setNodes((ns) => ns.map((n) => (n.id === nid ? { ...n, data } : n)));
    setDirty(true);
  };

  const deleteNode = (nid: string) => {
    setNodes((ns) => ns.filter((n) => n.id !== nid));
    setEdges((es) => es.filter((e) => e.source !== nid && e.target !== nid));
    setSelectedId(null);
    setDirty(true);
  };

  const graph = () => ({
    nodes: nodes.map((n) => ({ id: n.id, type: n.type ?? "template", position: { x: Math.round(n.position.x), y: Math.round(n.position.y) }, data: n.data })),
    edges: edges.map<WorkflowEdge>((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle ?? null })),
  });

  const save = async (): Promise<string | null> => {
    setSaving(true);
    try {
      const body = { name: name.trim() || "Untitled workflow", description, graph: graph(), input_fields: inputFields };
      const w = isNew ? await http.post<Workflow>("/workflows", body) : await http.put<Workflow>(`/workflows/${id}`, body);
      setDirty(false);
      toast.success("Workflow saved");
      if (isNew) nav(`/workflows/${w.id}`, { replace: true });
      return w.id;
    } catch (e) {
      toast.error(errMsg(e));
      return null;
    } finally {
      setSaving(false);
    }
  };

  const validate = async () => {
    try {
      const res = await http.post<{ valid: boolean; errors: string[] }>("/workflows/validate", { name: name.trim() || "Untitled", graph: graph(), input_fields: inputFields });
      setErrors(res.errors);
      if (res.valid) toast.success("Workflow is valid");
      else toast.error(`${res.errors.length} problem${res.errors.length > 1 ? "s" : ""} found`);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const run = async (input: Record<string, any>) => {
    let wid: string | null = isNew ? null : (id ?? null);
    if ((dirty || isNew) && !readOnly) wid = await save();
    if (!wid) return;
    try {
      const r = await start.mutateAsync({ target_type: "workflow", target_id: wid, input });
      setRunId(r.id);
    } catch {
      /* toast shown by hook */
    }
  };

  const duplicate = async () => {
    try {
      const w = await http.post<Workflow>(`/workflows/${id}/duplicate`);
      toast.success("Duplicated into your org");
      nav(`/workflows/${w.id}`);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const remove = async () => {
    try {
      await http.del(`/workflows/${id}`);
      toast.success("Workflow deleted");
      nav("/workflows");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    const type = e.dataTransfer.getData(DND_TYPE);
    if (!type || !NODE_META[type]) return;
    const p = rf.screenToFlowPosition({ x: e.clientX, y: e.clientY });
    addNode(type, { x: p.x - 110, y: p.y - 30 });
  };

  if (!isNew && wf.isLoading) return <PageLoader />;
  if (!isNew && wf.isError) {
    return (
      <div className="p-8 text-center text-sm text-muted">
        Workflow not found. <Link to="/workflows" className="text-primary hover:underline">Back to workflows</Link>
      </div>
    );
  }

  const dark = typeof document !== "undefined" && document.documentElement.classList.contains("dark");
  const nodeIds = nodes.map((n) => n.id);

  const panelBody =
    panel === "run" ? (
      <RunPanel fields={inputFields} runId={runId} stream={stream} starting={start.isPending || saving} onRun={run} />
    ) : selected ? (
      <NodeConfig
        key={selected.id}
        node={selected}
        readOnly={readOnly}
        onChange={(d) => updateData(selected.id, d)}
        onDelete={() => deleteNode(selected.id)}
        agents={agents.data ?? []}
        teams={teams.data ?? []}
        tools={tools.data ?? []}
        catalog={catalog.data}
        providers={providers.data?.providers ?? []}
        nodeIds={nodeIds}
      />
    ) : (
      <div className="space-y-4 p-4">
        <div>
          <div className="text-sm font-semibold">Workflow</div>
          <p className="mt-0.5 text-xs text-muted">Select a node to configure it. Connect nodes by dragging from a handle on the right to one on the left.</p>
        </div>
        <Field label="Description">
          <Textarea
            rows={3}
            disabled={readOnly}
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              setDirty(true);
            }}
            placeholder="What does this workflow do?"
          />
        </Field>
        <div className="grid grid-cols-3 gap-2 text-center">
          {[
            ["Nodes", nodes.length],
            ["Edges", edges.length],
            ["Inputs", inputFields.length],
          ].map(([k, v]) => (
            <div key={k} className="rounded-lg border border-border bg-surface-2/50 py-2">
              <div className="text-lg font-semibold tabular-nums">{v}</div>
              <div className="text-[11px] text-muted">{k}</div>
            </div>
          ))}
        </div>
        <TemplateHelp nodeIds={nodeIds} />
      </div>
    );

  return (
    <StatusCtx.Provider value={status}>
      <LookupCtx.Provider value={lookups}>
        <div className="flex h-full flex-col">
          {/* top bar */}
          <div className="surface-glass flex shrink-0 items-center gap-2 border-b border-border px-2 py-2 sm:px-3">
            <Link to="/workflows" className="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Back to workflows">
              <ChevronLeft className="size-4" />
            </Link>
            <input
              value={name}
              disabled={readOnly}
              onChange={(e) => {
                setName(e.target.value);
                setDirty(true);
              }}
              className="min-w-0 flex-1 truncate rounded-md bg-transparent px-1.5 py-1 text-sm font-semibold hover:bg-surface-2 focus:bg-surface-2 focus:outline-none sm:max-w-xs"
              aria-label="Workflow name"
            />
            {wf.data?.org_id === null && <Badge tone="primary" icon={<Globe className="size-2.5" />} className="hidden sm:inline-flex">Global</Badge>}
            {dirty && !readOnly && <Badge tone="warning" className="hidden sm:inline-flex">Unsaved</Badge>}
            <div className="flex-1" />
            <Button variant="outline" size="sm" icon={<ListPlus className="size-3.5" />} onClick={() => setInputsOpen(true)} title="Input fields">
              <span className="hidden md:inline">Inputs</span>
            </Button>
            <Button variant="outline" size="sm" icon={<ShieldCheck className="size-3.5" />} onClick={validate} title="Validate" className="hidden sm:inline-flex">
              <span className="hidden md:inline">Validate</span>
            </Button>
            {!readOnly && (
              <Button variant="outline" size="sm" icon={<Save className="size-3.5" />} loading={saving} onClick={save} title="Save">
                <span className="hidden md:inline">Save</span>
              </Button>
            )}
            {can("member") && (
              <Button size="sm" icon={<Play className="size-3.5" />} onClick={() => setPanel("run")} title="Run">
                <span className="hidden sm:inline">Run</span>
              </Button>
            )}
            {!isNew && (
              <Menu
                trigger={
                  <Button variant="ghost" size="sm" aria-label="More">
                    <Ellipsis className="size-4" />
                  </Button>
                }
              >
                {(close) => (
                  <>
                    <MenuItem icon={<ShieldCheck className="size-4" />} onClick={() => { close(); validate(); }}>Validate</MenuItem>
                    <MenuItem icon={<Copy className="size-4" />} onClick={() => { close(); duplicate(); }}>Duplicate to my org</MenuItem>
                    {!readOnly && <MenuItem danger icon={<Trash2 className="size-4" />} onClick={() => { close(); setConfirmDelete(true); }}>Delete workflow</MenuItem>}
                  </>
                )}
              </Menu>
            )}
          </div>

          {errors.length > 0 && (
            <div className="flex items-start gap-2 border-b border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-danger">
              <CircleAlert className="mt-0.5 size-4 shrink-0" />
              <ul className="flex-1 space-y-0.5">{errors.map((e) => <li key={e}>{e}</li>)}</ul>
              <button onClick={() => setErrors([])} className="cursor-pointer" aria-label="Dismiss"><X className="size-4" /></button>
            </div>
          )}

          <div className="relative flex min-h-0 flex-1">
            <aside className="hidden w-52 shrink-0 overflow-y-auto border-r border-border bg-surface/60 lg:block">
              <Palette onAdd={addNode} disabled={readOnly} />
            </aside>

            <div ref={wrapper} className="relative min-w-0 flex-1" onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDrop={onDrop}>
              <ReactFlow
                nodes={nodes}
                edges={displayEdges}
                nodeTypes={nodeTypes as NodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeClick={(_, n) => {
                  setSelectedId(n.id);
                  setPanel("config");
                }}
                onPaneClick={() => {
                  setSelectedId(null);
                  setPanel((p) => (p === "run" ? p : null));
                }}
                nodesDraggable={!readOnly}
                nodesConnectable={!readOnly}
                deleteKeyCode={readOnly ? null : ["Backspace", "Delete"]}
                colorMode={dark ? "dark" : "light"}
                fitView
                fitViewOptions={{ padding: 0.2, maxZoom: 1.1 }}
                minZoom={0.2}
                proOptions={{ hideAttribution: true }}
                defaultEdgeOptions={{ type: "smoothstep" }}
              >
                <Background gap={22} size={1.2} />
                <Controls className="!hidden lg:!flex" showInteractive={false} />
                <MiniMap className="!hidden lg:!block" pannable zoomable nodeStrokeWidth={2} nodeBorderRadius={8} />
                <Panel position="bottom-left" className="flex gap-2 lg:!hidden">
                  {!readOnly && (
                    <Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => setPaletteOpen(true)}>
                      Add node
                    </Button>
                  )}
                  <Button size="sm" variant="outline" onClick={() => rf.fitView({ padding: 0.2 })} aria-label="Fit view">
                    <Maximize2 className="size-3.5" />
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setPanel(panel ? null : "config")} aria-label="Panel">
                    <SlidersHorizontal className="size-3.5" />
                  </Button>
                </Panel>
                {!panel && (
                  <Panel position="top-right" className="!hidden lg:!block">
                    <Button size="sm" variant="outline" icon={<SlidersHorizontal className="size-3.5" />} onClick={() => setPanel("config")}>
                      Details
                    </Button>
                  </Panel>
                )}
                {readOnly && wf.data?.org_id === null && (
                  <Panel position="top-left">
                    <div className="flex items-center gap-2 rounded-xl border border-indigo-500/20 bg-surface/95 px-3 py-2 text-xs shadow-sm">
                      <Globe className="size-4 text-primary" />
                      <span className="text-muted">Read-only global workflow</span>
                      <button onClick={duplicate} className="cursor-pointer font-medium text-primary hover:underline">Duplicate</button>
                    </div>
                  </Panel>
                )}
              </ReactFlow>
            </div>

            <aside
              className={cn(
                "absolute inset-x-0 bottom-0 z-20 h-[68%] flex-col rounded-t-2xl border-t border-border bg-surface shadow-2xl",
                "lg:static lg:z-auto lg:h-auto lg:w-[360px] lg:shrink-0 lg:rounded-none lg:border-l lg:border-t-0 lg:shadow-none",
                panel ? "flex" : "hidden",
              )}
            >
              <div className="flex shrink-0 items-center gap-1 border-b border-border px-2 py-1.5">
                {[
                  { key: "config" as const, label: selected ? "Configure" : "Details" },
                  { key: "run" as const, label: "Run" },
                ].map((t) => (
                  <button
                    key={t.key}
                    onClick={() => setPanel(t.key)}
                    className={cn("cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium", (panel ?? "config") === t.key ? "bg-primary-soft text-primary" : "text-muted hover:bg-surface-2")}
                  >
                    {t.label}
                  </button>
                ))}
                <div className="flex-1" />
                <button
                  onClick={() => {
                    setPanel(null);
                    setSelectedId(null);
                  }}
                  className="cursor-pointer rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-fg"
                  aria-label="Close panel"
                >
                  <X className="size-4" />
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">{panelBody}</div>
            </aside>
          </div>
        </div>

        <Sheet open={paletteOpen} onClose={() => setPaletteOpen(false)} title="Add node" side="right" width="w-[300px]">
          <Palette onAdd={addNode} />
        </Sheet>
        <InputFieldsDialog
          open={inputsOpen}
          onClose={() => setInputsOpen(false)}
          value={inputFields}
          readOnly={readOnly}
          onChange={(v) => {
            setInputFields(v);
            setDirty(true);
          }}
        />
        <ConfirmDialog open={confirmDelete} onClose={() => setConfirmDelete(false)} onConfirm={remove} title="Delete this workflow?" description="Automations that run it will fail." />
      </LookupCtx.Provider>
    </StatusCtx.Provider>
  );
}

export default function WorkflowBuilder() {
  return (
    <ReactFlowProvider>
      <Builder />
    </ReactFlowProvider>
  );
}
