import { lazy } from "react";
import { Plus, Users } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const TeamsList = lazy(() => import("./TeamsList"));
const TeamEditor = lazy(() => import("./TeamEditor"));

export default defineModule({
  id: "teams",
  nav: [{ to: "/teams", label: "Teams", icon: Users, section: "Build", order: 30 }],
  commands: [{ id: "n-team", group: "Create", label: "New team", icon: Plus, to: "/teams/new" }],
  routes: [
    { path: "teams", element: <TeamsList /> },
    { path: "teams/:id", element: <TeamEditor /> },
  ],
});
