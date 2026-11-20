import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Archive, ArchiveRestore, Check, Compass, FolderKanban, Globe, Save, ShieldCheck, Trash2 } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Project, ProjectSettings } from "@/modules/projects/types";
import { useAction } from "@/shared/hooks/useAction";
import { useAgents } from "@/modules/agents/api";
import { useConnections } from "@/modules/connectors/api";
import { useSkills } from "@/modules/skills/api";
import { useTools } from "@/modules/tools/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, CardHeader, Field, Input, PageLoader, Select, Switch, Tabs, Textarea } from "@/shared/ui/primitives";
import { KeyValueEditor, MultiSelect, TagInput } from "@/shared/ui/inputs";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { IconTile } from "@/shared/ui/icons";
import { DocumentsPanel } from "@/modules/knowledge/DocumentsPanel";
import { MemoryPanel } from "@/modules/knowledge/MemoryPanel";
import { SaveBar } from "@/shared/components/library";

type Tab = "overview" | "knowledge" | "memory" | "tools" | "policies" | "danger";

interface Form {
  name: string;
  description: string;
  context: string;
  variables: Record<string, any>;
  settings: ProjectSettings;
}

const toForm = (p: Project): Form => ({
  name: p.name,
  description: p.description,
  context: p.context,
  variables: p.variables ?? {},
  settings: { web_access: true, memory_enabled: true, tasks_enabled: true, skill_discovery_enabled: true, ...(p.settings ?? {}) },
});

export default function ProjectDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { can, projectId, setProjectId } = useAuth();
  const project = useQuery({ queryKey: ["project", id], queryFn: () => http.get<Project>(`/projects/${id}`), enabled: !!id });
  const tools = useTools();
  const connections = useConnections();
  const skills = useSkills();
  const agents = useAgents();
  const [tab, setTab] = useState<Tab>("overview");
  const [form, setForm] = useState<Form | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (project.data) setForm(toForm(project.data));
  }, [project.data]);

  const readOnly = !can("member");
  const inv = [["projects"], ["project", id]];
  const save = useAction(
    () => {
      const s = form!.settings;
      return http.patch<Project>(`/projects/${id}`, {
        name: form!.name,
        description: form!.description,
        context: form!.context,
        variables: form!.variables,
        settings: {
          web_access: s.web_access !== false,
          memory_enabled: s.memory_enabled !== false,
          browser_for_all_agents: !!s.browser_for_all_agents,
          browser_render_js: !!s.browser_render_js,
          allowed_domains: s.allowed_domains ?? [],
          blocked_domains: s.blocked_domains ?? [],
          blocked_tools: s.blocked_tools ?? [],
          shared_tool_ids: s.shared_tool_ids ?? [],
          connection_ids: s.connection_ids ?? [],
          skill_ids: s.skill_ids ?? [],
          tasks_enabled: s.tasks_enabled !== false,
          skill_discovery_enabled: s.skill_discovery_enabled !== false,
          scheduling_enabled: !!s.scheduling_enabled,
          default_agent_id: s.default_agent_id ?? "",
        },
      });
    },
    { success: "Project saved", invalidate: inv },
  );
  const archive = useAction((archived: boolean) => http.patch(`/projects/${id}`, { archived }), { success: "Project updated", invalidate: inv });
  const del = useAction(() => http.del(`/projects/${id}`), { success: "Project deleted", invalidate: [["projects"]], onSuccess: () => nav("/projects") });

  if (project.isLoading || (project.data && !form)) return <PageLoader />;
  if (!project.data || !form) return <Page><PageHeader back="/projects" title="Project not found" /></Page>;
  const p = project.data;
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => (f ? { ...f, [k]: v } : f));
  const setS = <K extends keyof ProjectSettings>(k: K, v: ProjectSettings[K]) => setForm((f) => (f ? { ...f, settings: { ...f.settings, [k]: v } } : f));
  const s = form.settings;
  const active = p.id === projectId;
  const saveable = tab === "overview" || tab === "tools" || tab === "policies";

  return (
    <Page>
      <PageHeader
        back="/projects"
        icon={<IconTile icon={FolderKanban} color="indigo" />}
        title={p.name}
        description={
          <span className="inline-flex flex-wrap items-center gap-1.5">
            {active ? <Badge tone="primary" icon={<Check className="size-2.5" />}>Active project</Badge> : null}
            {p.archived && <Badge tone="muted">Archived</Badge>}
            <span>Context, knowledge and policies for every agent running here.</span>
          </span>
        }
        actions={!active && !p.archived && <Button variant="outline" onClick={() => setProjectId(p.id)}>Set as active</Button>}
      />
      <Tabs
        className="mb-5"
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "knowledge", label: "Knowledge" },
          { key: "memory", label: "Memory" },
          { key: "tools", label: "Tools & connectors" },
          { key: "policies", label: "Policies" },
          ...(can("admin") ? [{ key: "danger" as Tab, label: "Danger zone" }] : []),
        ]}
      />

      {tab === "overview" && (
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <Card>
            <CardHeader title="Project brief" description="Injected into the system prompt of every agent, team and workflow that runs in this project." />
            <div className="p-4">
              <Textarea
                rows={14}
                disabled={readOnly}
                value={form.context}
                onChange={(e) => set("context", e.target.value)}
                placeholder={"Goals, audience, tone, constraints, key facts…\n\nExample: We sell B2B analytics to EU retailers. Answers must be GDPR-aware and cite sources."}
              />
            </div>
          </Card>
          <div className="space-y-5">
            <Card className="space-y-4 p-4">
              <Field label="Name">
                <Input disabled={readOnly} value={form.name} onChange={(e) => set("name", e.target.value)} />
              </Field>
              <Field label="Description">
                <Textarea disabled={readOnly} rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} />
              </Field>
            </Card>
            <Card>
              <CardHeader title="Variables" description="Available to agents and as {{ vars.name }} in workflow templates." />
              <div className="p-4">
                <KeyValueEditor value={form.variables} onChange={(v) => set("variables", v)} keyPlaceholder="region" valuePlaceholder="EU" />
              </div>
            </Card>
          </div>
        </div>
      )}

      {tab === "knowledge" && <DocumentsPanel ownerType="project" ownerId={p.id} readOnly={readOnly} description="Searchable by every agent in this project via knowledge_search. Pin short, essential documents so they are always in context." />}

      {tab === "memory" && <MemoryPanel scope="project" projectId={p.id} readOnly={readOnly} />}

      {tab === "tools" && (
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-5">
          <Card>
            <CardHeader title="Shared tools" description="Given to every agent that runs in this project, in addition to its own tools." />
            <div className="p-3">
              <MultiSelect
                options={(tools.data ?? []).filter((t) => t.enabled).map((t) => ({ value: t.id, label: t.display_name || t.name, description: t.description, badge: t.kind }))}
                value={s.shared_tool_ids ?? []}
                onChange={(v) => !readOnly && setS("shared_tool_ids", v)}
              />
            </div>
          </Card>
          <Card>
            <CardHeader
              title="Skills"
              description="Project-level: every agent running in this project follows these, on top of its own skills."
              actions={<Link to="/discover" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"><Compass className="size-3.5" /> Discover</Link>}
            />
            <div className="p-3">
              <MultiSelect
                options={(skills.data ?? []).map((sk) => ({ value: sk.id, label: sk.name, description: sk.description, badge: sk.org_id === null ? "global" : undefined }))}
                value={s.skill_ids ?? []}
                onChange={(v) => !readOnly && setS("skill_ids", v)}
                emptyText="No skills yet - install some from Discover"
              />
              {(s.skill_ids?.length ?? 0) > 8 && <p className="mt-2 text-xs text-muted">Many skills attached: the largest are listed by name only and loaded on demand, to keep prompts small.</p>}
            </div>
          </Card>
          </div>
          <div className="space-y-5">
            <Card>
              <CardHeader title="App connectors" description="Connections whose tools every agent in this project can use." />
              <div className="p-3">
                <MultiSelect
                  options={(connections.data ?? []).map((c) => ({ value: c.id, label: c.name, description: c.connector_name, badge: c.enabled ? undefined : "disabled" }))}
                  value={s.connection_ids ?? []}
                  onChange={(v) => !readOnly && setS("connection_ids", v)}
                  emptyText="No connections yet - add one under Connectors"
                />
              </div>
            </Card>
            <Card className="p-4">
              <Field label="Default agent" hint="Suggested when people start a chat in this project.">
                <Select disabled={readOnly} value={s.default_agent_id ?? ""} onChange={(e) => setS("default_agent_id", e.target.value)}>
                  <option value="">None</option>
                  {(agents.data ?? []).map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </Select>
              </Field>
            </Card>
            <Card>
              <CardHeader title="Agent tools" description="Built-in abilities every agent in this project can use. To remove one for good, add its name to Blocked tools under Policies." />
              <div className="space-y-3 p-4">
                <Switch disabled={readOnly} checked={s.tasks_enabled !== false} onChange={(v) => setS("tasks_enabled", v)} label="To-do tools" description="create_tasks, list_tasks, update_task: agents can turn text into tasks on the Tasks page." />
                <Switch disabled={readOnly} checked={s.skill_discovery_enabled !== false} onChange={(v) => setS("skill_discovery_enabled", v)} label="Find and use skills" description="find_skills and use_skill: agents search installed skills and the skills.sh registry, then load one for the task. Nothing is installed." />
                <Switch disabled={readOnly} checked={!!s.scheduling_enabled} onChange={(v) => setS("scheduling_enabled", v)} label="Scheduling" description="schedule_task: agents can create recurring automations when you ask (for example “every weekday at 9am”). Off by default because it creates automations." />
              </div>
            </Card>
          </div>
        </div>
      )}

      {tab === "policies" && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader title={<span className="inline-flex items-center gap-2"><Globe className="size-4 text-muted" /> Web & browser</span>} />
            <div className="space-y-3 p-4">
              <Switch disabled={readOnly} checked={s.web_access !== false} onChange={(v) => setS("web_access", v)} label="Allow web access" description="When off, web_search, browse_webpage and http_request are removed from every agent here." />
              <Switch disabled={readOnly} checked={!!s.browser_for_all_agents} onChange={(v) => setS("browser_for_all_agents", v)} label="Give every agent the browser" description="Adds web search + browser to all agents, even if their own setting is off." />
              <Switch disabled={readOnly} checked={!!s.browser_render_js} onChange={(v) => setS("browser_render_js", v)} label="Render JavaScript" description="Use a headless browser for pages (requires Playwright on the server)." />
            </div>
          </Card>
          <Card>
            <CardHeader title={<span className="inline-flex items-center gap-2"><ShieldCheck className="size-4 text-muted" /> Guardrails</span>} />
            <div className="space-y-4 p-4">
              <Switch disabled={readOnly} checked={s.memory_enabled !== false} onChange={(v) => setS("memory_enabled", v)} label="Project memory" description="Inject recent project memories into prompts and allow agents to save new ones." />
              <Field label="Allowed domains" hint="If set, agents may only fetch these domains (and subdomains).">
                <TagInput value={s.allowed_domains ?? []} onChange={(v) => setS("allowed_domains", v)} placeholder="example.com" />
              </Field>
              <Field label="Blocked domains">
                <TagInput value={s.blocked_domains ?? []} onChange={(v) => setS("blocked_domains", v)} placeholder="facebook.com" />
              </Field>
              <Field label="Blocked tools" hint="Tool names that are never exposed in this project, e.g. http_request or slack_post_message.">
                <TagInput value={s.blocked_tools ?? []} onChange={(v) => setS("blocked_tools", v)} placeholder="http_request" />
              </Field>
            </div>
          </Card>
        </div>
      )}

      {tab === "danger" && can("admin") && (
        <Card className="border-red-500/30">
          <CardHeader title="Danger zone" />
          <div className="divide-y divide-border">
            <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium">{p.archived ? "Restore project" : "Archive project"}</div>
                <div className="text-xs text-muted">Archived projects are hidden from the project switcher. Nothing is deleted.</div>
              </div>
              <Button variant="outline" icon={p.archived ? <ArchiveRestore className="size-4" /> : <Archive className="size-4" />} loading={archive.isPending} onClick={() => archive.mutate(!p.archived)}>
                {p.archived ? "Restore" : "Archive"}
              </Button>
            </div>
            <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-medium text-danger">Delete project</div>
                <div className="text-xs text-muted">Permanently removes its documents, memory, conversations, runs and automations.</div>
              </div>
              <Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setConfirmDelete(true)}>Delete</Button>
            </div>
          </div>
        </Card>
      )}

      {saveable && !readOnly && (
        <SaveBar>
          <Button variant="outline" onClick={() => setForm(toForm(p))}>Reset</Button>
          <Button icon={<Save className="size-4" />} loading={save.isPending} disabled={!form.name.trim()} onClick={() => save.mutate()}>
            Save changes
          </Button>
        </SaveBar>
      )}
      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => del.mutate()}
        loading={del.isPending}
        title={`Delete “${p.name}”?`}
        description="This permanently deletes the project and everything in it. Agents, skills and tools in your library are not affected."
      />
    </Page>
  );
}
