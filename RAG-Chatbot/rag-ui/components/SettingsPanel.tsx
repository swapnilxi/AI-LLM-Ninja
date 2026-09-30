"use client";

import { useEffect, useState } from "react";
import { api, Catalog, getToken, Settings, setToken } from "@/lib/api";
import { Icon, IconName } from "./Icons";
import { Card, PageHeader, Spinner, useToast } from "./ui";

type TestResult = { ok: boolean; detail: string; ms: number };
type Section = "llm" | "embedding" | "store" | "rag" | "access";

const LABELS: Record<string, string> = {
  ollama_base_url: "Ollama URL", gemini_api_key: "Gemini API key", deepseek_api_key: "DeepSeek API key",
  deepseek_base_url: "DeepSeek base URL", openrouter_api_key: "OpenRouter API key", openrouter_base_url: "OpenRouter base URL",
  openai_api_key: "OpenAI API key", openai_base_url: "OpenAI base URL (or any compatible server)",
  groq_api_key: "Groq API key", groq_base_url: "Groq base URL",
  embedding_dimensions: "Dimensions (0 = default)", chroma_path: "Chroma folder",
  database_url: "Postgres / Neon connection string", vector_table: "Table / collection name",
};
const SECRET = new Set(["gemini_api_key", "deepseek_api_key", "openrouter_api_key", "openai_api_key", "groq_api_key", "database_url"]);
const NUMERIC = new Set(["embedding_dimensions"]);
// changing these makes existing vectors stale
const REINDEX_KEYS = ["embedding_provider", "embedding_model", "embedding_dimensions", "chunk_size", "chunk_overlap"];

const SECTIONS: { id: Section; label: string; icon: IconName; blurb: string }[] = [
  { id: "llm", label: "LLM", icon: "cpu", blurb: "The model that writes answers. Local (Ollama) or hosted (Gemini, OpenAI, Groq, DeepSeek, OpenRouter)." },
  { id: "embedding", label: "Embeddings", icon: "zap", blurb: "Turns text into vectors for search. Changing it requires rebuilding the index." },
  { id: "store", label: "Vector DB", icon: "database", blurb: "Where vectors live: local Chroma, local Postgres, or Neon." },
  { id: "rag", label: "RAG", icon: "sliders", blurb: "How documents are chunked, retrieved and turned into prompts." },
  { id: "access", label: "Access", icon: "key", blurb: "Browser-side settings and exporting your configuration." },
];
const sectionOf = (k: string): Section =>
  k.startsWith("llm_") || /_api_key$|_base_url$/.test(k) ? (k.startsWith("embedding") ? "embedding" : "llm")
  : k.startsWith("embedding_") ? "embedding"
  : ["vector_store", "chroma_path", "database_url", "vector_table"].includes(k) ? "store" : "rag";

export default function SettingsPanel({ onSaved }: { onSaved?: () => void }) {
  const toast = useToast();
  const [cat, setCat] = useState<Catalog | null>(null);
  const [saved, setSaved] = useState<Settings | null>(null);
  const [form, setForm] = useState<Settings>({});
  const [overrides, setOverrides] = useState<string[]>([]);
  const [editable, setEditable] = useState(true);
  const [tests, setTests] = useState<Record<string, TestResult | "running">>({});
  const [models, setModels] = useState<Record<string, string[]>>({});
  const [offline, setOffline] = useState<string | null>(null);
  const [section, setSection] = useState<Section>("llm");
  const [token, setTok] = useState(getToken());

  async function load() {
    setOffline(null);
    try {
      const [c, s] = await Promise.all([api<Catalog>("/catalog"), api("/config")]);
      setCat(c); setSaved(s.values); setForm(s.values); setOverrides(s.ui_overrides); setEditable(s.editable);
    } catch (e) { setOffline((e as Error).message); }
  }
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!cat || !saved) {
    return (
      <div className="page settings">
        <PageHeader title="Settings" />
        {offline ? (
          <Card className="bad">
            <b>Backend is offline</b>
            <p className="muted small">Cannot fetch configuration while the backend is unreachable.</p>
            <button type="button" onClick={load}>Retry connection</button>
          </Card>
        ) : <div className="muted row"><Spinner />Connecting to backend settings…</div>}
      </div>
    );
  }

  const set = (k: string, v: string | number | boolean) => setForm((f) => ({ ...f, [k]: v }));
  const dirty = Object.keys(form).filter((k) => form[k] !== saved[k]);
  const dirtyIn = (s: Section) => dirty.some((k) => sectionOf(k) === s);
  const needsReindex = dirty.some((k) => REINDEX_KEYS.includes(k)) || dirty.includes("vector_store");

  // NOTE: these three are plain render helpers (called as functions), not components:
  // defining components inside a component remounts them on every keystroke and steals input focus.
  function Field({ name, label, type, hint }: { name: string; label?: string; type?: "text" | "number" | "checkbox" | "textarea" | "range"; hint?: string }) {
    const t = type ?? (SECRET.has(name) ? "password" : NUMERIC.has(name) ? "number" : "text");
    const common = { disabled: !editable, id: name };
    return (
      <label key={name} className={`field ${t === "checkbox" ? "check" : ""}`}>
        <span>{label ?? LABELS[name] ?? name}{overrides.includes(name) && <em className="ui-tag" title="Set from the UI; overrides .env">UI</em>}</span>
        {t === "checkbox" ? (
          <input type="checkbox" {...common} checked={!!form[name]} onChange={(e) => set(name, e.target.checked)} />
        ) : t === "textarea" ? (
          <textarea {...common} rows={7} value={String(form[name] ?? "")} onChange={(e) => set(name, e.target.value)} />
        ) : (
          <input
            {...common} type={t === "range" ? "number" : t} step={t === "range" ? "any" : undefined}
            autoComplete="off" value={String(form[name] ?? "")}
            onChange={(e) => set(name, t === "number" || t === "range" ? Number(e.target.value) : e.target.value)}
          />
        )}
        {hint && <small className="muted">{hint}</small>}
      </label>
    );
  }

  function ModelField({ kind, provider }: { kind: "llm" | "embedding"; provider: string }) {
    const info = cat![kind][provider];
    const key = `${kind}_model`;
    const list = models[`${kind}:${provider}`] ?? info.models ?? [];
    const listId = `models-${kind}`;
    return (
      <label className="field">
        <span>Model <em>(empty = {info.default_model})</em></span>
        <div className="row">
          <input list={listId} disabled={!editable} value={String(form[key] ?? "")} placeholder={info.default_model} onChange={(e) => set(key, e.target.value)} />
          <datalist id={listId}>{list.map((m) => <option key={m} value={m} />)}</datalist>
          <button type="button" className="secondary" onClick={async () => {
            try {
              const r = await api("/models", "POST", { kind, values: form });
              setModels((m) => ({ ...m, [`${kind}:${provider}`]: r.models }));
              toast("ok", `${r.models.length} ${provider} models loaded — click the model box to choose.`);
            } catch (e) { toast("bad", `Could not list models: ${(e as Error).message}`); }
          }}>Fetch list</button>
        </div>
      </label>
    );
  }

  function TestButton({ target }: { target: "llm" | "embedding" | "vector_store" }) {
    const r = tests[target];
    return (
      <div className="row test">
        <button type="button" className="secondary" disabled={r === "running"} onClick={async () => {
          setTests((t) => ({ ...t, [target]: "running" }));
          try { const res = await api<TestResult>("/config/test", "POST", { target, values: form }); setTests((t) => ({ ...t, [target]: res })); }
          catch (e) { setTests((t) => ({ ...t, [target]: { ok: false, detail: (e as Error).message, ms: 0 } })); }
        }}>{r === "running" ? <><Spinner size={14} />Testing…</> : <><Icon name="zap" size={14} />Test connection</>}</button>
        {r && r !== "running" && <span className={r.ok ? "okText" : "error"}>{r.ok ? "✓" : "✗"} {r.detail} <span className="muted">({r.ms} ms)</span></span>}
      </div>
    );
  }

  function applyPreset(id: string) {
    const p = cat!.presets[id];
    setForm((f) => {
      const next = { ...f };
      for (const [k, v] of Object.entries(p.values)) if (!(SECRET.has(k) && f[k])) next[k] = v; // never clobber saved secrets
      return next;
    });
    toast("info", `Preset “${p.label}” applied — review, then Save.`);
  }

  async function save() {
    try {
      const changed = Object.fromEntries(dirty.map((k) => [k, form[k]]));
      const r = await api("/config", "PUT", { values: changed });
      setSaved(r.values); setForm(r.values); setOverrides(r.ui_overrides);
      toast("ok", needsReindex ? "Saved. Embedding/chunking changed — run “Rebuild index” in Documents." : "Settings saved");
      onSaved?.();
    } catch (e) { toast("bad", (e as Error).message); }
  }

  async function resetAll() {
    if (!confirm("Discard all UI overrides and go back to .env / defaults?")) return;
    const r = await api("/config", "DELETE");
    setSaved(r.values); setForm(r.values); setOverrides(r.ui_overrides);
    toast("ok", "Reset to .env defaults"); onSaved?.();
  }

  /** the current form as .env lines, so a UI-tuned setup can be committed to the backend */
  function copyEnv() {
    const lines = Object.entries(form).map(([k, v]) =>
      SECRET.has(k) ? `# ${k.toUpperCase()}=  (secret: paste your own value)` : `${k.toUpperCase()}=${String(v).includes("\n") ? JSON.stringify(v) : v}`);
    navigator.clipboard.writeText(lines.join("\n")).then(() => toast("ok", "Copied as .env lines (secrets left out)"), () => toast("bad", "Copy failed"));
  }

  const llm = String(form.llm_provider), emb = String(form.embedding_provider), vs = String(form.vector_store);
  const cur = SECTIONS.find((s) => s.id === section)!;

  return (
    <div className="page settings">
      <PageHeader title="Settings" subtitle="Changes saved here override the backend .env file."
        actions={
          <select className="pill-select" defaultValue="" disabled={!editable} onChange={(e) => { if (e.target.value) applyPreset(e.target.value); e.target.value = ""; }}>
            <option value="">Load a preset…</option>
            {Object.entries(cat.presets).map(([id, p]) => <option key={id} value={id}>{p.label}</option>)}
          </select>
        } />

      {!editable && <div className="banner bad"><Icon name="alert" size={16} /><span>Configuration is locked on this deployment (<code>ALLOW_UI_CONFIG=false</code>). Edit the backend <code>.env</code> instead.</span></div>}
      {needsReindex && <div className="banner warn"><Icon name="alert" size={16} /><span>These changes make the current index stale. After saving, use <b>Rebuild index</b> in Documents.</span></div>}

      <div className="seg" role="tablist">
        {SECTIONS.map((s) => (
          <button key={s.id} role="tab" aria-selected={section === s.id} className={section === s.id ? "on" : ""} onClick={() => setSection(s.id)}>
            <Icon name={s.icon} size={15} />{s.label}{dirtyIn(s.id) && <i className="dirty-dot" title="Unsaved changes" />}
          </button>
        ))}
      </div>

      <Card title={cur.label} icon={cur.icon}>
        <p className="muted small" style={{ marginTop: -4 }}>{cur.blurb}</p>

        {section === "llm" && (
          <>
            <label className="field"><span>Provider</span>
              <select disabled={!editable} value={llm} onChange={(e) => { set("llm_provider", e.target.value); set("llm_model", ""); }}>
                {Object.entries(cat.llm).map(([id, p]) => <option key={id} value={id}>{p.label}</option>)}
              </select>
            </label>
            {ModelField({ kind: "llm", provider: llm })}
            {cat.llm[llm].fields.map((f) => Field({ name: f }))}
            <div className="grid2">{Field({ name: "llm_temperature", label: "Temperature", type: "range", hint: "0 = focused, higher = more creative" })}{Field({ name: "llm_max_tokens", label: "Max output tokens (0 = default)", type: "number" })}</div>
            {TestButton({ target: "llm" })}
          </>
        )}

        {section === "embedding" && (
          <>
            <label className="field"><span>Provider</span>
              <select disabled={!editable} value={emb} onChange={(e) => { set("embedding_provider", e.target.value); set("embedding_model", ""); }}>
                {Object.entries(cat.embedding).map(([id, p]) => <option key={id} value={id}>{p.label}</option>)}
              </select>
            </label>
            {ModelField({ kind: "embedding", provider: emb })}
            {cat.embedding[emb].fields.map((f) => Field({ name: f }))}
            {TestButton({ target: "embedding" })}
          </>
        )}

        {section === "store" && (
          <>
            <label className="field"><span>Backend</span>
              <select disabled={!editable} value={vs} onChange={(e) => set("vector_store", e.target.value)}>
                {Object.entries(cat.vector_store).map(([id, p]) => <option key={id} value={id}>{p.label}</option>)}
              </select>
            </label>
            {cat.vector_store[vs].fields.map((f) => Field({ name: f }))}
            {vs === "postgres" && <p className="muted small">Local: <code>docker compose up -d</code> → <code>postgresql://rag:rag@localhost:5432/rag</code>. Neon: paste the connection string (with <code>?sslmode=require</code>).</p>}
            {TestButton({ target: "vector_store" })}
          </>
        )}

        {section === "rag" && (
          <>
            <div className="grid2">
              {Field({ name: "chunk_size", label: "Chunk size (chars)", type: "number", hint: "Smaller = more precise, larger = more context" })}
              {Field({ name: "chunk_overlap", label: "Chunk overlap (chars)", type: "number" })}
              {Field({ name: "top_k", label: "Top-K chunks", type: "number", hint: "How many passages are sent to the LLM" })}
              {Field({ name: "score_threshold", label: "Min similarity (0–1)", type: "range", hint: "Drop weak matches" })}
              {Field({ name: "history_turns", label: "Chat history turns", type: "number" })}
              {Field({ name: "auto_sync_interval", label: "Auto-sync every N seconds (0 = off)", type: "number" })}
            </div>
            {Field({ name: "query_rewrite", label: "Rewrite follow-up questions before searching (extra LLM call)", type: "checkbox" })}
            {Field({ name: "rag_data_dir", label: "Documents folder" })}
            {Field({ name: "system_prompt", label: "System prompt", type: "textarea" })}
          </>
        )}

        {section === "access" && (
          <>
            <label className="field"><span>Backend API token <em>(only if the backend sets ADMIN_TOKEN)</em></span>
              <input type="password" value={token} onChange={(e) => { setTok(e.target.value); setToken(e.target.value); }} />
            </label>
            <div className="row wrap" style={{ marginTop: 16 }}>
              <button className="secondary" onClick={copyEnv}><Icon name="copy" size={15} />Copy as .env</button>
              <button className="secondary" onClick={resetAll} disabled={!editable || overrides.length === 0}>Reset to .env</button>
            </div>
            <p className="muted small">“Copy as .env” turns what you tuned here into lines for <code>rag-be/.env</code> (API keys are left out on purpose).</p>
          </>
        )}
      </Card>

      <div className="savebar">
        <span className="muted small">{dirty.length ? `${dirty.length} unsaved change${dirty.length > 1 ? "s" : ""}` : "All changes saved"}</span>
        <div className="row">
          <button className="secondary" onClick={() => setForm(saved)} disabled={dirty.length === 0}>Discard</button>
          <button onClick={save} disabled={!editable || dirty.length === 0}>Save changes</button>
        </div>
      </div>
    </div>
  );
}
