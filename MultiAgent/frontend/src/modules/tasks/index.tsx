import { lazy } from "react";
import { ListChecks, WandSparkles } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const Tasks = lazy(() => import("./Tasks"));
const ExtractTasksPage = lazy(() => import("./ExtractTasksPage"));

export default defineModule({
  id: "tasks",
  nav: [{ to: "/tasks", label: "Tasks", icon: ListChecks, section: "Operate", order: 10, keywords: "todo to-do action items" }],
  commands: [{ id: "n-extract-tasks", group: "Create", label: "Text to tasks", icon: WandSparkles, to: "/tasks/extract", keywords: "extract action items notes" }],
  routes: [
    { path: "tasks", element: <Tasks /> },
    { path: "tasks/extract", element: <ExtractTasksPage /> },
  ],
});
