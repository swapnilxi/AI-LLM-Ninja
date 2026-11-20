import { lazy } from "react";
import { Bot, Plus } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const AgentsList = lazy(() => import("./AgentsList"));
const AgentCreate = lazy(() => import("./AgentCreate"));
const AgentWorkspace = lazy(() => import("./AgentWorkspace"));

export default defineModule({
  id: "agents",
  nav: [{ to: "/agents", label: "Agents", icon: Bot, section: "Build", order: 10 }],
  commands: [{ id: "n-agent", group: "Create", label: "New agent", icon: Plus, to: "/agents/new" }],
  routes: [
    { path: "agents", element: <AgentsList /> },
    { path: "agents/new", element: <AgentCreate /> },
    // overview, profile, instructions, model, tools, skills, knowledge, settings
    { path: "agents/:id/*", element: <AgentWorkspace /> },
  ],
});
