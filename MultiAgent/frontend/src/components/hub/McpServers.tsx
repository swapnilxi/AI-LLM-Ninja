import { useState } from "react";
import { BookOpen, Check, CircleCheck, CreditCard, Database, ExternalLink, Globe, KeyRound, Lock, Plus, Search, TriangleExclamationPoint, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Connection, HubMcpServer } from "@/lib/types";
import { errMsg } from "@/lib/utils";
import { Dialog } from "@/components/ui/overlay";
import { Badge, Button, Card, Field, Input, Switch } from "@/components/ui/primitives";
import { IconTile } from "@/components/ui/icons";
import { Grid } from "@/components/library";

const CATEGORY_ICON: Record<string, { icon: LucideIcon; color: string }> = {
  Developer: { icon: BookOpen, color: "slate" },
  "Search & browsing": { icon: Globe, color: "sky" },
  "AI & data": { icon: Database, color: "emerald" },
  Business: { icon: CreditCard, color: "violet" },
};

const AUTH_LABEL: Record<HubMcpServer["auth"], { text: string; tone: "success" | "muted" | "warning" }> = {
  none: { text: "No key needed", tone: "success" },
  optional: { text: "Key optional", tone: "muted" },
  bearer: { text: "API key required", tone: "warning" },
};

/** Grid of one-click MCP servers. Connecting creates an org connection and (optionally) attaches it to the project. */
export function McpServerGrid({ servers, projectId, projectName }: { servers: HubMcpServer[]; projectId?: string | null; projectName?: string }) {
  const { can } = useAuth();
  const [dialog, setDialog] = useState<HubMcpServer | null>(null);
  return (
    <>
      <Grid>
        {servers.map((s) => (
          <McpCard key={s.id} server={s} canConnect={can("admin")} projectId={projectId} onConnect={() => setDialog(s)} />
        ))}
      </Grid>
      {dialog && <McpInstallDialog server={dialog} projectId={projectId} projectName={projectName} onClose={() => setDialog(null)} />}
    </>
  );
}

function McpCard({ server: s, canConnect, projectId, onConnect }: { server: HubMcpServer; canConnect: boolean; projectId?: string | null; onConnect: () => void }) {
  const meta = CATEGORY_ICON[s.category] ?? CATEGORY_ICON.Developer;
  const auth = AUTH_LABEL[s.auth];
  const connected = !!s.connection_id;
  const attached = !!projectId && s.attached;
  return (
    <Card className="flex flex-col p-4 transition-all hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/5">
      <div className="flex items-start gap-3">
        <IconTile icon={meta.icon} color={meta.color} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold">{s.name}</h3>
          <div className="text-xs text-muted">{s.category}</div>
        </div>
        {connected && (
          <Badge tone={s.status === "error" ? "danger" : "success"} icon={<CircleCheck className="size-3" />}>
            {s.status === "error" ? "Check key" : "Connected"}
          </Badge>
        )}
      </div>
      <p className="mt-3 text-sm text-muted">{s.tagline}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge tone={auth.tone} icon={s.auth === "none" ? undefined : <KeyRound className="size-3" />}>{auth.text}</Badge>
        {attached && <Badge tone="primary" icon={<Check className="size-3" />}>In this project</Badge>}
      </div>
      {s.caveat && (
        <p className="mt-3 flex gap-1.5 text-xs text-muted">
          <TriangleExclamationPoint className="mt-0.5 size-3.5 shrink-0 text-warning" /> {s.caveat}
        </p>
      )}
      <div className="mt-auto flex items-center justify-between gap-2 pt-4">
        <a href={s.docs_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
          Docs <ExternalLink className="size-3" />
        </a>
        {!canConnect ? (
          <span className="inline-flex items-center gap-1 text-xs text-muted"><Lock className="size-3" /> Admins only</span>
        ) : connected && attached ? (
          s.auth === "none" ? (
            <span className="inline-flex items-center gap-1 text-xs text-muted"><Check className="size-3.5 text-success" /> Ready to use</span>
          ) : (
            <Button size="sm" variant="outline" onClick={onConnect}>Update key</Button>
          )
        ) : (
          <Button size="sm" icon={<Plus className="size-3.5" />} onClick={onConnect}>{connected ? "Add to project" : "Connect"}</Button>
        )}
      </div>
    </Card>
  );
}

function McpInstallDialog({ server: s, projectId, projectName, onClose }: { server: HubMcpServer; projectId?: string | null; projectName?: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [token, setToken] = useState("");
  const [attach, setAttach] = useState(!!projectId);
  const [busy, setBusy] = useState(false);
  const needsToken = s.auth === "bearer" && !s.connection_id;
  const label = s.token_label ?? "API key";

  const install = async () => {
    setBusy(true);
    try {
      const r = await http.post<{ connection: Connection; test: { ok: boolean; message: string }; attached: boolean }>("/hub/mcp/install", {
        server_id: s.id,
        token: token.trim(),
        project_id: attach && projectId ? projectId : undefined,
      });
      const where = r.attached ? ` and added to ${projectName ?? "the project"}` : "";
      r.test.ok ? toast.success(`${s.name} connected${where}. ${r.test.message}`) : toast.warning(`${s.name} saved${where}, but the test failed: ${r.test.message}`);
      ["hub", "connections", "projects", "project"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      onClose();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      size="md"
      title={s.connection_id ? `Update ${s.name}` : `Connect ${s.name}`}
      description={s.tagline}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button loading={busy} disabled={(needsToken && !token.trim()) || (!!s.connection_id && !token.trim() && !attach)} onClick={install}>
            {s.connection_id ? "Save" : "Connect"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="rounded-lg bg-surface-2 px-3 py-2 font-mono text-[11px] text-muted break-all">{s.url}</div>
        {s.auth !== "none" && (
          <Field
            label={
              <span className="inline-flex items-center gap-1.5">
                {label} {s.auth === "optional" && <span className="font-normal text-muted">(optional)</span>} <Lock className="size-3 text-muted" />
              </span>
            }
            hint={
              <>
                Stored encrypted and never shown again.{" "}
                {s.token_url && (
                  <a href={s.token_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    Get a key
                  </a>
                )}
                {s.connection_id && " Leave blank to keep the current key."}
              </>
            }
          >
            <Input type="password" autoComplete="off" autoFocus value={token} onChange={(e) => setToken(e.target.value)} placeholder={s.connection_id ? "••••••••" : ""} />
          </Field>
        )}
        {s.caveat && (
          <p className="flex gap-2 rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-muted">
            <TriangleExclamationPoint className="mt-0.5 size-3.5 shrink-0 text-warning" /> {s.caveat}
          </p>
        )}
        {projectId ? (
          <div className="rounded-lg border border-border px-3 py-2">
            <Switch
              checked={attach}
              onChange={setAttach}
              label={`Make it available to every agent in ${projectName ?? "this project"}`}
              description="Project-level: agents running in this project can call the server's tools. You can change this later in the project settings."
            />
          </div>
        ) : (
          <p className="flex gap-2 text-xs text-muted"><Search className="mt-0.5 size-3.5 shrink-0" /> Pick a project to attach it to, or attach it later from the project settings.</p>
        )}
      </div>
    </Dialog>
  );
}
