import { lazy } from "react";
import { FileDown, Plus, Sparkles, Terminal } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const SkillsList = lazy(() => import("./SkillsList"));
const ImportSkillPage = lazy(() => import("./SkillsList").then((m) => ({ default: m.ImportSkillPage })));
const InstallSkillPage = lazy(() => import("./SkillsList").then((m) => ({ default: m.InstallSkillPage })));
const SkillEditor = lazy(() => import("./SkillEditor"));

export default defineModule({
  id: "skills",
  nav: [{ to: "/skills", label: "Skills", icon: Sparkles, section: "Build", order: 50 }],
  commands: [
    { id: "p-tpl", label: "Skill templates", icon: Sparkles, to: "/skills?tab=templates", keywords: "gallery" },
    { id: "n-skill", group: "Create", label: "New skill", icon: Plus, to: "/skills/new" },
    { id: "n-skill-import", group: "Create", label: "Import SKILL.md", icon: FileDown, to: "/skills/import", keywords: "markdown paste" },
    { id: "n-skill-install", group: "Create", label: "Install skill from GitHub", icon: Terminal, to: "/skills/install", keywords: "npx skills add" },
  ],
  routes: [
    { path: "skills", element: <SkillsList /> },
    { path: "skills/import", element: <ImportSkillPage /> },
    { path: "skills/install", element: <InstallSkillPage /> },
    // /skills/new also accepts ?attach_agent=<id>, ?attach_conversation=<id> and ?return_to=<path>
    { path: "skills/:id", element: <SkillEditor /> },
  ],
});
