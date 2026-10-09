"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, Faq, getToken, Profile, profileUrl, SyncStatus } from "@/lib/api";
import { Icon } from "./Icons";
import { Badge, Card, PageHeader, Spinner, useToast } from "./ui";

const TONE = { INDEXED: "ok", PENDING: "warn", FAILED: "bad", DISABLED: "muted" } as const;
type Filter = "all" | "enabled" | "disabled" | "pending" | "failed";
type Draft = { question: string; answer: string };

/** Accepts the export format `[{question, answer}]` (or `{faqs: [...]}`) and reports what is wrong, per item. */
function parseFaqJson(text: string): { items: Draft[]; errors: string[] } {
  let data: unknown;
  try { data = JSON.parse(text); } catch (e) { return { items: [], errors: [`Not valid JSON: ${(e as Error).message}`] }; }
  const list = Array.isArray(data) ? data : data && typeof data === "object" && Array.isArray((data as { faqs?: unknown }).faqs) ? (data as { faqs: unknown[] }).faqs : null;
  if (!list) return { items: [], errors: ['Expected an array like [{"question": "...", "answer": "..."}]'] };
  const items: Draft[] = [], errors: string[] = [];
  list.forEach((x, i) => {
    const o = x as Record<string, unknown>;
    const q = typeof o?.question === "string" ? o.question.trim() : "", a = typeof o?.answer === "string" ? o.answer.trim() : "";
    if (!q || !a) errors.push(`Item ${i + 1}: needs a non-empty "question" and "answer" (strings)`);
    else if (q.length > 500) errors.push(`Item ${i + 1}: question is longer than 500 characters`);
    else if (a.length > 8000) errors.push(`Item ${i + 1}: answer is longer than 8000 characters`);
    else items.push({ question: q, answer: a });
  });
  if (list.length > 2000) errors.push("At most 2000 FAQs can be imported at once");
  return { items, errors };
}

export default function FaqManager({ profile, sync, canEdit, onChanged }: {
  profile: Profile; sync: SyncStatus | null; canEdit: boolean; onChanged?: () => void;
}) {
  const toast = useToast();
  const pid = profile.id;
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("all");
  const [filter, setFilter] = useState<Filter>("all");
  const [editing, setEditing] = useState<Faq | "new" | null>(null);
  const [importing, setImporting] = useState(false);
  const running = sync?.state === "running";

  const refresh = useCallback(async () => {
    try { setFaqs((await api<{ faqs: Faq[] }>(profileUrl(pid, "/faqs"))).faqs); }
    catch (e) { toast("bad", (e as Error).message); }
    finally { setLoading(false); }
  }, [pid, toast]);

  useEffect(() => { setLoading(true); setQ(""); setCategory("all"); setFilter("all"); refresh(); }, [pid]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { // follow the indexer: poll while it runs, refresh when it finishes
    if (!running) { refresh(); return; }
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [running, refresh]);

  const changed = async () => { await refresh(); onChanged?.(); };
  const fail = (e: unknown) => toast("bad", e instanceof ApiError ? e.message : (e as Error).message);

  async function toggle(f: Faq) {
    setFaqs((l) => l.map((x) => (x.id === f.id ? { ...x, enabled: !f.enabled, status: "PENDING" } : x))); // optimistic
    try { await api(profileUrl(pid, `/faqs/${f.id}`), "PATCH", { enabled: !f.enabled }); await changed(); } catch (e) { fail(e); refresh(); }
  }
  async function remove(f: Faq) {
    if (!confirm(`Delete this FAQ?\n\n${f.question}`)) return;
    try { await api(profileUrl(pid, `/faqs/${f.id}`), "DELETE"); toast("ok", "FAQ deleted"); await changed(); } catch (e) { fail(e); }
  }
  async function setUseFaqs(on: boolean) {
    try { await api(profileUrl(pid), "PATCH", { use_faqs: on }); toast("info", on ? "FAQs will be used in answers" : "FAQs are ignored for this profile"); await changed(); } catch (e) { fail(e); }
  }
  async function exportJson() {
    try {
      const token = getToken();
      const res = await fetch(`/api/profiles/${encodeURIComponent(pid)}/faqs/export`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await res.blob());
      a.download = `${pid}-faqs.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } catch (e) { fail(e); }
  }

  const categories = useMemo(() => [...new Set(faqs.map((f) => f.category).filter(Boolean))].sort(), [faqs]);
  const counts = useMemo(() => ({
    all: faqs.length, enabled: faqs.filter((f) => f.enabled).length, disabled: faqs.filter((f) => !f.enabled).length,
    pending: faqs.filter((f) => f.enabled && f.status === "PENDING").length, failed: faqs.filter((f) => f.status === "FAILED").length,
  }), [faqs]);
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return faqs.filter((f) =>
      (category === "all" || f.category === category) &&
      (filter === "all" || (filter === "enabled" ? f.enabled : filter === "disabled" ? !f.enabled : filter === "pending" ? f.enabled && f.status === "PENDING" : f.status === "FAILED")) &&
      (!needle || f.question.toLowerCase().includes(needle) || f.answer.toLowerCase().includes(needle)));
  }, [faqs, q, category, filter]);

  return (
    <div className="page">
      <PageHeader title={`${profile.name} · FAQs`}
        subtitle={<>Curated question &amp; answer pairs, stored in SQLite and searched by chat together with documents.{profile.is_common ? " These are shared with every profile." : ""}</>}
        actions={<>
          {canEdit && <button onClick={() => setEditing("new")}><Icon name="plus" size={15} />Add FAQ</button>}
          {canEdit && <button className="secondary" onClick={() => setImporting(true)}><Icon name="upload" size={15} />Import JSON</button>}
          <button className="secondary" onClick={exportJson} disabled={!faqs.length}><Icon name="download" size={15} />Export JSON</button>
        </>} />

      <div className="tiles compact">
        <div className="tile"><div className="tile-icon"><Icon name="help" size={18} /></div><div><div className="tile-value">{faqs.length}</div><div className="tile-label">FAQs</div></div></div>
        <div className="tile"><div className="tile-icon"><Icon name="check" size={18} /></div><div><div className="tile-value">{counts.enabled}</div><div className="tile-label">Enabled</div></div></div>
        <div className="tile"><div className="tile-icon"><Icon name="zap" size={18} /></div><div><div className="tile-value">{faqs.filter((f) => f.status === "INDEXED").length}</div><div className="tile-label">Searchable</div></div></div>
      </div>

      <Card title="Configuration" icon="sliders">
        <label className="check-row">
          <input type="checkbox" checked={profile.use_faqs} disabled={!canEdit} onChange={(e) => setUseFaqs(e.target.checked)} />
          <span><b>Use FAQs when answering</b><span className="muted small"> — when off, this profile&apos;s FAQs are removed from search (they stay saved). Individual FAQs can also be switched off below.</span></span>
        </label>
        <div className="muted small">JSON format: <code>{'[{"question": "…", "answer": "…"}]'}</code> · <code>category</code> and <code>enabled</code> are optional on import.</div>
      </Card>

      {running && (
        <div className="faq-indexing-banner">
          <div className="faq-indexing-main">
            <div className="faq-indexing-icon">
              <Spinner size={18} />
            </div>
            <div className="faq-indexing-content">
              <div className="faq-indexing-headline">
                <span className="faq-indexing-status-dot" />
                <strong>Indexing FAQs</strong>
                <span className="faq-indexing-badge">Active</span>
              </div>
              <div className="faq-indexing-sub">
                {sync?.message || "Updating vector embeddings and knowledge index…"}
                {sync?.queued?.length ? ` · ${sync.queued.length} queued` : ""}
              </div>
            </div>
          </div>
          <div className="faq-indexing-track">
            <div className="faq-indexing-glow" />
          </div>
        </div>
      )}
      {sync?.state === "error" && (
        <div className="banner bad">
          <Icon name="alert" size={16} />
          <span><strong>Indexing failed:</strong> {sync.error}</span>
        </div>
      )}

      <Card className="table-card">
        <div className="toolbar">
          <div className="search"><Icon name="search" size={15} /><input placeholder="Search questions and answers…" value={q} onChange={(e) => setQ(e.target.value)} />{q && <button className="icon-btn" onClick={() => setQ("")}><Icon name="x" size={13} /></button>}</div>
          <div className="chips">
            {(["all", "enabled", "disabled", "pending", "failed"] as Filter[]).filter((s) => s === "all" || counts[s] > 0).map((s) => (
              <button key={s} className={`chip ${filter === s ? "on" : ""}`} onClick={() => setFilter(s)}>{s}<span className="chip-count">{counts[s]}</span></button>
            ))}
          </div>
          {categories.length > 0 && <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category"><option value="all">All categories</option>{categories.map((c) => <option key={c}>{c}</option>)}</select>}
        </div>

        {loading ? (
          <div className="empty-table">
            <div className="empty-table-loading">
              <Spinner size={22} />
              <span>Loading FAQs…</span>
            </div>
          </div>
        ) : rows.length === 0 ? (
          <div className="empty-table"><Icon name="help" size={28} /><b>{faqs.length ? "No FAQs match" : `No FAQs for ${profile.name} yet`}</b>
            <span className="muted small">{faqs.length ? "Try a different search or filter." : "Add one, or import a JSON file."}</span></div>
        ) : (
          <div className="faq-list">
            {rows.map((f) => (
              <div key={f.id} className={`faq-item ${f.enabled ? "" : "off"}`}>
                <div className="faq-main">
                  <div className="faq-q">{f.question}</div>
                  <div className="faq-a">{f.answer}</div>
                  <div className="row wrap faq-meta">
                    {f.category && <Badge tone="info">{f.category}</Badge>}
                    <Badge tone={TONE[f.status] ?? "muted"}>{f.status.toLowerCase()}</Badge>
                    {f.error_message && <span className="error small" title={f.error_message}>{f.error_message.slice(0, 80)}</span>}
                  </div>
                </div>
                <div className="faq-actions">
                  <label className="switch" title={f.enabled ? "Enabled — click to disable" : "Disabled — click to enable"}>
                    <input type="checkbox" checked={f.enabled} disabled={!canEdit} onChange={() => toggle(f)} /><span />
                  </label>
                  {canEdit && <button className="icon-btn" title="Edit" onClick={() => setEditing(f)}><Icon name="edit" size={15} /></button>}
                  {canEdit && <button className="icon-btn danger" title="Delete" onClick={() => remove(f)}><Icon name="trash" size={15} /></button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {editing && <FaqDialog profileId={pid} faq={editing === "new" ? null : editing} categories={categories} onClose={() => setEditing(null)}
        onSaved={async () => { setEditing(null); await changed(); }} />}
      {importing && <ImportDialog profile={profile} onClose={() => setImporting(false)} onDone={async () => { setImporting(false); await changed(); }} />}
    </div>
  );
}

function FaqDialog({ profileId, faq, categories, onClose, onSaved }: {
  profileId: string; faq: Faq | null; categories: string[]; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [question, setQuestion] = useState(faq?.question ?? "");
  const [answer, setAnswer] = useState(faq?.answer ?? "");
  const [category, setCategory] = useState(faq?.category ?? "");
  const [enabled, setEnabled] = useState(faq?.enabled ?? true);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const body = { question, answer, category, enabled };
      if (faq) await api(profileUrl(profileId, `/faqs/${faq.id}`), "PATCH", body);
      else await api(profileUrl(profileId, "/faqs"), "POST", body);
      toast("ok", faq ? "FAQ updated — re-indexing" : "FAQ added — indexing");
      onSaved();
    } catch (e) { toast("bad", e instanceof ApiError ? e.message : (e as Error).message); }
    finally { setSaving(false); }
  }

  return (
    <>
      <div className="scrim light" onClick={onClose} />
      <div className="modal card" role="dialog" aria-label={faq ? "Edit FAQ" : "Add FAQ"}>
        <div className="card-head"><h3>{faq ? "Edit FAQ" : "Add FAQ"}</h3><button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button></div>
        <div className="form">
          <label>Question<input value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)} placeholder="What is your refund policy?" autoFocus /></label>
          <label>Answer<textarea rows={6} value={answer} maxLength={8000} onChange={(e) => setAnswer(e.target.value)} placeholder="The answer the assistant should give…" /></label>
          <label>Category <span className="muted small">(optional)</span>
            <input value={category} maxLength={60} list="faq-categories" onChange={(e) => setCategory(e.target.value)} placeholder="e.g. billing" />
            <datalist id="faq-categories">{categories.map((c) => <option key={c} value={c} />)}</datalist>
          </label>
          <label className="check"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />Enabled (searchable by chat)</label>
        </div>
        <div className="row modal-actions">
          <button onClick={save} disabled={saving || !question.trim() || !answer.trim()}>{saving ? <Spinner size={14} /> : faq ? "Save" : "Add"}</button>
          <button className="secondary" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </>
  );
}

function ImportDialog({ profile, onClose, onDone }: { profile: Profile; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"append" | "replace">("append");
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const parsed = useMemo(() => (text.trim() ? parseFaqJson(text) : null), [text]);

  async function submit() {
    if (!parsed || !parsed.items.length) return;
    if (mode === "replace" && !confirm(`Replace ALL existing FAQs of ${profile.name} with these ${parsed.items.length}?`)) return;
    setBusy(true);
    try {
      const r = await api<{ added: number; skipped_duplicates: number }>(profileUrl(profile.id, `/faqs/import?mode=${mode}`), "POST", { faqs: parsed.items });
      toast("ok", `${r.added} FAQ${r.added === 1 ? "" : "s"} imported${r.skipped_duplicates ? `, ${r.skipped_duplicates} duplicate${r.skipped_duplicates === 1 ? "" : "s"} skipped` : ""}`);
      onDone();
    } catch (e) { toast("bad", e instanceof ApiError ? e.message : (e as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <>
      <div className="scrim light" onClick={onClose} />
      <div className="modal card" role="dialog" aria-label="Import FAQs">
        <div className="card-head"><h3>Import FAQs into {profile.name}</h3><button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button></div>
        <div className="form">
          <div className="row wrap">
            <button className="secondary sm" onClick={() => file.current?.click()}><Icon name="upload" size={14} />Choose .json file</button>
            <input ref={file} type="file" accept="application/json,.json" hidden onChange={async (e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) setText(await f.text()); }} />
            <span className="muted small">or paste JSON below</span>
          </div>
          <textarea rows={9} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} className="mono"
            placeholder={'[\n  { "question": "What are your opening hours?", "answer": "9 to 5, Monday to Friday." }\n]'} />
          {parsed && (
            <div className="stack" style={{ gap: 6 }}>
              {parsed.items.length > 0 && <div className="note"><Icon name="check" size={14} />{parsed.items.length} valid FAQ{parsed.items.length === 1 ? "" : "s"} found</div>}
              {parsed.errors.slice(0, 5).map((m, i) => <div key={i} className="note bad"><Icon name="alert" size={14} />{m}</div>)}
              {parsed.errors.length > 5 && <div className="muted small">…and {parsed.errors.length - 5} more problems</div>}
            </div>
          )}
          <div className="stack" style={{ gap: 6 }}>
            <label className="check"><input type="radio" name="mode" checked={mode === "append"} onChange={() => setMode("append")} />Add to existing FAQs (questions that already exist are skipped)</label>
            <label className="check"><input type="radio" name="mode" checked={mode === "replace"} onChange={() => setMode("replace")} />Replace all existing FAQs of this profile</label>
          </div>
        </div>
        <div className="row modal-actions">
          <button onClick={submit} disabled={busy || !parsed?.items.length}>{busy ? <Spinner size={14} /> : `Import${parsed?.items.length ? ` ${parsed.items.length}` : ""}`}</button>
          <button className="secondary" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </>
  );
}
