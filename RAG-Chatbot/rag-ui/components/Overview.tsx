"use client";

import { useEffect, useMemo, useState } from "react";
import { api, AppStatus, DOC_PENDING, DocRow, Profile, profileUrl, Settings } from "@/lib/api";
import { kindOf } from "@/utils/files";
import { Icon, IconName } from "./Icons";
import type { View } from "./Sidebar";
import { Badge, Card, PageHeader, Spinner, useToast } from "./ui";

type Test = { ok: boolean; detail: string; ms: number };
type Target = "llm" | "embedding" | "vector_store";

const KEY_FIELD: Record<string, string> = {
  gemini: "gemini_api_key", openai: "openai_api_key", groq: "groq_api_key", deepseek: "deepseek_api_key", openrouter: "openrouter_api_key",
};

export default function Overview({ status, config, profile, onNavigate, onRefresh }: {
  status: AppStatus | null; config: Settings | null; profile: Profile | null; onNavigate: (v: View) => void; onRefresh: () => void;
}) {
  const toast = useToast();
  const [docs, setDocs] = useState<DocRow[] | null>(null);
  const [tests, setTests] = useState<Partial<Record<Target, Test | "running">>>({});

  useEffect(() => {
    if (!profile) { setDocs([]); return; }
    api<{ documents: DocRow[] }>(profileUrl(profile.id, "/documents")).then((d) => setDocs(d.documents)).catch(() => setDocs([]));
  }, [status?.sync.state, status?.store.chunks, profile?.id]);

  const provider = String(config?.llm_provider ?? "");
  const keyReady = !config ? false : provider === "ollama" || !!config[KEY_FIELD[provider]];
  const chunks = status?.store.chunks ?? 0;
  const files = docs ?? [];
  const pending = files.filter((f) => DOC_PENDING.includes(f.status)).length;

  const steps: { done: boolean; title: string; hint: string; go: View; cta: string }[] = [
    { done: keyReady, title: "Choose an LLM and add its API key", hint: provider === "ollama" ? "Ollama needs no key — make sure it is running." : `Provider: ${provider || "?"}`, go: "settings", cta: "Open settings" },
    { done: !!status?.store.ok, title: "Connect a vector database", hint: status?.store.ok ? `${status.store.backend} connected` : status?.store.error ?? "Backend unreachable", go: "settings", cta: "Configure" },
    { done: files.length > 0, title: `Add documents to ${profile?.name ?? "a profile"}`, hint: "PDF, Word, Markdown, text, CSV, JSON, HTML", go: "documents", cta: "Add files" },
    { done: chunks > 0, title: "Build the index", hint: pending ? `${pending} file(s) waiting to be indexed` : "Sync turns your files into searchable chunks", go: "documents", cta: "Sync" },
  ];
  const doneCount = steps.filter((s) => s.done).length;
  const ready = doneCount === steps.length;

  const byType = useMemo(() => {
    const m = new Map<string, number>();
    for (const f of files) m.set(kindOf(f.filename)?.label ?? "Other", (m.get(kindOf(f.filename)?.label ?? "Other") ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [files]);

  async function runTest(target: Target) {
    setTests((t) => ({ ...t, [target]: "running" }));
    try {
      const r = await api<Test>("/config/test", "POST", { target, values: {} });
      setTests((t) => ({ ...t, [target]: r }));
    } catch (e) {
      setTests((t) => ({ ...t, [target]: { ok: false, detail: (e as Error).message, ms: 0 } }));
    }
  }

  const sync = status?.sync;
  const tile = (icon: IconName, label: string, value: string | number, sub?: string) => (
    <div className="tile"><div className="tile-icon"><Icon name={icon} size={18} /></div><div><div className="tile-value">{value}</div><div className="tile-label">{label}</div>{sub && <div className="tile-sub muted small">{sub}</div>}</div></div>
  );

  const row = (target: Target, icon: IconName, title: string, main: string, sub: string) => {
    const t = tests[target];
    return (
      <div className="cfg-row">
        <div className="tile-icon"><Icon name={icon} size={18} /></div>
        <div className="cfg-main"><div className="cfg-title">{title}</div><div>{main}</div><div className="muted small">{sub}</div>
          {t && t !== "running" && <div className={`small ${t.ok ? "okText" : "error"}`}>{t.ok ? "✓" : "✗"} {t.detail} <span className="muted">({t.ms} ms)</span></div>}
        </div>
        <button className="secondary sm" disabled={t === "running" || !config} onClick={() => runTest(target)}>{t === "running" ? <Spinner size={12} /> : "Test"}</button>
      </div>
    );
  };

  return (
    <div className="page">
      <PageHeader title="Overview" subtitle="Health of your RAG pipeline at a glance."
        actions={<button className="secondary" onClick={onRefresh}><Icon name="refresh" size={15} />Refresh</button>} />

      <Card className={ready ? "hero ready" : "hero"}>
        <div className="hero-top">
          <div>
            <h2>{ready ? "You're all set 🎉" : "Get started"}</h2>
            <p className="muted">{ready ? "Your documents are indexed. Ask them anything." : `${doneCount} of ${steps.length} steps done`}</p>
          </div>
          {ready && <button onClick={() => onNavigate("chat")}><Icon name="chat" size={16} />Start chatting</button>}
        </div>
        <div className="progress"><div style={{ width: `${(doneCount / steps.length) * 100}%` }} /></div>
        <ol className="steps">
          {steps.map((s, i) => (
            <li key={i} className={s.done ? "done" : ""}>
              <span className="step-mark">{s.done ? <Icon name="check" size={14} /> : i + 1}</span>
              <div className="step-text"><b>{s.title}</b><span className="muted small">{s.hint}</span></div>
              {!s.done && <button className="secondary sm" onClick={() => onNavigate(s.go)}>{s.cta}</button>}
            </li>
          ))}
        </ol>
      </Card>

      <div className="tiles">
        {tile("doc", "Documents", files.length, pending ? `${pending} pending` : "all indexed")}
        {tile("layers", "Indexed chunks", chunks.toLocaleString())}
        {tile("database", "Vector store", status?.store.ok ? status.store.backend ?? "ok" : "offline", status?.store.location?.split("/").slice(-2).join("/"))}
        {tile("cpu", "LLM", provider || "—", config?.llm_model ? String(config.llm_model) : "default model")}
      </div>

      <div className="grid-2">
        <Card title="Active configuration" icon="sliders" actions={<button className="link" onClick={() => onNavigate("settings")}>Edit</button>}>
          {config ? (
            <>
              {row("llm", "cpu", "LLM", `${config.llm_provider} · ${config.llm_model || "default model"}`, keyReady ? "API key configured" : "⚠ API key missing")}
              {row("embedding", "zap", "Embeddings", `${config.embedding_provider} · ${config.embedding_model || "default model"}`, "Converts text to vectors")}
              {row("vector_store", "database", "Vector database", String(config.vector_store), config.vector_store === "chroma" ? String(config.chroma_path) : "Postgres / Neon (pgvector)")}
            </>
          ) : <div className="muted">Configuration unavailable — is the backend running?</div>}
        </Card>

        <div className="stack">
          <Card title="Indexing" icon="refresh" actions={<button className="link" onClick={() => onNavigate("documents")}>Manage</button>}>
            {sync?.state === "running" && <div className="row"><Spinner /><span>{sync.message || "Syncing…"}</span></div>}
            {sync?.state === "error" && <div className="error">✗ {sync.error}</div>}
            {sync?.state === "done" && sync.result && (
              <div className="small">
                <Badge tone="ok">last sync ok</Badge>{" "}
                +{sync.result.added.length} added · {sync.result.updated.length} updated · {sync.result.removed.length} removed · {sync.result.seconds}s
                {Object.entries(sync.result.errors).map(([f, m]) => <div key={f} className="error">{f}: {m}</div>)}
              </div>
            )}
            {(!sync || sync.state === "idle") && <div className="muted small">No sync has run in this session.</div>}
            <div className="row" style={{ marginTop: 12 }}>
              <button disabled={sync?.state === "running"} onClick={async () => { try { await api("/profiles/sync", "POST"); onRefresh(); toast("info", "Sync started"); } catch (e) { toast("bad", (e as Error).message); } }}>Sync now</button>
            </div>
          </Card>

          <Card title="Documents by type" icon="file">
            {byType.length === 0 ? <div className="muted small">No documents yet.</div> : byType.map(([label, n]) => (
              <div key={label} className="bar-row"><span>{label}</span><div className="bar"><div style={{ width: `${(n / files.length) * 100}%` }} /></div><span className="muted small">{n}</span></div>
            ))}
          </Card>
        </div>
      </div>
    </div>
  );
}
