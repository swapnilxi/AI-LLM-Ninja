import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Brain, Copy, Eye, Globe, Library, MessagesSquare, Play, Plus, Save, Trash2 } from "lucide-react";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Agent, AgentSettings, Effort } from "@/lib/types";
import { useAction, useAgent, useConnections, useProviders, useSkills, useTools } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, Card, CardHeader, Field, Input, PageLoader, Select, Switch, Tabs, Textarea } from "@/components/ui/primitives";
import { MultiSelect, TagInput } from "@/components/ui/inputs";
import { ConfirmDialog } from "@/components/ui/overlay";
import { AgentAvatar, IconPicker } from "@/components/ui/icons";
import { GlobalNotice, SaveBar, ScopeBadge } from "@/components/library";
import { RunLauncher } from "@/components/run/RunLauncher";
import { DocumentsPanel } from "@/components/knowledge/DocumentsPanel";
import { MemoryPanel } from "@/components/knowledge/MemoryPanel";
import { TrainPanel } from "@/components/training/TrainPanel";
import { QuickSkillDialog } from "@/components/skills/QuickSkillDialog";
import { modelLabel } from "./parts";

type Form = {
  name: string;
  description: string;
  avatar: string;
  color: string;
  provider: string;
  model: string;
  system_prompt: string;
  temperature: number | null;
  max_tokens: number;
  max_steps: number;
  effort: Effort;
  tool_ids: string[];
  skill_ids: string[];
  connection_ids: string[];
  settings: AgentSettings;
  tags: string[];
};

const EMPTY: Form = {
  name: "",
  description: "",
  avatar: "bot",
  color: "indigo",
  provider: "default",
  model: "",
  system_prompt: "",
  temperature: null,
  max_tokens: 8000,
  max_steps: 8,
  effort: "medium",
  tool_ids: [],
  skill_ids: [],
  connection_ids: [],
  settings: { knowledge_enabled: true },
  tags: [],
};

const EFFORTS: { value: Effort; label: string }[] = [
  { value: "low", label: "Low · fastest, cheapest" },
  { value: "medium", label: "Medium · balanced (default)" },
  { value: "high", label: "High · deeper reasoning" },
  { value: "xhigh", label: "Extra high · hard agentic tasks" },
  { value: "max", label: "Max · when correctness matters most" },
];

type TabKey = "profile" | "model" | "instructions" | "capabilities" | "knowledge" | "memory" | "train";

function toForm(a: Agent): Form {
  return {
    name: a.name,
    description: a.description,
    avatar: a.avatar || "bot",
    color: a.color || "indigo",
    provider: a.provider || "default",
    model: a.model,
    system_prompt: a.system_prompt,
    temperature: a.temperature,
    max_tokens: a.max_tokens,
    max_steps: a.max_steps,
    effort: a.effort,
    tool_ids: a.tool_ids,
    skill_ids: a.skill_ids,
    connection_ids: a.connection_ids,
    settings: a.settings ?? {},
    tags: a.tags,
  };
}

export default function AgentEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const { can, user } = useAuth();
  const agent = useAgent(id);
  const providers = useProviders();
  const skills = useSkills();
  const tools = useTools();
  const connections = useConnections();
  const [form, setForm] = useState<Form>(EMPTY);
  const [scope, setScope] = useState<"org" | "global">("org");
  const [tab, setTab] = useState<TabKey>("profile");
  const [confirm, setConfirm] = useState(false);
  const [running, setRunning] = useState(false);
  const [newSkill, setNewSkill] = useState(false);

  useEffect(() => {
    if (agent.data) setForm(toForm(agent.data));
  }, [agent.data]);

  const readOnly = !can("member") || (!!agent.data && agent.data.org_id === null && !user?.is_superadmin);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));
  const setSetting = (k: keyof AgentSettings, v: boolean) => setForm((f) => ({ ...f, settings: { ...f.settings, [k]: v } }));

  const providerList = providers.data?.providers ?? [];
  const resolvedDefault = providers.data?.default;
  const effectiveProviderKey = form.provider === "default" ? resolvedDefault?.provider : form.provider;
  const providerMeta = providerList.find((p) => p.key === effectiveProviderKey);
  const selectedMeta = providerList.find((p) => p.key === form.provider);

  const body = () => ({
    ...form,
    model: form.provider === "default" ? "" : form.model,
    temperature: providerMeta?.supports_temperature ? form.temperature : null,
  });
  const save = useAction(() => (isNew ? http.post<Agent>("/agents", { ...body(), scope }) : http.put<Agent>(`/agents/${id}`, body())), {
    success: "Agent saved",
    invalidate: [["agents"]],
    onSuccess: (a) => isNew && nav(`/agents/${a.id}`, { replace: true }),
  });
  const dup = useAction(() => http.post<Agent>(`/agents/${id}/duplicate`), { success: "Duplicated into your org", invalidate: [["agents"]], onSuccess: (a) => nav(`/agents/${a.id}`) });
  const del = useAction(() => http.del(`/agents/${id}`), { success: "Agent deleted", invalidate: [["agents"]], onSuccess: () => nav("/agents") });

  const skillOptions = useMemo(
    () => (skills.data ?? []).map((s) => ({ value: s.id, label: s.name, description: s.description, badge: s.org_id === null ? "global" : undefined })),
    [skills.data],
  );
  const toolOptions = useMemo(
    () => (tools.data ?? []).filter((t) => t.enabled).map((t) => ({ value: t.id, label: t.display_name || t.name, description: t.description, badge: t.kind === "builtin" ? t.category : t.kind })),
    [tools.data],
  );
  const connectionOptions = useMemo(
    () => (connections.data ?? []).map((c) => ({ value: c.id, label: `${c.connector_name} · ${c.name}`, description: c.enabled ? `Status: ${c.status}` : "Disabled", badge: c.connector_key })),
    [connections.data],
  );

  if (!isNew && agent.isLoading) return <PageLoader />;

  const tabs: { key: TabKey; label: string }[] = [
    { key: "profile", label: "Profile" },
    { key: "model", label: "Model" },
    { key: "instructions", label: "Instructions" },
    { key: "capabilities", label: "Capabilities & tools" },
    ...(!isNew ? ([{ key: "knowledge", label: "Knowledge" }, { key: "memory", label: "Memory" }, { key: "train", label: "Train" }] as { key: TabKey; label: string }[]) : []),
  ];

  return (
    <Page>
      <PageHeader
        back="/agents"
        icon={<AgentAvatar agent={{ avatar: form.avatar, color: form.color }} size="md" />}
        title={isNew ? "New agent" : form.name || "Agent"}
        description={
          !isNew && agent.data ? (
            <span className="flex flex-wrap items-center gap-2">
              <ScopeBadge orgId={agent.data.org_id} />
              <span className="font-mono text-xs">{modelLabel(agent.data)}</span>
            </span>
          ) : (
            "Agents are reusable across projects. Project context, documents and memory are added at run time."
          )
        }
        actions={
          !isNew && (
            <>
              {can("member") && <Button icon={<Play className="size-4" />} onClick={() => setRunning(true)}>Run</Button>}
              <Button variant="outline" icon={<MessagesSquare className="size-4" />} onClick={() => nav(`/chat?agent=${id}`)}>Chat</Button>
              {can("member") && <Button variant="outline" icon={<Copy className="size-4" />} onClick={() => dup.mutate()} loading={dup.isPending}>Duplicate</Button>}
              {!readOnly && <Button variant="outline" size="icon" icon={<Trash2 className="size-4" />} onClick={() => setConfirm(true)} aria-label="Delete" title="Delete" />}
            </>
          )
        }
      />
      {readOnly && agent.data?.org_id === null && can("member") && <GlobalNotice onDuplicate={() => dup.mutate()} busy={dup.isPending} />}

      <Tabs tabs={tabs} value={tab} onChange={setTab} className="mb-5" />

      {tab === "knowledge" && id && (
        <DocumentsPanel ownerType="agent" ownerId={id} readOnly={!can("member")} description="Documents only this agent can search (in addition to project and organization documents). Pinned documents go into every prompt." />
      )}
      {tab === "memory" && id && <MemoryPanel scope="agent" agentId={id} readOnly={!can("member")} />}
      {tab === "train" && id && <TrainPanel agentId={id} readOnly={!can("member")} onAutoLearnChange={(v) => setSetting("auto_learn", v)} />}

      {tab !== "knowledge" && tab !== "memory" && tab !== "train" && (
        <fieldset disabled={readOnly} className="min-w-0">
          {tab === "profile" && (
            <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
              <Card className="space-y-4 p-4 sm:p-5">
                <Field label="Name">
                  <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Research Analyst" autoFocus={isNew} />
                </Field>
                <Field label="Description" hint="Shown to teammates and used by supervisors and routers to pick the right agent.">
                  <Textarea rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="Finds and verifies up-to-date information on the web." />
                </Field>
                <Field label="Tags">
                  <TagInput value={form.tags} onChange={(v) => set("tags", v)} />
                </Field>
                {isNew && user?.is_superadmin && (
                  <Field label="Library scope" hint="Global agents are shared (read-only) with every organization.">
                    <Select value={scope} onChange={(e) => setScope(e.target.value as "org" | "global")}>
                      <option value="org">This organization</option>
                      <option value="global">Global library</option>
                    </Select>
                  </Field>
                )}
              </Card>
              <Card>
                <CardHeader title="Icon" description="Pick a flat icon and accent color." />
                <div className="p-4">
                  <div className="mb-4 flex items-center gap-3 rounded-xl border border-border bg-gradient-to-br from-primary-soft/60 to-transparent p-3">
                    <AgentAvatar agent={{ avatar: form.avatar, color: form.color }} size="lg" />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold">{form.name || "Untitled agent"}</div>
                      <div className="line-clamp-2 text-xs text-muted">{form.description || "No description"}</div>
                    </div>
                  </div>
                  <IconPicker icon={form.avatar} color={form.color} onChange={(v) => setForm((f) => ({ ...f, avatar: v.icon, color: v.color }))} />
                </div>
              </Card>
            </div>
          )}

          {tab === "model" && (
            <Card className="p-4 sm:p-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field
                  label="Provider"
                  hint={
                    form.provider === "default"
                      ? resolvedDefault
                        ? `Uses the organization default: ${resolvedDefault.provider} · ${resolvedDefault.model}`
                        : "Uses the organization default model"
                      : selectedMeta && !selectedMeta.configured
                        ? "No API key configured yet - add one in Settings → Model providers."
                        : undefined
                  }
                >
                  <Select value={form.provider} onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value, model: "" }))}>
                    <option value="default">Organization default</option>
                    {providerList.map((p) => (
                      <option key={p.key} value={p.key}>
                        {p.label}
                        {p.configured ? "" : " (not configured)"}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Model" hint={form.provider === "default" ? "Set by the organization default." : "Pick a suggestion or type any model id."}>
                  <Input
                    list="agent-model-options"
                    value={form.provider === "default" ? resolvedDefault?.model ?? "" : form.model}
                    disabled={form.provider === "default"}
                    onChange={(e) => set("model", e.target.value)}
                    placeholder={selectedMeta?.models[0] ?? "model-id"}
                    className="font-mono text-xs"
                  />
                  <datalist id="agent-model-options">
                    {(selectedMeta?.models ?? []).map((m) => (
                      <option key={m} value={m} />
                    ))}
                  </datalist>
                </Field>
                <Field label="Reasoning effort" hint="Controls thinking depth on models that support it (Claude, GPT-5 / o-series).">
                  <Select value={form.effort} onChange={(e) => set("effort", e.target.value as Effort)}>
                    {EFFORTS.map((e) => (
                      <option key={e.value} value={e.value}>
                        {e.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                {providerMeta?.supports_temperature ? (
                  <Field label={`Temperature ${form.temperature === null ? "(model default)" : form.temperature.toFixed(1)}`} hint="Lower is more focused, higher is more creative.">
                    <div className="flex h-9 items-center gap-3">
                      <input
                        type="range"
                        min={0}
                        max={2}
                        step={0.1}
                        value={form.temperature ?? 0.7}
                        onChange={(e) => set("temperature", Number(e.target.value))}
                        className="w-full accent-[var(--primary)]"
                      />
                      <Button size="sm" variant="ghost" onClick={() => set("temperature", null)} disabled={form.temperature === null}>
                        Reset
                      </Button>
                    </div>
                  </Field>
                ) : (
                  <Field label="Temperature" hint="This provider manages sampling itself (not configurable).">
                    <Input disabled value="Managed by model" />
                  </Field>
                )}
                <Field label="Max output tokens" hint="Per model response (256 – 128,000).">
                  <Input type="number" min={256} max={128000} value={form.max_tokens} onChange={(e) => set("max_tokens", Number(e.target.value))} />
                </Field>
                <Field label="Max steps" hint="Maximum model ↔ tool iterations per run (1 – 30).">
                  <Input type="number" min={1} max={30} value={form.max_steps} onChange={(e) => set("max_steps", Number(e.target.value))} />
                </Field>
              </div>
            </Card>
          )}

          {tab === "instructions" && (
            <Card>
              <CardHeader
                title="System prompt"
                description="Who the agent is and how it should work. Skills, organization guidelines, the project brief, pinned documents and memory are appended automatically."
              />
              <div className="p-4">
                <Textarea
                  rows={18}
                  value={form.system_prompt}
                  onChange={(e) => set("system_prompt", e.target.value)}
                  placeholder={"You are a meticulous research analyst.\n\n- Always cite sources\n- Prefer primary data\n- …"}
                  className="font-mono text-[13px]"
                />
              </div>
            </Card>
          )}

          {tab === "capabilities" && (
            <div className="grid gap-5 lg:grid-cols-2">
              <Card>
                <CardHeader title="Capabilities" description="Built-in abilities. Project policies can still restrict them (e.g. web access off)." />
                <div className="divide-y divide-border px-4">
                  <div className="py-2">
                    <Switch
                      checked={!!form.settings.browser_enabled}
                      onChange={(v) => setSetting("browser_enabled", v)}
                      label={<span className="inline-flex items-center gap-2"><Globe className="size-4 text-primary" /> Web search & browser</span>}
                      description="Adds web_search and browse_webpage (JS rendering when available)."
                    />
                  </div>
                  <div className="py-2">
                    <Switch
                      checked={!!form.settings.memory_enabled}
                      onChange={(v) => setSetting("memory_enabled", v)}
                      label={<span className="inline-flex items-center gap-2"><Brain className="size-4 text-primary" /> Long-term memory</span>}
                      description="Adds the memory tool and injects this agent's recent memories."
                    />
                  </div>
                  <div className="py-2">
                    <Switch
                      checked={form.settings.knowledge_enabled !== false}
                      onChange={(v) => setSetting("knowledge_enabled", v)}
                      label={<span className="inline-flex items-center gap-2"><Library className="size-4 text-primary" /> Document knowledge</span>}
                      description="Searches agent, project and organization documents when any exist."
                    />
                  </div>
                  <div className="py-2">
                    <Switch
                      checked={!!form.settings.show_thinking}
                      onChange={(v) => setSetting("show_thinking", v)}
                      label={<span className="inline-flex items-center gap-2"><Eye className="size-4 text-primary" /> Show reasoning summaries</span>}
                      description="Records summarized thinking in the run trace when the model supports it."
                    />
                  </div>
                </div>
              </Card>
              <Card>
                <CardHeader
                  title="Skills"
                  description="Instruction packs; their bundled tools are added automatically."
                  actions={!readOnly && <Button size="sm" variant="outline" icon={<Plus className="size-3.5" />} onClick={() => setNewSkill(true)}>New skill</Button>}
                />
                <div className="p-3">
                  <MultiSelect options={skillOptions} value={form.skill_ids} onChange={(v) => set("skill_ids", v)} emptyText="No skills yet" />
                </div>
                <QuickSkillDialog open={newSkill} onClose={() => setNewSkill(false)} onCreated={(sk) => set("skill_ids", [...form.skill_ids, sk.id])} />
              </Card>
              <Card>
                <CardHeader title="Tools" description="Built-in and custom tools this agent can call." />
                <div className="p-3">
                  <MultiSelect options={toolOptions} value={form.tool_ids} onChange={(v) => set("tool_ids", v)} emptyText="No tools available" />
                </div>
              </Card>
              <Card>
                <CardHeader
                  title="App connectors"
                  description="Connections installed in Connectors. Their actions become tools (projects can also share connectors with every agent)."
                  actions={connectionOptions.length > 0 ? <Badge tone="muted">{form.connection_ids.length} selected</Badge> : undefined}
                />
                <div className="p-3">
                  {connectionOptions.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted">
                      No connections yet.{" "}
                      <button type="button" className="cursor-pointer font-medium text-primary hover:underline" onClick={() => nav("/connectors")}>
                        Connect an app
                      </button>
                    </div>
                  ) : (
                    <MultiSelect options={connectionOptions} value={form.connection_ids} onChange={(v) => set("connection_ids", v)} />
                  )}
                </div>
              </Card>
            </div>
          )}
        </fieldset>
      )}

      {!readOnly && tab !== "knowledge" && tab !== "memory" && tab !== "train" && (
        <SaveBar>
          <Button variant="outline" onClick={() => nav("/agents")}>Cancel</Button>
          <Button icon={<Save className="size-4" />} loading={save.isPending} disabled={!form.name.trim()} onClick={() => save.mutate()}>
            {isNew ? "Create agent" : "Save agent"}
          </Button>
        </SaveBar>
      )}
      {!isNew && id && running && <RunLauncher open={running} onClose={() => setRunning(false)} targetType="agent" targetId={id} targetName={form.name} />}
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => del.mutate()}
        loading={del.isPending}
        title="Delete this agent?"
        description="Its documents and memories are deleted too. Teams and workflows that use it will fail until updated."
      />
    </Page>
  );
}
