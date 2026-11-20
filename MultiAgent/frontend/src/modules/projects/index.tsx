import { lazy } from "react";
import { FolderKanban, Plus } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const ProjectsList = lazy(() => import("./ProjectsList"));
const NewProjectPage = lazy(() => import("./ProjectsList").then((m) => ({ default: m.NewProjectPage })));
const ProjectDetail = lazy(() => import("./ProjectDetail"));

export default defineModule({
  id: "projects",
  nav: [{ to: "/projects", label: "Projects", icon: FolderKanban, section: "Workspace", order: 10 }],
  commands: [{ id: "n-project", group: "Create", label: "New project", icon: Plus, to: "/projects/new" }],
  routes: [
    { path: "projects", element: <ProjectsList /> },
    { path: "projects/new", element: <NewProjectPage /> },
    { path: "projects/:id", element: <ProjectDetail /> },
  ],
});
