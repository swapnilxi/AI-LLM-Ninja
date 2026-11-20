import { DocumentsPanel } from "@/modules/knowledge/DocumentsPanel";
import { Ingestor } from "@/modules/knowledge/Ingestor";
import { withReturn } from "@/shared/hooks/useReturnTo";
import type { TabProps } from "../AgentTraining";

export function IngestTab({ agent, canEdit }: TabProps) {
  const here = `/training/${agent.id}/ingest`;
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      {canEdit && <Ingestor ownerType="agent" ownerId={agent.id} docLink={(d) => withReturn(`/training/documents/${d.id}`, here)} className="self-start" />}
      <div className={canEdit ? "" : "lg:col-span-2"}>
        <DocumentsPanel
          ownerType="agent"
          ownerId={agent.id}
          readOnly={!canEdit}
          hideAdd
          title="Ingested documents"
          description="Only this agent searches these (on top of project and organization documents). Pinned documents go into every prompt."
        />
      </div>
    </div>
  );
}
