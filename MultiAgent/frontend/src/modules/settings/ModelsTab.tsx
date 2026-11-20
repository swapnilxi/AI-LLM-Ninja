import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CircleCheck, CircleX, Cpu, ExternalLink, KeyRound, Server, Trash2, Zap } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { ProviderInfo } from "@/modules/settings/types";
import { errMsg } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useProviders } from "@/modules/settings/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, EmptyState, Field, Input, PageLoader } from "@/shared/ui/primitives";
import { IconTile } from "@/shared/ui/icons";

const COLOR: Record<string, string> = {
  anthropic: "amber", openai: "emerald", groq: "rose", gemini: "sky", openrouter: "violet", deepseek: "indigo", mistral: "amber", ollama: "slate", openai_compatible: "teal",
};

export function ModelsTab() {
  const providers = useProviders();
  const { can } = useAuth();
  const admin = can("admin");
  const nav = useNavigate();
  const [testing, setTesting] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, { ok: boolean; message: string }>>({});
  const remove = useAction((key: string) => http.del(`/org/providers/${key}`), { success: "Provider key removed", invalidate: [["providers"]] });

  const test = async (p: ProviderInfo) => {
    setTesting(p.key);
    try {
      const r = await http.post<{ ok: boolean; message: string }>(`/org/providers/${p.key}/test`);
      setResults((x) => ({ ...x, [p.key]: r }));
    } catch (e) {
      setResults((x) => ({ ...x, [p.key]: { ok: false, message: errMsg(e) } }));
    } finally {
      setTesting(null);
    }
  };

  if (providers.isLoading) return <PageLoader />;
  const list = (providers.data?.providers ?? []).filter((p) => p.key !== "mock");
  const def = providers.data?.default;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-xl border border-indigo-500/20 bg-gradient-to-r from-primary-soft to-transparent p-4 sm:flex-row sm:items-center">
        <Cpu className="size-5 shrink-0 text-primary" />
        <div className="flex-1 text-sm">
          Agents on the <span className="font-medium">Default</span> model currently use{" "}
          <span className="font-mono text-[13px] font-medium">{def ? `${def.provider} / ${def.model}` : "…"}</span>
          {def?.provider === "mock" && <span className="text-muted"> - the offline demo model. Add a key below to use a real LLM.</span>}
        </div>
        <Link to="/settings/general" className="text-sm font-medium text-primary hover:underline">Change default</Link>
      </div>
      <p className="text-sm text-muted">Keys are encrypted at rest and never shown again in full. Org keys override server-wide keys from the environment.</p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {list.map((p) => {
          const r = results[p.key];
          const hasOrgConfig = !!p.org_key || !!p.base_url;
          return (
            <Card key={p.key} className="flex flex-col p-4">
              <div className="flex items-start gap-3">
                <IconTile icon={p.key === "ollama" || p.key === "openai_compatible" ? Server : Zap} color={COLOR[p.key] ?? "indigo"} size="sm" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate text-sm font-semibold">{p.label}</h3>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {p.configured ? <Badge tone="success" icon={<CircleCheck className="size-2.5" />}>Ready</Badge> : <Badge tone="muted">Not configured</Badge>}
                    {p.org_key && <Badge tone="primary" icon={<KeyRound className="size-2.5" />}>Org key {p.org_key !== "set" ? p.org_key : ""}</Badge>}
                    {p.server_key && <Badge tone="muted" icon={<Server className="size-2.5" />}>Server key</Badge>}
                  </div>
                </div>
              </div>
              {p.models.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {p.models.slice(0, 4).map((m) => (
                    <span key={m} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-muted">{m}</span>
                  ))}
                </div>
              )}
              {p.base_url && <div className="mt-2 truncate font-mono text-[11px] text-muted">{p.base_url}</div>}
              {r && (
                <div className={`mt-3 flex items-start gap-1.5 rounded-lg px-2.5 py-2 text-xs ${r.ok ? "bg-emerald-500/10 text-success" : "bg-red-500/10 text-danger"}`}>
                  {r.ok ? <CircleCheck className="mt-px size-3.5 shrink-0" /> : <CircleX className="mt-px size-3.5 shrink-0" />}
                  <span className="break-words">{r.message}</span>
                </div>
              )}
              <div className="mt-auto flex flex-wrap items-center gap-2 pt-4">
                {admin && (
                  <Button size="sm" variant={p.configured ? "outline" : "primary"} icon={<KeyRound className="size-3.5" />} onClick={() => nav(`/settings/models/${p.key}`)}>
                    {hasOrgConfig ? "Update" : p.needs_key ? "Add key" : "Configure"}
                  </Button>
                )}
                {admin && p.configured && (
                  <Button size="sm" variant="ghost" loading={testing === p.key} onClick={() => test(p)}>Test</Button>
                )}
                {admin && hasOrgConfig && (
                  <Button size="sm" variant="ghost" onClick={() => remove.mutate(p.key)} aria-label="Remove key">
                    <Trash2 className="size-3.5 text-muted" />
                  </Button>
                )}
                {p.docs && (
                  <a href={p.docs} target="_blank" rel="noopener noreferrer" className="ml-auto inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
                    Get key <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

/** /settings/models/:provider: set an org API key and/or base URL for one LLM provider. */
export function ProviderPage() {
  const { provider: key } = useParams();
  const providers = useProviders();
  const nav = useNavigate();
  const provider = providers.data?.providers.find((p) => p.key === key) ?? null;
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const url = baseUrl ?? provider?.base_url ?? "";
  const done = () => nav("/settings/models");
  const save = useAction(
    () => {
      const body: Record<string, string> = {};
      if (apiKey.trim()) body.api_key = apiKey.trim();
      body.base_url = url.trim();
      return http.put(`/org/providers/${provider!.key}`, body);
    },
    { success: "Provider saved", invalidate: [["providers"]], onSuccess: done },
  );
  if (providers.isLoading) return <PageLoader />;
  if (!provider)
    return (
      <Page className="max-w-2xl">
        <PageHeader back="/settings/models" title="Provider not found" />
        <EmptyState icon={<Cpu className="size-5" />} title="Unknown provider" description={`There is no LLM provider called “${key}”.`} />
      </Page>
    );
  const needsUrl = provider.key === "openai_compatible";
  return (
    <Page className="max-w-2xl">
      <PageHeader
        back="/settings/models"
        icon={<IconTile icon={provider.key === "ollama" || provider.key === "openai_compatible" ? Server : Zap} color={COLOR[provider.key] ?? "indigo"} />}
        title={`Configure ${provider.label}`}
        description="The key is encrypted with the server secret and only a masked preview is ever returned."
      />
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!(needsUrl && !url.trim())) save.mutate();
          }}
        >
          <div className="space-y-4 p-4 sm:p-5">
            <Field label={provider.needs_key ? "API key" : "API key (optional)"} hint={provider.org_key ? `Current: ${provider.org_key}. Leave empty to keep it.` : undefined}>
              <Input autoFocus type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={provider.key === "anthropic" ? "sk-ant-…" : "sk-…"} />
            </Field>
            <Field label={needsUrl ? "Base URL" : "Base URL (optional override)"} hint={provider.default_base_url ? `Default: ${provider.default_base_url}` : "OpenAI-compatible endpoint, e.g. https://api.together.xyz/v1"}>
              <Input value={url} onChange={(e) => setBaseUrl(e.target.value)} placeholder={provider.default_base_url || "https://…/v1"} />
            </Field>
            {provider.docs && (
              <a href={provider.docs} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
                Where do I get a key? <ExternalLink className="size-3" />
              </a>
            )}
          </div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
            <Button type="button" variant="outline" onClick={done}>Cancel</Button>
            <Button type="submit" loading={save.isPending} disabled={needsUrl && !url.trim()}>Save</Button>
          </div>
        </form>
      </Card>
    </Page>
  );
}
