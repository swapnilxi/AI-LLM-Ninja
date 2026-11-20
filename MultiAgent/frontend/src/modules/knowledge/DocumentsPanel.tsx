import { useRef, useState } from "react";
import { FileText, FileUp, Link2, Pin, PinOff, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/lib/api";
import type { Doc } from "@/lib/types";
import { bytes, cn, errMsg, timeAgo } from "@/lib/utils";
import { useAction, useDocuments } from "@/hooks/useData";
import { ConfirmDialog, Dialog } from "@/components/ui/overlay";
import { Badge, Button, Card, CardHeader, Checkbox, EmptyState, Field, Input, Spinner, Tabs, Textarea } from "@/components/ui/primitives";

/** Knowledge documents attached to an org, project or agent. */
export function DocumentsPanel({ ownerType, ownerId, readOnly, title = "Knowledge documents", description }: { ownerType: "org" | "project" | "agent"; ownerId: string; readOnly?: boolean; title?: string; description?: string }) {
  const docs = useDocuments(ownerType, ownerId);
  const [adding, setAdding] = useState(false);
  const [viewing, setViewing] = useState<Doc | null>(null);
  const [deleting, setDeleting] = useState<Doc | null>(null);
  const key = [["documents", ownerType, ownerId]];
  const toggle = useAction((d: Doc) => http.patch(`/documents/${d.id}`, { pinned: !d.pinned }), { invalidate: key });
  const remove = useAction((d: Doc) => http.del(`/documents/${d.id}`), { invalidate: key, success: "Document removed", onSuccess: () => setDeleting(null) });

  return (
    <Card>
      <CardHeader
        title={title}
        description={description ?? "Agents search these with knowledge_search. Pinned documents are injected into every prompt."}
        actions={!readOnly && <Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => setAdding(true)}>Add</Button>}
      />
      <div className="p-2 sm:p-3">
        {docs.isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : !docs.data?.length ? (
          <EmptyState icon={<FileText className="size-5" />} title="No documents yet" description="Upload PDFs, Word, Markdown, CSV or text, paste content, or import a web page." className="border-0" />
        ) : (
          <ul className="divide-y divide-border">
            {docs.data.map((d) => (
              <li key={d.id} className="flex items-center gap-3 px-2 py-2.5">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted"><FileText className="size-4" /></div>
                <button className="min-w-0 flex-1 cursor-pointer text-left" onClick={async () => setViewing(await http.get<Doc>(`/documents/${d.id}`))}>
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{d.title}</span>
                    {d.pinned && <Badge tone="primary" icon={<Pin className="size-2.5" />}>Pinned</Badge>}
                  </div>
                  <div className="truncate text-xs text-muted">{d.source} · {bytes(d.size)} · {d.chunk_count} chunks · {timeAgo(d.created_at)}</div>
                </button>
                {!readOnly && (
                  <div className="flex shrink-0 gap-1">
                    <Button variant="ghost" size="icon" title={d.pinned ? "Unpin" : "Pin to prompt"} onClick={() => toggle.mutate(d)}>
                      {d.pinned ? <PinOff className="size-4 text-muted" /> : <Pin className="size-4 text-muted" />}
                    </Button>
                    <Button variant="ghost" size="icon" title="Delete" onClick={() => setDeleting(d)}>
                      <Trash2 className="size-4 text-muted" />
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <AddDocumentDialog open={adding} onClose={() => setAdding(false)} ownerType={ownerType} ownerId={ownerId} />
      <Dialog open={!!viewing} onClose={() => setViewing(null)} title={viewing?.title} description={viewing ? `${viewing.chunk_count} chunks · ${bytes(viewing.size)}` : ""} size="lg">
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">{viewing?.content}</pre>
      </Dialog>
      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting)} loading={remove.isPending} title={`Delete “${deleting?.title}”?`} />
    </Card>
  );
}

function AddDocumentDialog({ open, onClose, ownerType, ownerId }: { open: boolean; onClose: () => void; ownerType: string; ownerId: string }) {
  const [mode, setMode] = useState<"upload" | "text" | "url">("upload");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [pinned, setPinned] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const key = [["documents", ownerType, ownerId]];
  const reset = () => {
    setTitle("");
    setContent("");
    setUrl("");
    setFile(null);
    setPinned(false);
  };
  const done = useAction(async () => {
    if (mode === "upload") {
      if (!file) throw new Error("Choose a file");
      const fd = new FormData();
      fd.append("file", file);
      fd.append("owner_type", ownerType);
      fd.append("owner_id", ownerId);
      fd.append("pinned", String(pinned));
      if (title) fd.append("title", title);
      return http.upload("/documents/upload", fd);
    }
    if (mode === "url") return http.post("/documents/from-url", { owner_type: ownerType, owner_id: ownerId, url, title: title || undefined, pinned });
    return http.post("/documents", { owner_type: ownerType, owner_id: ownerId, title, content, pinned });
  }, { invalidate: key, success: "Document added", onSuccess: () => { reset(); onClose(); } });

  const submit = async () => {
    setBusy(true);
    try {
      await done.mutateAsync();
    } catch (e) {
      if (!(e instanceof Error) || e.message === "Choose a file") toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Add document"
      size="lg"
      footer={
        <>
          <Checkbox className="mr-auto" checked={pinned} onChange={setPinned} label="Pin to every prompt" />
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button loading={busy} onClick={submit}>Add document</Button>
        </>
      }
    >
      <Tabs
        tabs={[
          { key: "upload", label: <><FileUp className="size-3.5" /> Upload</> },
          { key: "text", label: <><FileText className="size-3.5" /> Paste text</> },
          { key: "url", label: <><Link2 className="size-3.5" /> From URL</> },
        ]}
        value={mode}
        onChange={setMode}
        className="mb-4"
      />
      <div className="space-y-4">
        {mode === "upload" && (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
            }}
            onClick={() => fileRef.current?.click()}
            className={cn("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors", drag ? "border-primary bg-primary-soft/50" : "border-border hover:bg-surface-2")}
          >
            <FileUp className="mb-2 size-6 text-muted" />
            <div className="text-sm font-medium">{file ? file.name : "Drop a file or click to browse"}</div>
            <div className="mt-1 text-xs text-muted">PDF, DOCX, MD, TXT, CSV, JSON, HTML · up to 15 MB</div>
            <input ref={fileRef} type="file" hidden accept=".pdf,.docx,.md,.markdown,.txt,.csv,.tsv,.json,.html,.htm,.yaml,.yml,.xml,.log" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
        )}
        {mode === "url" && (
          <Field label="Page URL" hint="The page is fetched through the SSRF-safe browser and converted to text.">
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/handbook" />
          </Field>
        )}
        <Field label={mode === "text" ? "Title" : "Title (optional)"}>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Refund policy" />
        </Field>
        {mode === "text" && (
          <Field label="Content">
            <Textarea rows={10} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Paste text or markdown…" />
          </Field>
        )}
      </div>
    </Dialog>
  );
}
