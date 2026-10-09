"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, Category, DOC_PENDING, DocRow, DocStatus, Profile, profileUrl, SyncStatus, upload } from "@/lib/api";
import { acceptAttr, DocInfo, DocRef, downloadDocument, fetchDocInfo, formatSize, kindOf, openDocument, validateFiles } from "@/utils/files";
import { Icon, fileIcon } from "./Icons";
import { Badge, Card, PageHeader, Spinner, useToast } from "./ui";

const TONE: Record<DocStatus, "ok" | "warn" | "bad" | "info" | "muted"> = {
  INDEXED: "ok", PENDING: "warn", DISCOVERED: "warn", STALE: "warn", INDEXING: "info", FAILED: "bad", DELETED: "muted",
};
const STATES: (DocStatus | "all")[] = ["all", "INDEXED", "PENDING", "STALE", "FAILED"];
type Sort = "name" | "size" | "modified" | "status";
type Listing = { documents: DocRow[]; folders: string[]; supported_extensions: string[]; categories: Category[] };

const parentOf = (p: string) => p.split("/").slice(0, -1).join("/");
const leaf = (p: string) => p.split("/").pop() ?? p;

export default function Documents({ profile, sync, canEdit, onChanged }: {
  profile: Profile; sync: SyncStatus | null; canEdit: boolean; onChanged?: () => void;
}) {
  const toast = useToast();
  const pid = profile.id;
  const [data, setData] = useState<Listing>({ documents: [], folders: [], supported_extensions: [], categories: [] });
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [notes, setNotes] = useState<{ bad: boolean; text: string }[]>([]);
  const [cwd, setCwd] = useState(""); // current folder ("" = profile root)
  const [q, setQ] = useState("");
  const [state, setState] = useState<DocStatus | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sort, setSort] = useState<Sort>("name");
  const [selected, setSelected] = useState<DocRow | null>(null);
  const [info, setInfo] = useState<DocInfo | "loading" | null>(null);
  const [managingCategories, setManagingCategories] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const running = sync?.state === "running";
  const exts = data.supported_extensions;
  const ref = (d: DocRow): DocRef => ({ profileId: pid, documentId: d.id, name: d.filename });

  const refresh = useCallback(async () => {
    try {
      setData(await api<Listing>(profileUrl(pid, "/documents")));
    } catch (e) {
      toast("bad", (e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [pid, toast]);

  // switching profile: start clean
  useEffect(() => { setLoading(true); setCwd(""); setSelected(null); setQ(""); setState("all"); setCategoryFilter("all"); setNotes([]); refresh(); }, [pid]); // eslint-disable-line react-hooks/exhaustive-deps
  // the shell polls sync status; re-read the listing while a job runs and once when it finishes
  useEffect(() => {
    if (!running) { refresh(); return; }
    const t = setInterval(refresh, 1500);
    return () => clearInterval(t);
  }, [running, refresh]);

  useEffect(() => {
    if (!selected) { setInfo(null); return; }
    setInfo("loading");
    fetchDocInfo(ref(selected)).then(setInfo).catch((e) => setInfo({ name: selected.filename, type: "?", mime: "", size: 0, error: e.message }));
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const changed = async () => { await refresh(); onChanged?.(); };
  const fail = (e: unknown) => toast("bad", e instanceof ApiError ? e.message : (e as Error).message);
  const catById = useMemo(() => Object.fromEntries(data.categories.map((c) => [c.id, c])), [data.categories]);
  const current = selected ? data.documents.find((d) => d.id === selected.id) ?? selected : null;

  async function toggleCategory(doc: DocRow, categoryId: string) {
    const next = doc.category_ids.includes(categoryId) ? doc.category_ids.filter((id) => id !== categoryId) : [...doc.category_ids, categoryId];
    setData((d) => ({ ...d, documents: d.documents.map((x) => (x.id === doc.id ? { ...x, category_ids: next } : x)) })); // optimistic
    try { await api(profileUrl(pid, `/documents/${doc.id}/categories`), "PATCH", { category_ids: next }); } catch (e) { fail(e); refresh(); }
  }

  async function doUpload(list: File[]) {
    setUploading(true);
    try {
      const { accepted, rejected, warnings } = await validateFiles(list, { allowedExts: exts });
      setNotes([...rejected.map((r) => ({ bad: true, text: `${r.name}: ${r.reason}` })), ...warnings.map((w) => ({ bad: false, text: `${w.name}: ${w.reason}` }))]);
      if (accepted.length) {
        await upload(pid, accepted, cwd);
        toast("ok", `${accepted.length} file${accepted.length > 1 ? "s" : ""} uploaded to ${profile.name}${cwd ? `/${cwd}` : ""} — indexing started`);
      }
      await changed();
    } catch (e) { fail(e); } finally { setUploading(false); }
  }

  async function newFolder() {
    const name = prompt(`New folder inside ${cwd || profile.name}:`)?.trim();
    if (!name) return;
    try {
      await api(profileUrl(pid, "/folders"), "POST", { path: cwd ? `${cwd}/${name}` : name });
      await changed();
    } catch (e) { fail(e); }
  }

  async function removeFolder(path: string) {
    const url = profileUrl(pid, `/folders/${path.split("/").map(encodeURIComponent).join("/")}`);
    try {
      await api(url, "DELETE");
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 409)) return fail(e);
      const n = data.documents.filter((d) => d.relative_path.startsWith(path + "/")).length;
      if (!confirm(`"${path}" is not empty${n ? ` (${n} document${n > 1 ? "s" : ""})` : ""}.\n\nPermanently delete the folder and everything in it? This cannot be undone.`)) return;
      try { await api(url + "?recursive=true&confirm=true", "DELETE"); } catch (e2) { return fail(e2); }
    }
    toast("ok", `Folder ${path} deleted`);
    await changed();
  }

  async function removeDoc(d: DocRow) {
    if (!confirm(`Delete ${d.relative_path}? The file is permanently removed from disk and from the index.`)) return;
    try {
      await api(profileUrl(pid, `/documents/${d.id}`), "DELETE");
      if (selected?.id === d.id) setSelected(null);
      toast("ok", `${d.filename} deleted`);
      await changed();
    } catch (e) { fail(e); }
  }

  async function run(path: string, okMsg: string, confirmMsg?: string) {
    if (confirmMsg && !confirm(confirmMsg)) return;
    try { await api(path, "POST"); toast("info", okMsg); await changed(); } catch (e) { fail(e); }
  }

  const counts = useMemo(() => Object.fromEntries(STATES.map((s) => [s, s === "all" ? data.documents.length : data.documents.filter((f) => f.status === s || (s === "PENDING" && f.status === "DISCOVERED")).length])), [data.documents]);
  const flat = !!q.trim() || state !== "all" || categoryFilter !== "all";

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let list = data.documents.filter((f) =>
      (state === "all" || f.status === state || (state === "PENDING" && f.status === "DISCOVERED")) &&
      (categoryFilter === "all" || f.category_ids.includes(categoryFilter)) &&
      (!needle || f.relative_path.toLowerCase().includes(needle)));
    if (!flat) list = list.filter((f) => f.folder === cwd);
    const key = { name: (f: DocRow) => f.filename.toLowerCase(), size: (f: DocRow) => -f.size, modified: (f: DocRow) => -(f.modified ?? 0), status: (f: DocRow) => f.status }[sort];
    return list.sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0));
  }, [data.documents, q, state, categoryFilter, sort, cwd, flat]);

  const subfolders = useMemo(() => (flat ? [] : data.folders.filter((f) => parentOf(f) === cwd)), [data.folders, cwd, flat]);
  const docsIn = (folder: string) => data.documents.filter((d) => d.relative_path.startsWith(folder + "/")).length;
  const crumbs = cwd ? cwd.split("/") : [];

  return (
    <div className="page">
      <PageHeader title={`${profile.name} · Documents`} subtitle={<>Folder: <code>{profile.folder}</code>{profile.include_common && !profile.is_common && <> · also searches <b>Common</b></>}</>}
        actions={<>
          <button onClick={() => run(profileUrl(pid, "/sync"), "Sync started")} disabled={running}>{running ? <><Spinner size={14} />Indexing…</> : <><Icon name="refresh" size={15} />Sync now</>}</button>
          <button className="secondary" onClick={() => run(profileUrl(pid, "/documents/reindex"), "Re-indexing all documents…", `Re-embed every document in ${profile.name}?`)} disabled={running}
            title="Drop this profile's index and re-embed all its documents">Re-index</button>
        </>} />

      <div className="tiles compact">
        <div className="tile"><div className="tile-icon"><Icon name="doc" size={18} /></div><div><div className="tile-value">{profile.stats.documents}</div><div className="tile-label">Documents</div></div></div>
        <div className="tile"><div className="tile-icon"><Icon name="check" size={18} /></div><div><div className="tile-value">{profile.stats.indexed}</div><div className="tile-label">Indexed</div></div></div>
        <div className="tile"><div className="tile-icon"><Icon name="database" size={18} /></div><div><div className="tile-value">{formatSize(profile.stats.bytes)}</div><div className="tile-label">Total size</div></div></div>
        <div className="tile"><div className="tile-icon"><Icon name="zap" size={18} /></div><div><div className="tile-value">{profile.stats.pending}</div><div className="tile-label">Waiting to index</div></div></div>
      </div>

      {sync && sync.state !== "idle" && (
        <div className={`banner ${sync.state === "error" ? "bad" : running ? "info" : "ok"}`}>
          {running ? <Spinner /> : <Icon name={sync.state === "error" ? "alert" : "check"} size={16} />}
          <span>
            {running && <><strong>Indexing{sync.profile ? ` ${sync.profile}` : ""}…</strong> {sync.message}{sync.queued?.length ? ` · ${sync.queued.length} queued` : ""}</>}
            {sync.state === "error" && <><strong>Sync failed:</strong> {sync.error}</>}
            {sync.state === "done" && sync.result && <><strong>Sync complete.</strong> +{sync.result.added.length} added · {sync.result.updated.length} updated · {sync.result.removed.length} removed · {sync.result.unchanged} unchanged · {sync.result.seconds}s</>}
            {sync.result && Object.entries(sync.result.errors).map(([f, m]) => <div key={f} className="error small">{f}: {m}</div>)}
          </span>
        </div>
      )}
      {running && <div className="indeterminate"><div /></div>}

      {canEdit && (
        <div className={`drop ${dragging ? "over" : ""} ${uploading ? "busy" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); doUpload(Array.from(e.dataTransfer.files)); }}
          onClick={() => !uploading && input.current?.click()}>
          {uploading ? <><Spinner /><span>Uploading and validating…</span></> : (
            <><Icon name="upload" size={22} /><div><b>Drop files here</b> or click to upload to <b>{profile.name}{cwd ? ` / ${cwd}` : ""}</b><div className="muted small">{exts.join("  ")} · max 25 MB each · files are checked before upload</div></div></>
          )}
          <input ref={input} type="file" multiple hidden accept={acceptAttr(exts)} onChange={(e) => { const picked = Array.from(e.target.files ?? []); e.target.value = ""; if (picked.length) doUpload(picked); }} />
        </div>
      )}
      {notes.map((n, i) => <div key={i} className={`note ${n.bad ? "bad" : "warn"}`}><Icon name={n.bad ? "x" : "alert"} size={14} />{n.text}</div>)}

      <Card className="table-card">
        <div className="toolbar">
          <div className="search"><Icon name="search" size={15} /><input placeholder={`Search ${profile.name}…`} value={q} onChange={(e) => setQ(e.target.value)} />{q && <button className="icon-btn" onClick={() => setQ("")}><Icon name="x" size={13} /></button>}</div>
          <div className="chips">
            {STATES.filter((s) => s === "all" || counts[s] > 0).map((s) => (
              <button key={s} className={`chip ${state === s ? "on" : ""}`} onClick={() => setState(s)}>{s === "all" ? "all" : s.toLowerCase()}<span className="chip-count">{counts[s]}</span></button>
            ))}
          </div>
          {data.categories.length > 0 && (
            <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} aria-label="Category">
              <option value="all">All categories</option>
              {data.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort by"><option value="name">Sort: name</option><option value="size">Sort: size</option><option value="modified">Sort: recent</option><option value="status">Sort: status</option></select>
          {canEdit && <button className="secondary sm" onClick={newFolder}><Icon name="plus" size={14} />New folder</button>}
          {canEdit && <button className="secondary sm" onClick={() => setManagingCategories(true)}><Icon name="tag" size={14} />Categories</button>}
        </div>

        {!flat && (
          <div className="crumbs">
            <button className="link" onClick={() => setCwd("")}>{profile.name}</button>
            {crumbs.map((c, i) => <span key={i}> / <button className="link" onClick={() => setCwd(crumbs.slice(0, i + 1).join("/"))}>{c}</button></span>)}
          </div>
        )}

        {loading ? <div className="empty-table"><Spinner /></div> : rows.length === 0 && subfolders.length === 0 ? (
          <div className="empty-table"><Icon name="doc" size={28} /><b>{data.documents.length ? "Nothing here" : "No documents yet"}</b><span className="muted small">{data.documents.length ? "Try a different folder, search or filter." : `Upload files above or copy them into ${profile.folder}, then sync.`}</span></div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Name</th>{flat && <th>Folder</th>}<th>Size</th><th>Status</th><th>Indexed</th><th /></tr></thead>
              <tbody>
                {subfolders.map((f) => (
                  <tr key={f} onClick={() => setCwd(f)} className="folder-row">
                    <td><span className="file-cell"><Icon name="layers" size={16} /><span className="file-name">{leaf(f)}/</span></span></td>
                    <td className="muted" colSpan={flat ? 4 : 3}>{docsIn(f)} document{docsIn(f) === 1 ? "" : "s"}</td>
                    <td className="actions" onClick={(e) => e.stopPropagation()}>
                      {canEdit && <button className="icon-btn danger" title="Delete folder" onClick={() => removeFolder(f)}><Icon name="trash" size={15} /></button>}
                    </td>
                  </tr>
                ))}
                {rows.map((f) => (
                  <tr key={f.id} className={selected?.id === f.id ? "sel" : ""} onClick={() => setSelected(f)}>
                    <td>
                      <span className="file-cell"><Icon name={fileIcon(f.filename)} size={16} /><span className="file-name" title={f.relative_path}>{f.filename}</span></span>
                      {f.category_ids.length > 0 && (
                        <div className="row wrap" style={{ marginTop: 4 }}>
                          {f.category_ids.map((cid) => catById[cid] && <Badge key={cid} tone="info">{catById[cid].name}</Badge>)}
                        </div>
                      )}
                    </td>
                    {flat && <td className="muted">{f.folder || "—"}</td>}
                    <td>{f.size ? formatSize(f.size) : "—"}</td>
                    <td><Badge tone={TONE[f.status] ?? "muted"}>{f.status.toLowerCase()}</Badge>{f.error && <div className="error small" title={f.error}>{f.error.slice(0, 60)}</div>}</td>
                    <td className="muted small">{f.indexed_at ? new Date(f.indexed_at * 1000).toLocaleString() : "—"}{f.chunks ? ` · ${f.chunks} chunks` : ""}</td>
                    <td className="actions" onClick={(e) => e.stopPropagation()}>
                      <button className="icon-btn" title="Open" onClick={() => openDocument(ref(f)).catch((e) => toast("bad", e.message))}><Icon name="external" size={15} /></button>
                      {canEdit && <button className="icon-btn" title="Re-index this document" disabled={running} onClick={() => run(profileUrl(pid, `/documents/${f.id}/index`), `Re-indexing ${f.filename}…`)}><Icon name="refresh" size={15} /></button>}
                      {canEdit && <button className="icon-btn danger" title="Delete" onClick={() => removeDoc(f)}><Icon name="trash" size={15} /></button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {current && (
        <>
          <div className="scrim light" onClick={() => setSelected(null)} />
          <aside className="drawer" aria-label="File details">
            <div className="drawer-head">
              <div className="file-cell"><Icon name={fileIcon(current.filename)} size={18} /><b title={current.relative_path}>{current.relative_path}</b></div>
              <button className="icon-btn" onClick={() => setSelected(null)}><Icon name="x" size={16} /></button>
            </div>
            {info === "loading" || !info ? <div className="empty-table"><Spinner /></div> : (
              <div className="drawer-body">
                {info.error && <div className="note bad"><Icon name="alert" size={14} />{info.error}</div>}
                {current.error && <div className="note bad"><Icon name="alert" size={14} />{current.error}</div>}
                {info.scanned && <div className="note warn"><Icon name="alert" size={14} />This PDF has no text layer (scanned images). Run OCR first, e.g. <code>ocrmypdf in.pdf out.pdf</code>.</div>}
                {info.encrypted && <div className="note warn"><Icon name="alert" size={14} />Encrypted PDF — indexing needs it to be unlocked.</div>}
                <dl className="meta">
                  <dt>Profile</dt><dd>{profile.name}</dd>
                  <dt>Type</dt><dd>{info.type}</dd>
                  <dt>Size</dt><dd>{formatSize(info.size)}</dd>
                  {info.pages !== undefined && <><dt>Pages</dt><dd>{info.pages}</dd></>}
                  {info.title && <><dt>Title</dt><dd>{info.title}</dd></>}
                  {info.author && <><dt>Author</dt><dd>{info.author}</dd></>}
                  {info.created && <><dt>Created</dt><dd>{new Date(info.created).toLocaleDateString()}</dd></>}
                  {info.paragraphs !== undefined && <><dt>Paragraphs</dt><dd>{info.paragraphs}</dd></>}
                  {info.tables !== undefined && <><dt>Tables</dt><dd>{info.tables}</dd></>}
                  <dt>Index</dt><dd><Badge tone={TONE[current.status]}>{current.status.toLowerCase()}</Badge> · {current.chunks} chunks</dd>
                  {current.embedding_model && <><dt>Embedding</dt><dd className="small">{current.embedding_model} · {current.embedding_dimension}d · v{current.embedding_version}</dd></>}
                  {current.chunking_version && <><dt>Chunking</dt><dd className="small">{current.chunking_version}</dd></>}
                </dl>
                <div className="row wrap" style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <b className="small">Categories</b>
                  {canEdit && <button className="icon-btn" title="Manage categories" onClick={() => setManagingCategories(true)}><Icon name="tag" size={14} /></button>}
                </div>
                {data.categories.length === 0 ? (
                  <div className="muted small" style={{ marginBottom: 14 }}>
                    No categories yet for {profile.name}.{canEdit && <> <button className="link" onClick={() => setManagingCategories(true)}>Create one</button></>}
                  </div>
                ) : (
                  <div className="chips" style={{ marginBottom: 14 }}>
                    {data.categories.map((c) => (
                      <button key={c.id} className={`chip ${current.category_ids.includes(c.id) ? "on" : ""}`} disabled={!canEdit}
                        title={canEdit ? (current.category_ids.includes(c.id) ? `Remove ${c.name}` : `Add ${c.name}`) : c.name}
                        onClick={() => toggleCategory(current, c.id)}>{c.name}</button>
                    ))}
                  </div>
                )}
                {DOC_PENDING.includes(current.status) && <div className="muted small">Waiting to be indexed — press Sync now.</div>}
                <div className="row wrap">
                  <button onClick={() => openDocument(ref(current)).catch((e) => toast("bad", e.message))}><Icon name="external" size={15} />Open</button>
                  <button className="secondary" onClick={() => downloadDocument(ref(current)).catch((e) => toast("bad", e.message))}><Icon name="download" size={15} />Download</button>
                  {canEdit && <button className="secondary danger" onClick={() => removeDoc(current)}><Icon name="trash" size={15} />Delete</button>}
                </div>
              </div>
            )}
          </aside>
        </>
      )}
      {managingCategories && (
        <CategoriesDialog profile={profile} categories={data.categories} onClose={() => setManagingCategories(false)} onChanged={refresh} />
      )}
    </div>
  );
}

function CategoriesDialog({ profile, categories, onClose, onChanged }: {
  profile: Profile; categories: Category[]; onClose: () => void; onChanged: () => Promise<void>;
}) {
  const toast = useToast();
  const pid = profile.id;
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const fail = (e: unknown) => toast("bad", e instanceof ApiError ? e.message : (e as Error).message);

  async function add() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      await api(profileUrl(pid, "/categories"), "POST", { name: trimmed });
      setName("");
      await onChanged();
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  async function rename(c: Category) {
    const trimmed = editName.trim();
    setEditingId(null);
    if (!trimmed || trimmed === c.name) return;
    try { await api(profileUrl(pid, `/categories/${c.id}`), "PATCH", { name: trimmed }); await onChanged(); } catch (e) { fail(e); }
  }

  async function remove(c: Category) {
    if (!confirm(`Delete category "${c.name}"? Documents keep their other categories but lose this one.`)) return;
    try { await api(profileUrl(pid, `/categories/${c.id}`), "DELETE"); await onChanged(); } catch (e) { fail(e); }
  }

  return (
    <>
      <div className="scrim light" onClick={onClose} />
      <div className="modal card" role="dialog" aria-label="Manage categories">
        <div className="card-head"><h3>Categories for {profile.name}</h3><button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button></div>
        <div className="form">
          <div className="row wrap">
            <input value={name} maxLength={60} placeholder="New category name" onKeyDown={(e) => e.key === "Enter" && add()} onChange={(e) => setName(e.target.value)} />
            <button className="sm" onClick={add} disabled={busy || !name.trim()}>{busy ? <Spinner size={14} /> : <><Icon name="plus" size={14} />Add</>}</button>
          </div>
          {categories.length === 0 ? (
            <div className="muted small">No categories yet. Add one above, then tag documents with it from the document details panel.</div>
          ) : (
            <div className="stack" style={{ gap: 6 }}>
              {categories.map((c) => (
                <div key={c.id} className="row wrap" style={{ justifyContent: "space-between" }}>
                  {editingId === c.id ? (
                    <input autoFocus value={editName} maxLength={60} onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && rename(c)} onBlur={() => rename(c)} />
                  ) : (
                    <span>{c.name}</span>
                  )}
                  <div className="row">
                    <button className="icon-btn" title="Rename" onClick={() => { setEditingId(c.id); setEditName(c.name); }}><Icon name="edit" size={14} /></button>
                    <button className="icon-btn danger" title="Delete" onClick={() => remove(c)}><Icon name="trash" size={14} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="row modal-actions">
          <button className="secondary" onClick={onClose}>Done</button>
        </div>
      </div>
    </>
  );
}
