import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Building2, FolderKanban, Lock } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { useReturnTo, withReturn } from "@/shared/hooks/useReturnTo";
import { DocumentsPanel } from "@/modules/knowledge/DocumentsPanel";
import { Ingestor } from "@/modules/knowledge/Ingestor";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { IconTile } from "@/shared/ui/icons";
import { Button, EmptyState } from "@/shared/ui/primitives";

/** /training/ingest?owner_type=project|org&owner_id=…&return_to=… - add documents to a project or the organization. */
export default function IngestPage() {
  const [params] = useSearchParams();
  const loc = useLocation();
  const nav = useNavigate();
  const { org, projects, can } = useAuth();
  const ownerType = params.get("owner_type");
  const ownerId = params.get("owner_id") ?? "";
  const fallback = ownerType === "project" ? `/projects/${ownerId}` : ownerType === "org" ? "/settings" : "/training";
  const back = useReturnTo(fallback);

  if (ownerType === "agent" && ownerId) return <Navigate to={`/training/${ownerId}/ingest`} replace />;
  if ((ownerType !== "project" && ownerType !== "org") || !ownerId)
    return (
      <Page>
        <PageHeader title="Ingest documents" back="/training" />
        <EmptyState title="Nothing to ingest into" description="Open this page from a project's or the organization's knowledge section, or pick an agent on the Training page." action={<Button onClick={() => nav("/training")}>Go to Training</Button>} />
      </Page>
    );

  const project = ownerType === "project" ? projects.find((p) => p.id === ownerId) : undefined;
  const name = ownerType === "org" ? org?.name ?? "Organization" : project?.name ?? "Project";
  const readOnly = ownerType === "org" ? !can("admin") : !can("member");
  const here = `${loc.pathname}${loc.search}`;

  return (
    <Page>
      <PageHeader
        back={back}
        icon={<IconTile icon={ownerType === "org" ? Building2 : FolderKanban} color={ownerType === "org" ? "slate" : "sky"} />}
        title={`Add knowledge to ${name}`}
        description={
          ownerType === "org"
            ? "Organization documents are searchable by every agent in every project."
            : "Project documents are searchable by every agent working in this project."
        }
        actions={<Button variant="outline" onClick={() => nav(back)}>Done</Button>}
      />
      {readOnly ? (
        <div className="mb-5 flex items-center gap-3 rounded-xl border border-indigo-500/20 bg-gradient-to-r from-primary-soft to-transparent p-4 text-sm">
          <Lock className="size-5 shrink-0 text-primary" />
          <span className="text-muted">{ownerType === "org" ? "Only admins can add organization documents." : "Your role cannot add documents."}</span>
        </div>
      ) : null}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        {!readOnly && <Ingestor ownerType={ownerType} ownerId={ownerId} docLink={(d) => withReturn(`/training/documents/${d.id}`, here)} className="self-start" />}
        <div className={readOnly ? "lg:col-span-2" : ""}>
          <DocumentsPanel ownerType={ownerType} ownerId={ownerId} readOnly={readOnly} hideAdd title={ownerType === "org" ? "Organization documents" : "Project documents"} />
        </div>
      </div>
    </Page>
  );
}
