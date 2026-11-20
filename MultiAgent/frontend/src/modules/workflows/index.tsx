import { lazy } from "react";
import { Plus, Workflow } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const WorkflowsList = lazy(() => import("./WorkflowsList"));
const WorkflowBuilder = lazy(() => import("./WorkflowBuilder"));

export default defineModule({
  id: "workflows",
  nav: [{ to: "/workflows", label: "Workflows", icon: Workflow, section: "Build", order: 40 }],
  commands: [{ id: "n-wf", group: "Create", label: "New workflow", icon: Plus, to: "/workflows/new" }],
  routes: [
    { path: "workflows", element: <WorkflowsList /> },
    // `/*` keeps the builder mounted for nested panels such as /workflows/:id/inputs
    { path: "workflows/:id/*", element: <WorkflowBuilder /> },
  ],
});
