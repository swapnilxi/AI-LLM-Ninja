import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { KeyRound, Plus, TriangleAlert } from "lucide-react";
import { apiBase, http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Role } from "@/shared/lib/types";
import { formatDate, timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { IconTile } from "@/shared/ui/icons";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, PageLoader, Select } from "@/shared/ui/primitives";
import { CopyButton } from "@/shared/ui/inputs";

interface ApiKeyRow {
  id: string;
  name: string;
  prefix: string;
  role: Role;
  revoked: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export function ApiKeysTab() {
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: () => http.get<ApiKeyRow[]>("/org/api-keys") });
  const nav = useNavigate();
  const [revoking, setRevoking] = useState<ApiKeyRow | null>(null);
  const revoke = useAction((id: string) => http.del(`/org/api-keys/${id}`), { success: "Key revoked", invalidate: [["api-keys"]], onSuccess: () => setRevoking(null) });

  if (keys.isLoading) return <PageLoader />;
  const list = keys.data ?? [];
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="API keys"
          description="Use the full REST API from scripts, CI or other apps. A key is scoped to this organization and can never exceed your role."
          actions={<Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => nav("/settings/api-keys/new")}>Create key</Button>}
        />
        {list.length === 0 ? (
          <EmptyState icon={<KeyRound className="size-5" />} title="No API keys" description="Create one to call agents, teams and workflows programmatically." className="m-4 border-0" />
        ) : (
          <ul className="divide-y divide-border">
            {list.map((k) => (
              <li key={k.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate text-sm font-medium">{k.name}</span>
                    <Badge tone="muted" className="capitalize">{k.role}</Badge>
                    {k.revoked && <Badge tone="danger">Revoked</Badge>}
                    {!k.revoked && k.expires_at && new Date(k.expires_at) < new Date() && <Badge tone="warning">Expired</Badge>}
                  </div>
                  <div className="mt-0.5 truncate text-xs text-muted">
                    <span className="font-mono">{k.prefix}…</span> · created {timeAgo(k.created_at)} · {k.last_used_at ? `last used ${timeAgo(k.last_used_at)}` : "never used"}
                    {k.expires_at && <> · expires {formatDate(k.expires_at)}</>}
                  </div>
                </div>
                {!k.revoked && (
                  <Button size="sm" variant="outline" onClick={() => setRevoking(k)}>Revoke</Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <ConfirmDialog open={!!revoking} onClose={() => setRevoking(null)} onConfirm={() => revoking && revoke.mutate(revoking.id)} loading={revoke.isPending} title={`Revoke “${revoking?.name}”?`} description="Requests using this key will be rejected immediately." confirmLabel="Revoke" />
    </div>
  );
}

/** /settings/api-keys/new: create a key, then reveal it once on the same page. */
export function NewApiKeyPage() {
  const { projectId } = useAuth();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [days, setDays] = useState("90");
  const [created, setCreated] = useState<string | null>(null);
  const create = useAction(() => http.post<{ key: string }>("/org/api-keys", { name, role, expires_in_days: days ? Number(days) : null }), {
    invalidate: [["api-keys"]],
    onSuccess: (r) => setCreated(r.key),
  });
  const done = () => nav("/settings/api-keys");
  const origin = apiBase || window.location.origin;
  const curl = created
    ? `curl -X POST ${origin}/api/runs \\\n  -H "Authorization: Bearer ${created}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"project_id": "${projectId ?? "<project_id>"}", "target_type": "agent", "target_id": "<agent_id>", "input": {"message": "Hello"}, "wait": true}'`
    : "";
  return (
    <Page className="max-w-2xl">
      <PageHeader
        back="/settings/api-keys"
        icon={<IconTile icon={KeyRound} color="indigo" />}
        title={created ? "Your new API key" : "Create API key"}
        description={created ? "Copy it now. For your security it is shown only once." : "A key is scoped to this organization and can never exceed your role."}
      />
      <Card>
        {created ? (
          <>
            <div className="space-y-4 p-4 sm:p-5">
              <div className="flex gap-2 rounded-lg border border-amber-500/25 bg-amber-500/5 p-3 text-sm">
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" />
                <span>Copy this key now - it will not be shown again. Store it like a password.</span>
              </div>
              <div className="flex gap-2">
                <Input readOnly value={created} className="font-mono text-xs" />
                <CopyButton text={created} />
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-xs font-medium text-muted">Example: run an agent and wait for the result</span>
                  <CopyButton text={curl} label="Copy" />
                </div>
                <pre className="overflow-x-auto rounded-lg border border-border bg-surface-2 p-3 font-mono text-[11px] leading-relaxed">{curl}</pre>
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
              <Button onClick={done}>Done</Button>
            </div>
          </>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) create.mutate();
            }}
          >
            <div className="space-y-4 p-4 sm:p-5">
              <Field label="Name">
                <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="CI pipeline" />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Role">
                  <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                    <option value="viewer">Viewer (read-only)</option>
                    <option value="member">Member (build & run)</option>
                    <option value="admin">Admin</option>
                  </Select>
                </Field>
                <Field label="Expires after (days)" hint="Empty = never">
                  <Input type="number" min={1} max={3650} value={days} onChange={(e) => setDays(e.target.value)} />
                </Field>
              </div>
            </div>
            <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
              <Button type="button" variant="outline" onClick={done}>Cancel</Button>
              <Button type="submit" loading={create.isPending} disabled={!name.trim()}>Create key</Button>
            </div>
          </form>
        )}
      </Card>
    </Page>
  );
}
