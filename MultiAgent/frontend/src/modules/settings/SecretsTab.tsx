import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Info, KeyRound, Plus, Trash2 } from "lucide-react";
import { http } from "@/shared/lib/api";
import { timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { IconTile } from "@/shared/ui/icons";
import { Button, Card, CardHeader, EmptyState, Field, Input, PageLoader } from "@/shared/ui/primitives";

interface SecretRow {
  id: string;
  name: string;
  description: string;
  preview: string;
  updated_at: string;
}

export function SecretsTab() {
  const secrets = useQuery({ queryKey: ["secrets"], queryFn: () => http.get<SecretRow[]>("/org/secrets") });
  const nav = useNavigate();
  const [removing, setRemoving] = useState<SecretRow | null>(null);
  const remove = useAction((id: string) => http.del(`/org/secrets/${id}`), { success: "Secret deleted", invalidate: [["secrets"]], onSuccess: () => setRemoving(null) });

  if (secrets.isLoading) return <PageLoader />;
  const list = secrets.data ?? [];
  return (
    <div className="space-y-5">
      <div className="flex gap-3 rounded-xl border border-border bg-surface p-4 text-sm">
        <Info className="mt-0.5 size-4 shrink-0 text-primary" />
        <div className="space-y-1 text-muted">
          <p>
            Secrets are encrypted at rest and never returned in full. Reference them in custom HTTP tools as{" "}
            <code className="rounded bg-surface-2 px-1 font-mono text-xs text-fg">{"{{ secrets.NAME }}"}</code> (URL, headers or body); they are redacted from tool output.
          </p>
          <p>
            Add <code className="rounded bg-surface-2 px-1 font-mono text-xs text-fg">TAVILY_API_KEY</code> or <code className="rounded bg-surface-2 px-1 font-mono text-xs text-fg">BRAVE_API_KEY</code> to upgrade web search from keyless DuckDuckGo.
          </p>
        </div>
      </div>
      <Card>
        <CardHeader title="Secrets" description={`${list.length} stored`} actions={<Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => nav("/settings/secrets/new")}>Add secret</Button>} />
        {list.length === 0 ? (
          <EmptyState icon={<KeyRound className="size-5" />} title="No secrets yet" description="Store API tokens for your custom tools and web search providers." className="m-4 border-0" />
        ) : (
          <ul className="divide-y divide-border">
            {list.map((s) => (
              <li key={s.id} className="flex items-center gap-3 px-4 py-3">
                <KeyRound className="size-4 shrink-0 text-muted" />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-mono text-sm font-medium">{s.name}</div>
                  <div className="truncate text-xs text-muted">
                    <span className="font-mono">{s.preview}</span>
                    {s.description && <> · {s.description}</>} · updated {timeAgo(s.updated_at)}
                  </div>
                </div>
                <Link to={`/settings/secrets/${encodeURIComponent(s.name)}`} className="inline-flex h-8 shrink-0 items-center rounded-lg border border-border bg-surface px-3 text-xs font-medium hover:bg-surface-2">Replace</Link>
                <Button variant="ghost" size="icon" onClick={() => setRemoving(s)} aria-label={`Delete ${s.name}`}>
                  <Trash2 className="size-4 text-muted" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <ConfirmDialog open={!!removing} onClose={() => setRemoving(null)} onConfirm={() => removing && remove.mutate(removing.id)} loading={remove.isPending} title={`Delete ${removing?.name}?`} description="Tools referencing this secret will stop working." />
    </div>
  );
}

/** /settings/secrets/new and /settings/secrets/:name (replace the value of an existing secret). */
export function SecretPage() {
  const { name: existing } = useParams();
  const nav = useNavigate();
  const secrets = useQuery({ queryKey: ["secrets"], queryFn: () => http.get<SecretRow[]>("/org/secrets"), enabled: !!existing });
  const current = existing ? secrets.data?.find((x) => x.name === existing) : undefined;
  const [name, setName] = useState(existing ?? "");
  const [value, setValue] = useState("");
  const [description, setDescription] = useState<string | null>(null);
  const desc = description ?? current?.description ?? "";
  const valid = /^[A-Za-z_][A-Za-z0-9_]*$/.test(name);
  const done = () => nav("/settings/secrets");
  const save = useAction(() => http.post("/org/secrets", { name, value, description: desc }), { success: "Secret saved", invalidate: [["secrets"]], onSuccess: done });
  if (existing && secrets.isLoading) return <PageLoader />;
  return (
    <Page className="max-w-2xl">
      <PageHeader
        back="/settings/secrets"
        icon={<IconTile icon={KeyRound} color="indigo" />}
        title={existing ? `Replace ${existing}` : "Add secret"}
        description="Encrypted at rest and never returned in full. Reference it in custom HTTP tools as {{ secrets.NAME }}."
      />
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && value) save.mutate();
          }}
        >
          <div className="space-y-4 p-4 sm:p-5">
            <Field label="Name" error={name && !valid ? "Letters, numbers and underscores; must not start with a number" : undefined}>
              <Input autoFocus={!existing} disabled={!!existing} value={name} onChange={(e) => setName(e.target.value.toUpperCase())} placeholder="GITHUB_TOKEN" className="font-mono" />
            </Field>
            <Field label="Value">
              <Input type="password" autoComplete="off" autoFocus={!!existing} value={value} onChange={(e) => setValue(e.target.value)} />
            </Field>
            <Field label="Description (optional)">
              <Input value={desc} onChange={(e) => setDescription(e.target.value)} />
            </Field>
          </div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
            <Button type="button" variant="outline" onClick={done}>Cancel</Button>
            <Button type="submit" loading={save.isPending} disabled={!valid || !value}>Save secret</Button>
          </div>
        </form>
      </Card>
    </Page>
  );
}
