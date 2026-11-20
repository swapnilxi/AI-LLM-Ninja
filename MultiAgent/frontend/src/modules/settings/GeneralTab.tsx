import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { cn, formatNumber } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useProviders } from "@/modules/settings/api";
import { Button, Card, CardHeader, Field, Input, Select, Textarea } from "@/shared/ui/primitives";
import { MultiSelect } from "@/shared/ui/inputs";

interface Usage {
  tokens_today: number;
  daily_token_limit: number;
  active_runs: number;
  max_concurrent_runs: number;
}

function Meter({ label, used, limit, format = (n: number) => String(n) }: { label: string; used: number; limit: number; format?: (n: number) => string }) {
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0;
  const tone = pct >= 90 ? "bg-[#d03b3b] dark:bg-[#e66767]" : pct >= 70 ? "bg-[#fab219]" : "bg-[#2a78d6] dark:bg-[#3987e5]";
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className="font-medium">
          {format(used)} <span className="text-muted">/ {limit ? format(limit) : "∞"}</span>
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#cde2fb] dark:bg-[#184f95]/50" role="meter" aria-label={label} aria-valuenow={used} aria-valuemin={0} aria-valuemax={limit || undefined}>
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${limit ? Math.max(pct, used ? 2 : 0) : 0}%` }} />
      </div>
    </div>
  );
}

export function GeneralTab() {
  const { org, can, refresh } = useAuth();
  const providers = useProviders();
  const usage = useQuery({ queryKey: ["org-usage"], queryFn: () => http.get<Usage>("/org/usage"), refetchInterval: 30_000 });
  const admin = can("admin");
  const [name, setName] = useState("");
  const [context, setContext] = useState("");
  const [defaultProvider, setDefaultProvider] = useState("");
  const [defaultModel, setDefaultModel] = useState("");
  const [search, setSearch] = useState("auto");
  const [tokenLimit, setTokenLimit] = useState("");
  const [concurrency, setConcurrency] = useState("");
  const [allowed, setAllowed] = useState<string[]>([]);

  useEffect(() => {
    if (!org) return;
    const s = org.settings ?? {};
    setName(org.name);
    setContext(org.context ?? "");
    setDefaultProvider(s.default_provider ?? "");
    setDefaultModel(s.default_model ?? "");
    setSearch(s.web_search_provider ?? "auto");
    setTokenLimit(s.daily_token_limit !== undefined && s.daily_token_limit !== null ? String(s.daily_token_limit) : "");
    setConcurrency(s.max_concurrent_runs !== undefined && s.max_concurrent_runs !== null ? String(s.max_concurrent_runs) : "");
    setAllowed(s.allowed_providers ?? []);
  }, [org]);

  const list = providers.data?.providers ?? [];
  const models = list.find((p) => p.key === defaultProvider)?.models ?? [];
  const save = useAction(
    () =>
      http.patch("/org", {
        name,
        context,
        settings: {
          default_provider: defaultProvider || null,
          default_model: defaultProvider ? defaultModel || null : null,
          web_search_provider: search === "auto" ? null : search,
          daily_token_limit: tokenLimit === "" ? null : Math.max(0, parseInt(tokenLimit, 10) || 0),
          max_concurrent_runs: concurrency === "" ? null : Math.max(0, parseInt(concurrency, 10) || 0),
          allowed_providers: allowed.length ? allowed : null,
        },
      }),
    { success: "Organization saved", invalidate: [["providers"], ["org-usage"]], onSuccess: () => refresh() },
  );

  const u = usage.data;
  const def = providers.data?.default;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
      <div className="space-y-5">
        <Card>
          <CardHeader title="Organization" />
          <div className="space-y-4 p-4">
            <Field label="Name">
              <Input disabled={!admin} value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Organization guidelines" hint="Injected into every agent's system prompt across all projects - brand voice, policies, compliance rules.">
              <Textarea disabled={!admin} rows={8} value={context} onChange={(e) => setContext(e.target.value)} placeholder="We are Acme Inc. Always be concise and professional. Never share customer data…" />
            </Field>
          </div>
        </Card>
        <Card>
          <CardHeader title="Models & tools" description="Agents set to the “Default” model use this. Leave empty to auto-pick the first configured provider." />
          <div className="grid gap-4 p-4 sm:grid-cols-2">
            <Field label="Default provider">
              <Select disabled={!admin} value={defaultProvider} onChange={(e) => setDefaultProvider(e.target.value)}>
                <option value="">Auto-detect</option>
                {list.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.label}
                    {p.configured ? "" : " (not configured)"}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Default model">
              <Input disabled={!admin || !defaultProvider} list="default-models" value={defaultModel} onChange={(e) => setDefaultModel(e.target.value)} placeholder={models[0] ?? "model id"} />
              <datalist id="default-models">
                {models.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </Field>
            <Field label="Web search provider" hint="Tavily / Brave need TAVILY_API_KEY / BRAVE_API_KEY secrets; DuckDuckGo needs no key.">
              <Select disabled={!admin} value={search} onChange={(e) => setSearch(e.target.value)}>
                <option value="auto">Auto (best available)</option>
                <option value="tavily">Tavily</option>
                <option value="brave">Brave Search</option>
                <option value="duckduckgo">DuckDuckGo</option>
              </Select>
            </Field>
            <div className="text-sm sm:pt-6">
              <span className="text-muted">Currently resolves to </span>
              <span className="font-medium">{def ? `${def.provider} · ${def.model}` : "…"}</span>
            </div>
            <Field label="Allowed providers" hint="Restrict which model providers agents may use. Empty = all." className="sm:col-span-2">
              <MultiSelect
                options={list.filter((p) => p.key !== "mock").map((p) => ({ value: p.key, label: p.label, badge: p.configured ? "configured" : undefined }))}
                value={allowed}
                onChange={(v) => admin && setAllowed(v)}
                maxHeight="max-h-48"
              />
            </Field>
          </div>
        </Card>
      </div>
      <div className="space-y-5">
        <Card>
          <CardHeader title="Usage & limits" description="Guardrails that protect your budget and the platform." />
          <div className="space-y-5 p-4">
            {u ? (
              <>
                <Meter label="Tokens today" used={u.tokens_today} limit={u.daily_token_limit} format={formatNumber} />
                <Meter label="Active runs" used={u.active_runs} limit={u.max_concurrent_runs} />
              </>
            ) : (
              <div className="text-sm text-muted">Loading…</div>
            )}
            <Field label="Daily token limit" hint="0 = unlimited. Empty = server default.">
              <Input disabled={!admin} type="number" min={0} value={tokenLimit} onChange={(e) => setTokenLimit(e.target.value)} placeholder="2000000" />
            </Field>
            <Field label="Max concurrent runs" hint="Empty = server default.">
              <Input disabled={!admin} type="number" min={0} value={concurrency} onChange={(e) => setConcurrency(e.target.value)} placeholder="8" />
            </Field>
          </div>
        </Card>
        {admin && (
          <Button className="w-full justify-center" icon={<Save className="size-4" />} loading={save.isPending} disabled={!name.trim()} onClick={() => save.mutate()}>
            Save settings
          </Button>
        )}
      </div>
    </div>
  );
}
