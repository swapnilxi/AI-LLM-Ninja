import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Bot, Copy, Save, Trash2, Webhook } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { JSONSchema } from "@/shared/lib/types";
import type { Tool } from "@/modules/tools/types";
import { cn } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useAgents } from "@/modules/agents/api";
import { useTool } from "@/modules/tools/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, CardHeader, Field, Input, PageLoader, Select, Switch, Textarea } from "@/shared/ui/primitives";
import { KeyValueEditor } from "@/shared/ui/inputs";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { IconTile } from "@/shared/ui/icons";
import { GlobalNotice, SaveBar, ScopeBadge } from "@/shared/components/library";
import { ParamBuilder, ParamTable, TestPanel, toolIcon } from "./parts";

type Kind = "http" | "agent";

interface Form {
  name: string;
  display_name: string;
  description: string;
  kind: Kind;
  category: string;
  parameters: JSONSchema;
  config: Record<string, any>;
  enabled: boolean;
}

const EMPTY: Form = {
  name: "",
  display_name: "",
  description: "",
  kind: "http",
  category: "custom",
  parameters: { type: "object", properties: { query: { type: "string", description: "What to look up" } }, required: ["query"] },
  config: { method: "GET", url: "https://api.example.com/search?q={{ args.query }}", headers: {}, query: {}, body_template: "", response_path: "", timeout: 30 },
  enabled: true,
};

const NAME_RE = /^[a-zA-Z][a-zA-Z0-9_-]*$/;

function KindToggle({ value, onChange, disabled }: { value: Kind; onChange: (k: Kind) => void; disabled?: boolean }) {
  const opts: { key: Kind; title: string; text: string; icon: typeof Webhook }[] = [
    { key: "http", title: "HTTP API", text: "Call any REST endpoint with templated URL, headers and body.", icon: Webhook },
    { key: "agent", title: "Agent as tool", text: "Let one agent hand a task to another agent.", icon: Bot },
  ];
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {opts.map((o) => (
        <button
          key={o.key}
          type="button"
          disabled={disabled}
          onClick={() => onChange(o.key)}
          className={cn(
            "flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-left transition-colors disabled:cursor-default",
            value === o.key ? "border-primary bg-gradient-to-br from-primary-soft to-transparent" : "border-border hover:bg-surface-2",
          )}
        >
          <IconTile icon={o.icon} color={o.key === "http" ? "teal" : "indigo"} size="sm" />
          <span className="min-w-0">
            <span className="block text-sm font-medium">{o.title}</span>
            <span className="block text-xs text-muted">{o.text}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

export default function ToolEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const { can, user } = useAuth();
  const tool = useTool(id);
  const agents = useAgents();
  const [form, setForm] = useState<Form>(EMPTY);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    const t = tool.data;
    if (t && t.kind !== "builtin")
      setForm({ name: t.name, display_name: t.display_name, description: t.description, kind: t.kind as Kind, category: t.category, parameters: t.parameters, config: t.config ?? {}, enabled: t.enabled });
  }, [tool.data]);

  const save = useAction(() => (isNew ? http.post<Tool>("/tools", form) : http.put<Tool>(`/tools/${id}`, form)), {
    success: "Tool saved",
    invalidate: [["tools"]],
    onSuccess: (t) => isNew && nav(`/tools/${t.id}`, { replace: true }),
  });
  const dup = useAction(() => http.post<Tool>(`/tools/${id}/duplicate`), { success: "Duplicated into your org", invalidate: [["tools"]], onSuccess: (t) => nav(`/tools/${t.id}`) });
  const del = useAction(() => http.del(`/tools/${id}`), { success: "Tool deleted", invalidate: [["tools"]], onSuccess: () => nav("/tools") });

  if (!isNew && tool.isLoading) return <PageLoader />;
  const t = tool.data;

  /* ---------------------------------------------------------------- built-in (read only) */
  if (t && t.kind === "builtin") {
    const ic = toolIcon(t);
    return (
      <Page>
        <PageHeader
          back="/tools"
          icon={<IconTile icon={ic.icon} color={ic.color} />}
          title={t.display_name || t.name}
          description={
            <span className="flex flex-wrap items-center gap-2">
              <Badge tone="primary">Built-in</Badge>
              <Badge tone="muted">{t.category}</Badge>
              <span className="font-mono text-xs">{t.name}</span>
            </span>
          }
        />
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-5">
            <Card className="p-4 sm:p-5">
              <h3 className="mb-1 text-sm font-semibold">What it does</h3>
              <p className="text-sm text-muted">{t.description}</p>
              <p className="mt-3 text-xs text-muted">
                Add it to an agent in the agent editor (Capabilities & tools). Web tools respect each project's web-access policy and domain allow/deny lists; every
                request goes through the SSRF-safe network layer.
              </p>
            </Card>
            <Card>
              <CardHeader title="Parameters" />
              <ParamTable schema={t.parameters} />
            </Card>
          </div>
          <TestPanel tool={t} />
        </div>
      </Page>
    );
  }

  /* ---------------------------------------------------------------- custom */
  const readOnly = !can("member") || (!!t && t.org_id === null && !user?.is_superadmin);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));
  const setCfg = (k: string, v: any) => setForm((f) => ({ ...f, config: { ...f.config, [k]: v } }));
  const nameError = form.name && !NAME_RE.test(form.name) ? "Start with a letter; letters, numbers, _ and - only" : undefined;
  const switchKind = (k: Kind) =>
    setForm((f) => ({
      ...f,
      kind: k,
      config: k === "agent" ? { agent_id: f.config.agent_id ?? "" } : { method: "GET", url: "", headers: {}, query: {}, body_template: "", response_path: "", timeout: 30 },
      parameters: k === "agent" ? { type: "object", properties: { task: { type: "string", description: "Task for the agent" } }, required: ["task"] } : f.parameters,
    }));
  const ic = toolIcon({ kind: form.kind, builtin_key: null });

  return (
    <Page>
      <PageHeader
        back="/tools"
        icon={<IconTile icon={ic.icon} color={ic.color} />}
        title={isNew ? "New tool" : form.display_name || form.name || "Tool"}
        description={t ? <span className="flex items-center gap-2"><ScopeBadge orgId={t.org_id} /><span className="font-mono text-xs">{t.name}</span></span> : "Custom tools become callable functions for any agent you attach them to."}
        actions={
          !isNew && (
            <>
              {can("member") && <Button variant="outline" icon={<Copy className="size-4" />} onClick={() => dup.mutate()} loading={dup.isPending}>Duplicate</Button>}
              {!readOnly && <Button variant="outline" size="icon" icon={<Trash2 className="size-4" />} onClick={() => setConfirm(true)} aria-label="Delete" title="Delete" />}
            </>
          )
        }
      />
      {readOnly && t?.org_id === null && can("member") && <GlobalNotice onDuplicate={() => dup.mutate()} busy={dup.isPending} />}

      <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
        <fieldset disabled={readOnly} className="min-w-0 space-y-5">
          <KindToggle value={form.kind} onChange={switchKind} disabled={readOnly || !isNew} />
          <Card className="space-y-4 p-4 sm:p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Function name" hint={nameError ? undefined : "What the model calls, e.g. search_crm"} error={nameError}>
                <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="search_crm" className="font-mono text-xs" />
              </Field>
              <Field label="Display name">
                <Input value={form.display_name} onChange={(e) => set("display_name", e.target.value)} placeholder="CRM search" />
              </Field>
            </div>
            <Field label="Description" hint="Tell the model when and how to use this tool - this is what it reads.">
              <Textarea rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="Search customer records by name or email. Returns matching contacts." />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Category">
                <Input value={form.category} onChange={(e) => set("category", e.target.value)} placeholder="custom" />
              </Field>
              <div className="flex items-end pb-1">
                <Switch checked={form.enabled} onChange={(v) => set("enabled", v)} label="Enabled" description="Disabled tools are hidden from agents." />
              </div>
            </div>
          </Card>

          {form.kind === "http" ? (
            <Card>
              <CardHeader title="HTTP request" description="Templates use sandboxed Jinja. Requests go through the SSRF guard and project domain policy." />
              <div className="space-y-4 p-4 sm:p-5">
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Field label="Method" className="sm:w-32">
                    <Select value={form.config.method ?? "GET"} onChange={(e) => setCfg("method", e.target.value)}>
                      {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
                        <option key={m}>{m}</option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="URL template" className="flex-1">
                    <Input value={form.config.url ?? ""} onChange={(e) => setCfg("url", e.target.value)} placeholder="https://api.example.com/items/{{ args.id }}" className="font-mono text-xs" />
                  </Field>
                </div>
                <div className="rounded-lg border border-border bg-surface-2/60 p-3 text-xs text-muted">
                  <div className="mb-1 font-medium text-fg">Template variables</div>
                  <ul className="space-y-0.5">
                    <li><code className="font-mono">{"{{ args.x }}"}</code> - tool arguments (URL-encoded automatically inside the URL)</li>
                    <li><code className="font-mono">{"{{ secrets.NAME }}"}</code> - org secrets from Settings → Secrets (never shown to the model)</li>
                    <li><code className="font-mono">{"{{ vars.x }}"}</code> - project variables · <code className="font-mono">{"{{ project.name }}"}</code>, <code className="font-mono">{"{{ org.name }}"}</code></li>
                  </ul>
                </div>
                <Field label="Headers">
                  <KeyValueEditor value={form.config.headers ?? {}} onChange={(v) => setCfg("headers", v)} keyPlaceholder="Authorization" valuePlaceholder="Bearer {{ secrets.API_TOKEN }}" />
                </Field>
                <Field label="Query parameters">
                  <KeyValueEditor value={form.config.query ?? {}} onChange={(v) => setCfg("query", v)} keyPlaceholder="limit" valuePlaceholder="{{ args.limit }}" />
                </Field>
                <Field label="Body template" hint="Rendered then sent as JSON when it parses as JSON, otherwise as raw text.">
                  <Textarea mono rows={5} value={form.config.body_template ?? ""} onChange={(e) => setCfg("body_template", e.target.value)} placeholder={'{"query": "{{ args.query }}", "limit": 5}'} />
                </Field>
                <div className="grid gap-4 sm:grid-cols-3">
                  <Field label="Response path" hint="Dot path into the JSON, e.g. data.items">
                    <Input value={form.config.response_path ?? ""} onChange={(e) => setCfg("response_path", e.target.value)} className="font-mono text-xs" />
                  </Field>
                  <Field label="Timeout (s)">
                    <Input type="number" min={1} max={120} value={form.config.timeout ?? 30} onChange={(e) => setCfg("timeout", Number(e.target.value))} />
                  </Field>
                  <Field label="Max output chars">
                    <Input type="number" min={500} max={20000} value={form.config.max_chars ?? 12000} onChange={(e) => setCfg("max_chars", Number(e.target.value))} />
                  </Field>
                </div>
              </div>
            </Card>
          ) : (
            <Card>
              <CardHeader title="Target agent" description="The selected agent runs with the caller's project context and returns its answer as the tool result." />
              <div className="p-4 sm:p-5">
                <Field label="Agent">
                  <Select value={form.config.agent_id ?? ""} onChange={(e) => setCfg("agent_id", e.target.value)}>
                    <option value="">Select an agent…</option>
                    {(agents.data ?? []).map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                        {a.org_id === null ? " (global)" : ""}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            </Card>
          )}

          <ParamBuilder value={form.parameters} onChange={(v) => set("parameters", v)} readOnly={readOnly} />
        </fieldset>

        <div className="space-y-5">
          {t ? (
            <TestPanel tool={t} />
          ) : (
            <Card className="p-4 text-sm text-muted">Save the tool to test it against the active project.</Card>
          )}
        </div>
      </div>

      {!readOnly && (
        <SaveBar>
          <Button variant="outline" onClick={() => nav("/tools")}>Cancel</Button>
          <Button
            icon={<Save className="size-4" />}
            loading={save.isPending}
            disabled={!form.name.trim() || !!nameError || (form.kind === "agent" && !form.config.agent_id) || (form.kind === "http" && !form.config.url)}
            onClick={() => save.mutate()}
          >
            {isNew ? "Create tool" : "Save tool"}
          </Button>
        </SaveBar>
      )}
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={() => del.mutate()} loading={del.isPending} title="Delete this tool?" description="Agents and skills that reference it will stop receiving it." />
    </Page>
  );
}
