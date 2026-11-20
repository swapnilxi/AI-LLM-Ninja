import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Code2, ExternalLink, FileText, Pin, PinOff, Trash2, Type } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { bytes, formatDate } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useReturnTo } from "@/shared/hooks/useReturnTo";
import { useDocument } from "@/modules/knowledge/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { Markdown } from "@/shared/ui/Markdown";
import { Badge, Button, Card, CardHeader, EmptyState, PageLoader } from "@/shared/ui/primitives";

const MAX_RENDER = 300_000; // keep very large documents responsive

function ownerHome(ownerType?: string, ownerId?: string): string {
  if (ownerType === "agent") return `/training/${ownerId}/ingest`;
  if (ownerType === "project") return `/projects/${ownerId}`;
  if (ownerType === "org") return "/settings";
  return "/training";
}

/** /training/documents/:docId - read one knowledge document. */
export default function DocumentPage() {
  const { docId } = useParams();
  const doc = useDocument(docId);
  const nav = useNavigate();
  const { can } = useAuth();
  const back = useReturnTo(ownerHome(doc.data?.owner_type, doc.data?.owner_id));
  const [confirm, setConfirm] = useState(false);
  const [full, setFull] = useState(false);
  const d = doc.data;
  const isMarkdown = !!d && (/\.(md|markdown)$/i.test(d.source_ref || d.title) || d.mime.includes("markdown"));
  const [rendered, setRendered] = useState(true);
  const inv = [["document", docId], ["documents", d?.owner_type, d?.owner_id], ["training"]];
  const toggle = useAction(() => http.patch(`/documents/${docId}`, { pinned: !d?.pinned }), { invalidate: inv });
  const remove = useAction(() => http.del(`/documents/${docId}`), {
    success: "Document removed",
    invalidate: [["documents", d?.owner_type, d?.owner_id], ["training"]],
    onSuccess: () => nav(back, { replace: true }),
  });

  if (doc.isLoading) return <PageLoader />;
  if (!d)
    return (
      <Page>
        <PageHeader title="Document not found" back={back} />
        <EmptyState icon={<FileText className="size-5" />} title="This document does not exist or was deleted." />
      </Page>
    );

  const readOnly = !can("member") || (d.owner_type === "org" && !can("admin"));
  const content = full ? d.content : d.content.slice(0, MAX_RENDER);
  const truncated = !full && d.content.length > MAX_RENDER;
  const isUrl = /^https?:\/\//i.test(d.source_ref);

  return (
    <Page>
      <PageHeader
        back={back}
        title={d.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {d.pinned && <Badge tone="primary" icon={<Pin className="size-2.5" />}>Pinned</Badge>}
            <span>{bytes(d.size)} · {d.chunk_count} chunk{d.chunk_count === 1 ? "" : "s"} · added {formatDate(d.created_at)}</span>
          </span>
        }
        actions={
          !readOnly && (
            <>
              <Button variant="outline" icon={d.pinned ? <PinOff className="size-4" /> : <Pin className="size-4" />} loading={toggle.isPending} onClick={() => toggle.mutate()}>
                {d.pinned ? "Unpin" : "Pin to prompt"}
              </Button>
              <Button variant="outline" icon={<Trash2 className="size-4" />} onClick={() => setConfirm(true)}>Delete</Button>
            </>
          )
        }
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
        <Card className="min-w-0">
          <CardHeader
            title="Content"
            description="The extracted text the agent searches."
            actions={
              isMarkdown && (
                <Button size="sm" variant="ghost" icon={rendered ? <Code2 className="size-3.5" /> : <Type className="size-3.5" />} onClick={() => setRendered(!rendered)}>
                  {rendered ? "Raw" : "Rendered"}
                </Button>
              )
            }
          />
          <div className="p-4 sm:p-5">
            {isMarkdown && rendered ? (
              <Markdown>{content}</Markdown>
            ) : (
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">{content}</pre>
            )}
            {truncated && (
              <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-muted">
                Showing the first {MAX_RENDER.toLocaleString()} of {d.content.length.toLocaleString()} characters.
                <Button size="sm" variant="outline" onClick={() => setFull(true)}>Show all</Button>
              </div>
            )}
          </div>
        </Card>

        <Card className="self-start">
          <CardHeader title="Details" />
          <dl className="divide-y divide-border text-sm">
            <Row label="Belongs to">
              <Link to={ownerHome(d.owner_type, d.owner_id)} className="font-medium text-primary hover:underline">
                {d.owner_type === "agent" ? "Agent" : d.owner_type === "project" ? "Project" : "Organization"}
              </Link>
            </Row>
            <Row label="Source">{d.source}</Row>
            {d.source_ref && (
              <Row label={isUrl ? "URL" : "File"}>
                {isUrl ? (
                  <a href={d.source_ref} target="_blank" rel="noreferrer noopener" className="inline-flex max-w-full items-center gap-1 text-primary hover:underline">
                    <span className="truncate">{d.source_ref.replace(/^https?:\/\//, "")}</span>
                    <ExternalLink className="size-3 shrink-0" />
                  </a>
                ) : (
                  <span className="break-all">{d.source_ref}</span>
                )}
              </Row>
            )}
            {d.mime && <Row label="Type"><span className="break-all font-mono text-xs">{d.mime}</span></Row>}
            <Row label="Size">{bytes(d.size)}</Row>
            <Row label="Chunks">{d.chunk_count}</Row>
            <Row label="Updated">{formatDate(d.updated_at)}</Row>
          </dl>
          {d.owner_type === "agent" && (
            <div className="border-t border-border p-3">
              <Button variant="outline" size="sm" className="w-full justify-center" onClick={() => nav(`/training/${d.owner_id}/test`)}>Test retrieval for this agent</Button>
            </div>
          )}
        </Card>
      </div>

      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => remove.mutate()}
        loading={remove.isPending}
        title={`Delete “${d.title}”?`}
        description="The document and its chunks are removed from the knowledge base. This cannot be undone."
      />
    </Page>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-4 py-2.5">
      <dt className="shrink-0 text-xs text-muted">{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  );
}
