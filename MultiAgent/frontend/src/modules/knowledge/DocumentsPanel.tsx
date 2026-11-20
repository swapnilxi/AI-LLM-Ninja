import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { FileText, Globe, Pin, PinOff, Plus, Trash2, Type, Upload } from "lucide-react";
import { http } from "@/shared/lib/api";
import type { Doc } from "@/modules/knowledge/types";
import { bytes, timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { withReturn } from "@/shared/hooks/useReturnTo";
import { useDocuments } from "@/modules/knowledge/api";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { Badge, Button, Card, CardHeader, EmptyState, Spinner } from "@/shared/ui/primitives";

const SOURCE_ICON: Record<string, typeof FileText> = { upload: Upload, url: Globe, text: Type };

/** Where "Add" goes: agents use their training page, projects/org use the generic ingest page. */
export function ingestPath(ownerType: string, ownerId: string): string {
  return ownerType === "agent" ? `/training/${ownerId}/ingest` : `/training/ingest?owner_type=${ownerType}&owner_id=${encodeURIComponent(ownerId)}`;
}

/** Knowledge documents attached to an org, project or agent. Adding and reading documents happen on their own pages. */
export function DocumentsPanel({ ownerType, ownerId, readOnly, title = "Knowledge documents", description, hideAdd }: {
  ownerType: "org" | "project" | "agent";
  ownerId: string;
  readOnly?: boolean;
  title?: string;
  description?: string;
  /** Hide the Add button (e.g. when the ingest form is already on the page). */
  hideAdd?: boolean;
}) {
  const loc = useLocation();
  const nav = useNavigate();
  const here = `${loc.pathname}${loc.search}`;
  const docs = useDocuments(ownerType, ownerId);
  const [deleting, setDeleting] = useState<Doc | null>(null);
  const key = [["documents", ownerType, ownerId], ["training"]];
  const toggle = useAction((d: Doc) => http.patch(`/documents/${d.id}`, { pinned: !d.pinned }), { invalidate: key });
  const remove = useAction((d: Doc) => http.del(`/documents/${d.id}`), { invalidate: key, success: "Document removed", onSuccess: () => setDeleting(null) });
  const addTo = ownerType === "agent" ? ingestPath(ownerType, ownerId) : withReturn(ingestPath(ownerType, ownerId), here);
  const total = docs.data?.reduce((n, d) => n + d.chunk_count, 0) ?? 0;

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            {title}
            {!!docs.data?.length && <Badge tone="muted">{docs.data.length} · {total} chunks</Badge>}
          </span>
        }
        description={description ?? "Agents search these with knowledge_search. Pinned documents are injected into every prompt."}
        actions={
          !readOnly &&
          !hideAdd && (
            <Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => nav(addTo)}>Add</Button>
          )
        }
      />
      <div className="p-2 sm:p-3">
        {docs.isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : !docs.data?.length ? (
          <EmptyState icon={<FileText className="size-5" />} title="No documents yet" description="Upload PDFs, Word, Markdown, CSV or text, paste content, or import a web page." className="border-0" />
        ) : (
          <ul className="divide-y divide-border">
            {docs.data.map((d) => {
              const Icon = SOURCE_ICON[d.source] ?? FileText;
              return (
                <li key={d.id} className="flex items-center gap-3 px-2 py-2.5">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-muted"><Icon className="size-4" /></div>
                  <Link to={withReturn(`/training/documents/${d.id}`, here)} className="min-w-0 flex-1 rounded-md text-left hover:text-primary">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{d.title}</span>
                      {d.pinned && <Badge tone="primary" icon={<Pin className="size-2.5" />}>Pinned</Badge>}
                    </div>
                    <div className="truncate text-xs text-muted">{d.source} · {bytes(d.size)} · {d.chunk_count} chunk{d.chunk_count === 1 ? "" : "s"} · {timeAgo(d.created_at)}</div>
                  </Link>
                  {!readOnly && (
                    <div className="flex shrink-0 gap-1">
                      <Button variant="ghost" size="icon" title={d.pinned ? "Unpin" : "Pin to prompt"} aria-label={d.pinned ? "Unpin" : "Pin to prompt"} onClick={() => toggle.mutate(d)}>
                        {d.pinned ? <PinOff className="size-4 text-muted" /> : <Pin className="size-4 text-muted" />}
                      </Button>
                      <Button variant="ghost" size="icon" title="Delete" aria-label="Delete" onClick={() => setDeleting(d)}>
                        <Trash2 className="size-4 text-muted" />
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting)} loading={remove.isPending} title={`Delete “${deleting?.title}”?`} description="The document and its chunks are removed from the agent's knowledge. This cannot be undone." />
    </Card>
  );
}
