import { lazy } from "react";
import { FileUp, GraduationCap } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const TrainingHome = lazy(() => import("./TrainingHome"));
const AgentTraining = lazy(() => import("./AgentTraining"));
const IngestPage = lazy(() => import("./IngestPage"));
const DocumentPage = lazy(() => import("./DocumentPage"));

export default defineModule({
  id: "training",
  nav: [{ to: "/training", label: "Training", icon: GraduationCap, section: "Build", order: 15, keywords: "teach ingest documents knowledge lessons memory" }],
  commands: [
    { id: "n-teach", group: "Create", label: "Teach an agent", icon: GraduationCap, to: "/training", keywords: "train lesson rule fact example correction" },
    { id: "p-ingest", label: "Ingest documents into an agent", icon: FileUp, to: "/training", keywords: "upload knowledge pdf docs training" },
  ],
  routes: [
    { path: "training", element: <TrainingHome /> },
    // Static segments win over `:agentId`, so these two never collide with an agent id.
    { path: "training/ingest", element: <IngestPage /> },
    { path: "training/documents/:docId", element: <DocumentPage /> },
    // /training/:agentId/{ingest,teach,review,memory,test,settings}
    { path: "training/:agentId/*", element: <AgentTraining /> },
  ],
});
