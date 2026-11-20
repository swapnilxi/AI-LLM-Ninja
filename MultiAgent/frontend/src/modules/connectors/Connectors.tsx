import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, ExternalLink, FlaskConical, Lock, Pencil, Plug, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Connection, Connector } from "@/lib/types";
import { cn, errMsg, timeAgo } from "@/lib/utils";
import { useAction, useConnections, useConnectorCatalog, useHub } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, Card, Checkbox, EmptyState, Field, Input, PageLoader, Spinner, Switch, Tabs, Textarea } from "@/components/ui/primitives";
import { SearchInput } from "@/components/ui/inputs";
import { ConfirmDialog, Dialog } from "@/components/ui/overlay";
import { ConnectorIcon } from "@/components/ui/icons";
import { Grid } from "@/components/library";
import { McpServerGrid } from "@/components/hub/McpServers";

type ToolRow = { action: string; tool_name: string; description: string; write: boolean; exposed: boolean };

function StatusBadge({ status }: { status: string }) {
  if (status === "ok") return <Badge tone="success">Connected</Badge>;
  if (status === "error") return <Badge tone="danger">Error</Badge>;
  return <Badge tone="muted">Not tested</Badge>;
}

export default function Connectors() {
  const { can, project, projectId } = useAuth();
  const hub = useHub(projectId);
  const catalog = useConnectorCatalog();
  const connections = useConnections();
  const [tab, setTab] = useState<"connected" | "catalog">("connected");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState<{ connector: Connector; connection?: Connection } | null>(null);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (!touched && connections.data && connections.data.length === 0) setTab("catalog");
  }, [connections.data, touched]);

  const byKey = useMemo(() => Object.fromEntries((catalog.data ?? []).map((c) => [c.key, c])), [catalog.data]);
  const filteredCatalog = (catalog.data ?? []).filter((c) => !q || `${c.name} ${c.description} ${c.category}`.toLowerCase().includes(q.toLowerCase()));
  const categories = Array.from(new Set(filteredCatalog.map((c) => c.category)));

  return (
    <Page>
      <PageHeader
        title="Connectors"
        description="Connect apps and MCP servers once per organization. Their actions become tools for agents."
        actions={can("admin") && <Button icon={<Plus className="size-4" />} onClick={() => { setTouched(true); setTab("catalog"); }}>Connect an app</Button>}
      />

      <Card className="mb-5 grid gap-4 bg-gradient-to-br from-primary-soft/60 via-transparent to-transparent p-4 sm:grid-cols-3 sm:p-5">
        <div className="flex gap-3">
          <Plug className="mt-0.5 size-4 shrink-0 text-primary" />
          <div className="text-sm">
            <div className="font-medium">Attach to an agent</div>
            <div className="text-muted">
              <Link to="/agents" className="text-primary hover:underline">Agent editor</Link> → Capabilities & tools → App connectors.
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <ChevronRight className="mt-0.5 size-4 shrink-0 text-primary" />
          <div className="text-sm">
            <div className="font-medium">Share with a project</div>
            <div className="text-muted">
              <Link to="/projects" className="text-primary hover:underline">Project settings</Link> → connectors are given to every agent running there.
            </div>
          </div>
        </div>
        <div className="flex gap-3">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
          <div className="text-sm">
            <div className="font-medium">Secure by default</div>
            <div className="text-muted">Credentials are encrypted at rest, never returned, and calls pass the SSRF guard. Read-only mode hides write actions.</div>
          </div>
        </div>
      </Card>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={[
            { key: "connected", label: "Connected", count: connections.data?.length },
            { key: "catalog", label: "Catalog", count: catalog.data?.length },
          ]}
          value={tab}
          onChange={(v) => {
            setTouched(true);
            setTab(v);
          }}
        />
        {tab === "catalog" && <SearchInput value={q} onChange={setQ} placeholder="Search apps…" className="sm:w-64" />}
      </div>

      {tab === "connected" ? (
        connections.isLoading ? (
          <PageLoader />
        ) : !connections.data?.length ? (
          <EmptyState
            icon={<Plug className="size-5" />}
            title="No apps connected yet"
            description="Connect GitHub, Slack, Notion, Jira, Linear, email, any REST API or a remote MCP server."
            action={<Button onClick={() => setTab("catalog")}>Browse catalog</Button>}
          />
        ) : (
          <div className="space-y-3">
            {connections.data.map((c) => (
              <ConnectionRow key={c.id} connection={c} connector={byKey[c.connector_key]} onEdit={() => byKey[c.connector_key] && setDialog({ connector: byKey[c.connector_key], connection: c })} />
            ))}
          </div>
        )
      ) : catalog.isLoading ? (
        <PageLoader />
      ) : (
        <div className="space-y-7">
          {!q && !!hub.data?.mcp.length && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-xs font-medium uppercase tracking-wide text-muted">Popular tools (MCP)</h2>
                <Link to="/discover?tab=connectors" className="text-xs font-medium text-primary hover:underline">See all</Link>
              </div>
              <McpServerGrid servers={hub.data.mcp.filter((m) => m.popular)} projectId={projectId} projectName={project?.name} />
            </section>
          )}
          {categories.map((cat) => (
            <section key={cat}>
              <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-muted">{cat}</h2>
              <Grid>
                {filteredCatalog
                  .filter((c) => c.category === cat)
                  .map((c) => (
                    <CatalogCard key={c.key} connector={c} count={(connections.data ?? []).filter((x) => x.connector_key === c.key).length} onConnect={() => setDialog({ connector: c })} canConnect={can("admin")} />
                  ))}
              </Grid>
            </section>
          ))}
          {!filteredCatalog.length && <p className="text-sm text-muted">No apps match “{q}”.</p>}
        </div>
      )}

      {dialog && (
        <ConnectDialog
          connector={dialog.connector}
          connection={dialog.connection}
          onClose={() => setDialog(null)}
          onCreated={() => {
            setTouched(true);
            setTab("connected");
          }}
        />
      )}
    </Page>
  );
}

function CatalogCard({ connector, count, onConnect, canConnect }: { connector: Connector; count: number; onConnect: () => void; canConnect: boolean }) {
  return (
    <Card className="flex flex-col p-4 transition-all hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/5">
      <div className="flex items-start gap-3">
        <ConnectorIcon connectorKey={connector.key} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold">{connector.name}</h3>
            {count > 0 && <Badge tone="success">{count} connected</Badge>}
          </div>
          <div className="text-xs text-muted">{connector.category}</div>
        </div>
      </div>
      <p className="mt-3 line-clamp-2 text-sm text-muted">{connector.description}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {connector.dynamic ? (
          <Badge tone="primary">Tools discovered from server</Badge>
        ) : (
          connector.actions.map((a) => (
            <Badge key={a.name} tone={a.write ? "warning" : "muted"}>
              {a.name}
              {a.write ? " · write" : ""}
            </Badge>
          ))
        )}
      </div>
      <div className="mt-auto flex items-center justify-between gap-2 pt-4">
        {connector.docs_url ? (
          <a href={connector.docs_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
            Get credentials <ExternalLink className="size-3" />
          </a>
        ) : (
          <span />
        )}
        {canConnect ? (
          <Button size="sm" icon={<Plus className="size-3.5" />} onClick={onConnect}>
            Connect
          </Button>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-muted">
            <Lock className="size-3" /> Admins only
          </span>
        )}
      </div>
    </Card>
  );
}

function ConnectionRow({ connection: c, connector, onEdit }: { connection: Connection; connector?: Connector; onEdit: () => void }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [testing, setTesting] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const inv = [["connections"]];
  const tools = useQuery({ queryKey: ["connection-tools", c.id], queryFn: () => http.get<ToolRow[]>(`/connections/${c.id}/tools`), enabled: open });
  const toggle = useAction((v: boolean) => http.patch(`/connections/${c.id}`, { enabled: v }), { invalidate: inv });
  const del = useAction(() => http.del(`/connections/${c.id}`), { success: "Connection removed", invalidate: inv, onSuccess: () => setConfirm(false) });

  const test = async () => {
    setTesting(true);
    try {
      const r = await http.post<{ ok: boolean; message: string }>(`/connections/${c.id}/test`);
      r.ok ? toast.success(r.message) : toast.error(r.message);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setTesting(false);
      qc.invalidateQueries({ queryKey: ["connections"] });
      qc.invalidateQueries({ queryKey: ["connection-tools", c.id] });
    }
  };

  return (
    <Card className={cn(!c.enabled && "opacity-70")}>
      <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <ConnectorIcon connectorKey={c.connector_key} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-sm font-semibold">{c.name}</span>
              <StatusBadge status={c.status} />
              {c.config?.read_only && <Badge tone="muted">Read-only</Badge>}
            </div>
            <div className="truncate text-xs text-muted">
              {c.connector_name} · added {timeAgo(c.created_at)}
              {c.enabled_tools.length > 0 && ` · ${c.enabled_tools.length} action(s) enabled`}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {can("admin") && (
            <>
              <Switch checked={c.enabled} onChange={(v) => toggle.mutate(v)} />
              <Button size="sm" variant="outline" icon={<FlaskConical className="size-3.5" />} loading={testing} onClick={test}>
                Test
              </Button>
              <Button size="sm" variant="outline" icon={<Pencil className="size-3.5" />} onClick={onEdit} disabled={!connector}>
                Edit
              </Button>
              <Button size="icon" variant="ghost" aria-label="Delete connection" onClick={() => setConfirm(true)}>
                <Trash2 className="size-4 text-muted" />
              </Button>
            </>
          )}
          <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)} icon={<ChevronRight className={cn("size-4 transition-transform", open && "rotate-90")} />}>
            Tools
          </Button>
        </div>
      </div>
      {open && (
        <div className="border-t border-border px-4 py-3">
          {tools.isLoading ? (
            <div className="flex justify-center py-4"><Spinner /></div>
          ) : tools.isError ? (
            <p className="text-sm text-danger">{errMsg(tools.error)}</p>
          ) : !tools.data?.length ? (
            <p className="text-sm text-muted">No tools available. For MCP servers, check the URL and token with Test.</p>
          ) : (
            <ul className="divide-y divide-border">
              {tools.data.map((t) => (
                <li key={t.action} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-start sm:gap-3">
                  <div className="flex shrink-0 items-center gap-2 sm:w-64">
                    <span className="truncate font-mono text-xs font-medium">{t.tool_name}</span>
                    {t.write && <Badge tone="warning">write</Badge>}
                    {!t.exposed && <Badge tone="muted">hidden</Badge>}
                  </div>
                  <p className="min-w-0 flex-1 text-xs text-muted">{t.description}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={() => del.mutate()} loading={del.isPending} title={`Remove “${c.name}”?`} description="Agents and projects using this connection lose its tools. Stored credentials are deleted." />
    </Card>
  );
}

function ConnectDialog({ connector, connection, onClose, onCreated }: { connector: Connector; connection?: Connection; onClose: () => void; onCreated: () => void }) {
  const editing = !!connection;
  const initial = () => {
    const v: Record<string, any> = {};
    for (const f of connector.fields) {
      const existing = connection?.config?.[f.key];
      if (f.secret) v[f.key] = "";
      else if (existing !== undefined && existing !== null) v[f.key] = existing;
      else v[f.key] = f.default ?? (f.type === "boolean" ? false : "");
    }
    return v;
  };
  const [name, setName] = useState(connection?.name ?? connector.name);
  const [values, setValues] = useState<Record<string, any>>(initial);
  const [enabledTools, setEnabledTools] = useState<string[]>(connection?.enabled_tools ?? []);
  const inv = [["connections"], ["connection-tools", connection?.id]];

  const payloadConfig = () => {
    const cfg: Record<string, any> = {};
    for (const f of connector.fields) {
      const v = values[f.key];
      if (f.secret && (v === "" || v === undefined)) continue; // keep existing secret
      cfg[f.key] = f.type === "number" && v !== "" ? Number(v) : v;
    }
    return cfg;
  };

  const save = useAction(
    async () => {
      if (editing) return http.patch<Connection>(`/connections/${connection!.id}`, { name, config: payloadConfig(), enabled_tools: enabledTools });
      const created = await http.post<Connection>("/connections", { connector_key: connector.key, name, config: payloadConfig(), enabled_tools: enabledTools });
      try {
        const r = await http.post<{ ok: boolean; message: string }>(`/connections/${created.id}/test`);
        r.ok ? toast.success(r.message) : toast.warning(`Saved, but the test failed: ${r.message}`);
      } catch {
        /* test is best-effort */
      }
      return created;
    },
    {
      success: editing ? "Connection updated" : `${connector.name} connected`,
      invalidate: inv,
      onSuccess: () => {
        if (!editing) onCreated();
        onClose();
      },
    },
  );

  const missing = connector.fields.filter((f) => f.required && !(f.secret && editing) && !String(values[f.key] ?? "").trim());

  return (
    <Dialog
      open
      onClose={onClose}
      size="lg"
      title={
        <span className="flex items-center gap-3">
          <ConnectorIcon connectorKey={connector.key} size="sm" />
          {editing ? `Edit ${connection!.name}` : `Connect ${connector.name}`}
        </span>
      }
      description={connector.description}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button loading={save.isPending} disabled={!name.trim() || missing.length > 0} onClick={() => save.mutate()}>
            {editing ? "Save changes" : "Connect"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Connection name" hint="Shown in agent and project settings, e.g. “GitHub - platform team”.">
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        {connector.fields.map((f) => {
          const masked = connection?.config?.[f.key];
          const label = (
            <span className="inline-flex items-center gap-1.5">
              {f.label}
              {f.required && <span className="text-danger">*</span>}
              {f.secret && <Lock className="size-3 text-muted" />}
            </span>
          );
          if (f.type === "boolean")
            return (
              <div key={f.key} className="rounded-lg border border-border px-3 py-2">
                <Switch checked={!!values[f.key]} onChange={(v) => setValues({ ...values, [f.key]: v })} label={f.label} description={f.help} />
              </div>
            );
          return (
            <Field key={f.key} label={label} hint={f.secret && editing ? `Leave blank to keep the current value${masked ? ` (${masked})` : ""}.` : f.help}>
              {f.type === "textarea" ? (
                <Textarea mono rows={3} value={values[f.key] ?? ""} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} placeholder={f.secret && editing && masked ? String(masked) : f.placeholder} />
              ) : (
                <Input
                  type={f.secret || f.type === "password" ? "password" : f.type === "number" ? "number" : f.type === "url" ? "url" : "text"}
                  autoComplete="off"
                  value={values[f.key] ?? ""}
                  onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                  placeholder={f.secret && editing && masked ? String(masked) : f.placeholder}
                  className={cn(f.type === "url" && "font-mono text-xs")}
                />
              )}
            </Field>
          );
        })}
        {!connector.dynamic && connector.actions.length > 1 && (
          <div>
            <div className="mb-1.5 text-xs font-medium text-muted">Allowed actions <span className="font-normal">(none selected = all)</span></div>
            <div className="grid gap-2 rounded-lg border border-border p-3 sm:grid-cols-2">
              {connector.actions.map((a) => (
                <Checkbox
                  key={a.name}
                  checked={enabledTools.includes(a.name)}
                  onChange={(v) => setEnabledTools(v ? [...enabledTools, a.name] : enabledTools.filter((x) => x !== a.name))}
                  label={
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono text-xs">{a.name}</span>
                      {a.write && <Badge tone="warning">write</Badge>}
                    </span>
                  }
                />
              ))}
            </div>
          </div>
        )}
        {connector.dynamic && <p className="text-xs text-muted">Tools are discovered from the server after connecting (cached for 5 minutes). Use “Test” to refresh.</p>}
      </div>
    </Dialog>
  );
}
