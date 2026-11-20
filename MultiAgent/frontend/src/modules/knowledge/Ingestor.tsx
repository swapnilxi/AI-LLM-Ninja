/** Ingest knowledge for an owner (org / project / agent): multi-file drag-and-drop upload, pasted text, or a web page. */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, FileText, FileUp, Link2, Loader2, RotateCcw, Type, UploadCloud, X } from "lucide-react";
import { http } from "@/shared/lib/api";
import { bytes, cn, errMsg } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { Button, Card, Checkbox, Field, Input, Tabs, Textarea } from "@/shared/ui/primitives";
import type { Doc } from "./types";
import { ACCEPT_EXTS, fileProblem, MAX_UPLOAD_MB, uploadDocument } from "./upload";

type Mode = "upload" | "text" | "url";
type Status = "queued" | "uploading" | "processing" | "done" | "error";
interface Item {
  id: string;
  file: File;
  pinned: boolean;
  status: Status;
  progress: number;
  error?: string;
  doc?: Doc;
}

const CONCURRENCY = 3;
let seq = 0;

export function Ingestor({ ownerType, ownerId, onIngested, docLink, className }: {
  ownerType: "org" | "project" | "agent";
  ownerId: string;
  onIngested?: (doc: Doc) => void;
  /** Build a link to an ingested document (shown next to finished uploads). */
  docLink?: (doc: Doc) => string;
  className?: string;
}) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<Mode>("upload");
  const [pinned, setPinned] = useState(false);
  const refresh = useCallback(
    (doc: Doc) => {
      qc.invalidateQueries({ queryKey: ["documents", ownerType, ownerId] });
      qc.invalidateQueries({ queryKey: ["training"] });
      onIngested?.(doc);
    },
    [qc, ownerType, ownerId, onIngested],
  );

  return (
    <Card className={cn("overflow-hidden", className)}>
      <div className="flex flex-col gap-3 border-b border-border bg-gradient-to-r from-primary-soft/60 via-transparent to-transparent px-4 pt-3 sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold">Add knowledge</h3>
            <p className="mt-0.5 text-xs text-muted">Documents are split into chunks and searched with knowledge_search. Pinned documents go into every prompt.</p>
          </div>
          <Checkbox checked={pinned} onChange={setPinned} label={<span className="text-xs">Pin to every prompt</span>} />
        </div>
        <Tabs
          className="mb-0 border-b-0"
          tabs={[
            { key: "upload", label: <><FileUp className="size-3.5" /> Upload files</> },
            { key: "text", label: <><Type className="size-3.5" /> Paste text</> },
            { key: "url", label: <><Link2 className="size-3.5" /> From URL</> },
          ]}
          value={mode}
          onChange={setMode}
        />
      </div>
      <div className="p-3 sm:p-4">
        {mode === "upload" && <UploadQueue ownerType={ownerType} ownerId={ownerId} pinned={pinned} onDone={refresh} docLink={docLink} />}
        {mode === "text" && <PasteText ownerType={ownerType} ownerId={ownerId} pinned={pinned} onDone={refresh} />}
        {mode === "url" && <FromUrl ownerType={ownerType} ownerId={ownerId} pinned={pinned} onDone={refresh} />}
      </div>
    </Card>
  );
}

function UploadQueue({ ownerType, ownerId, pinned, onDone, docLink }: { ownerType: string; ownerId: string; pinned: boolean; onDone: (d: Doc) => void; docLink?: (doc: Doc) => string }) {
  const [items, setItems] = useState<Item[]>([]);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const started = useRef(new Set<string>());
  const patch = (id: string, p: Partial<Item>) => setItems((xs) => xs.map((x) => (x.id === id ? { ...x, ...p } : x)));

  const add = (files: FileList | File[] | null) => {
    if (!files) return;
    const next = Array.from(files).map<Item>((file) => {
      const problem = fileProblem(file);
      return { id: `f${++seq}`, file, pinned, status: problem ? "error" : "queued", progress: 0, error: problem ?? undefined };
    });
    setItems((xs) => [...next, ...xs]);
  };

  const start = (it: Item) => {
    started.current.add(it.id);
    patch(it.id, { status: "uploading", progress: 0, error: undefined });
    uploadDocument(it.file, {
      ownerType,
      ownerId,
      pinned: it.pinned,
      onProgress: (f) => patch(it.id, f >= 1 ? { progress: 1, status: "processing" } : { progress: f }),
    })
      .then((doc) => {
        patch(it.id, { status: "done", progress: 1, doc });
        onDone(doc);
      })
      .catch((e) => patch(it.id, { status: "error", error: errMsg(e) }));
  };

  useEffect(() => {
    const active = items.filter((i) => i.status === "uploading" || i.status === "processing").length;
    items
      .filter((i) => i.status === "queued" && !started.current.has(i.id))
      .slice(0, Math.max(0, CONCURRENCY - active))
      .forEach(start);
  }, [items]);

  const retry = (it: Item) => {
    started.current.delete(it.id);
    if (!fileProblem(it.file)) patch(it.id, { status: "queued", progress: 0, error: undefined });
  };
  const done = items.filter((i) => i.status === "done").length;
  const failed = items.filter((i) => i.status === "error").length;
  const busy = items.some((i) => i.status === "queued" || i.status === "uploading" || i.status === "processing");

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && fileRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          add(e.dataTransfer.files);
        }}
        onClick={() => fileRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-9 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
          drag ? "border-primary bg-primary-soft/60" : "border-border bg-gradient-to-b from-surface-2/60 to-transparent hover:border-primary/40",
        )}
      >
        <div className="mb-3 flex size-11 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/15 to-violet-500/10 text-primary ring-1 ring-inset ring-indigo-500/15">
          <UploadCloud className="size-5" />
        </div>
        <div className="text-sm font-medium">Drop files here or click to browse</div>
        <div className="mt-1 text-xs text-muted">PDF, DOCX, Markdown, TXT, CSV, JSON, HTML and more · up to {MAX_UPLOAD_MB} MB each · several at once</div>
        <input
          ref={fileRef}
          type="file"
          hidden
          multiple
          accept={ACCEPT_EXTS.join(",")}
          onChange={(e) => {
            add(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {items.length > 0 && (
        <div className="rounded-xl border border-border">
          <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2 text-xs text-muted">
            <span>
              {done} of {items.length} added{failed ? ` · ${failed} failed` : ""}
              {busy && " · working…"}
            </span>
            {!busy && (
              <button className="cursor-pointer font-medium hover:text-fg" onClick={() => setItems([])}>
                Clear
              </button>
            )}
          </div>
          <ul className="max-h-80 divide-y divide-border overflow-y-auto">
            {items.map((it) => (
              <li key={it.id} className="flex items-center gap-3 px-3 py-2.5">
                <StatusIcon status={it.status} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{it.file.name}</span>
                    <span className="shrink-0 text-[11px] tabular-nums text-muted">{bytes(it.file.size)}</span>
                  </div>
                  {it.status === "uploading" || it.status === "processing" || it.status === "queued" ? (
                    <div className="mt-1.5 flex items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                        <div
                          className={cn("h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-[width] duration-200", it.status === "processing" && "animate-pulse")}
                          style={{ width: `${Math.round(it.progress * 100)}%` }}
                        />
                      </div>
                      <span className="w-20 shrink-0 text-right text-[11px] text-muted">
                        {it.status === "queued" ? "Queued" : it.status === "processing" ? "Indexing…" : `${Math.round(it.progress * 100)}%`}
                      </span>
                    </div>
                  ) : it.status === "done" && it.doc ? (
                    <div className="mt-0.5 text-xs text-muted">
                      Added · {it.doc.chunk_count} chunk{it.doc.chunk_count === 1 ? "" : "s"}
                      {it.doc.pinned && " · pinned"}
                      {docLink && (
                        <>
                          {" · "}
                          <Link to={docLink(it.doc)} className="font-medium text-primary hover:underline">Open</Link>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="mt-0.5 text-xs text-danger">{it.error}</div>
                  )}
                </div>
                {it.status === "error" && !fileProblem(it.file) && (
                  <Button size="icon" variant="ghost" className="size-8" aria-label="Retry" title="Retry" onClick={() => retry(it)}>
                    <RotateCcw className="size-4 text-muted" />
                  </Button>
                )}
                {(it.status === "error" || it.status === "done") && (
                  <Button size="icon" variant="ghost" className="size-8" aria-label="Remove from list" title="Remove from list" onClick={() => setItems((xs) => xs.filter((x) => x.id !== it.id))}>
                    <X className="size-4 text-muted" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: Status }) {
  if (status === "done") return <CheckCircle2 className="size-5 shrink-0 text-success" />;
  if (status === "error") return <AlertCircle className="size-5 shrink-0 text-danger" />;
  if (status === "uploading" || status === "processing") return <Loader2 className="size-5 shrink-0 animate-spin text-primary" />;
  return <FileText className="size-5 shrink-0 text-muted" />;
}

function PasteText({ ownerType, ownerId, pinned, onDone }: { ownerType: string; ownerId: string; pinned: boolean; onDone: (d: Doc) => void }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const save = useAction(() => http.post<Doc>("/documents", { owner_type: ownerType, owner_id: ownerId, title: title.trim(), content, pinned }), {
    success: "Text added",
    onSuccess: (d) => {
      setTitle("");
      setContent("");
      onDone(d);
    },
  });
  return (
    <div className="space-y-3">
      <Field label="Title">
        <Input value={title} maxLength={255} onChange={(e) => setTitle(e.target.value)} placeholder="Refund policy" />
      </Field>
      <Field label="Content" hint={content ? `${content.length.toLocaleString()} characters` : "Paste text or markdown: policies, FAQs, product notes, transcripts…"}>
        <Textarea rows={10} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Paste text or markdown…" />
      </Field>
      <div className="flex justify-end">
        <Button icon={<Type className="size-4" />} disabled={!title.trim() || !content.trim()} loading={save.isPending} onClick={() => save.mutate()}>Add text</Button>
      </div>
    </div>
  );
}

function FromUrl({ ownerType, ownerId, pinned, onDone }: { ownerType: string; ownerId: string; pinned: boolean; onDone: (d: Doc) => void }) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const valid = /^https?:\/\/\S+\.\S+/i.test(url.trim());
  const save = useAction(() => http.post<Doc>("/documents/from-url", { owner_type: ownerType, owner_id: ownerId, url: url.trim(), title: title.trim() || undefined, pinned }), {
    success: "Page imported",
    onSuccess: (d) => {
      setUrl("");
      setTitle("");
      onDone(d);
    },
  });
  return (
    <div className="space-y-3">
      <Field label="Page URL" hint="Fetched through the SSRF-safe browser and converted to text. PDFs are supported too.">
        <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/handbook" onKeyDown={(e) => e.key === "Enter" && valid && save.mutate()} />
      </Field>
      <Field label="Title (optional)">
        <Input value={title} maxLength={255} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to the page title" />
      </Field>
      <div className="flex justify-end">
        <Button icon={<Link2 className="size-4" />} disabled={!valid} loading={save.isPending} onClick={() => save.mutate()}>Import page</Button>
      </div>
    </div>
  );
}
