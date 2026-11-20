import { lazy } from "react";
import { Wrench } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const ToolsList = lazy(() => import("./ToolsList"));
const ToolEditor = lazy(() => import("./ToolEditor"));

export default defineModule({
  id: "tools",
  nav: [{ to: "/tools", label: "Tools", icon: Wrench, section: "Build", order: 60 }],
  routes: [
    { path: "tools", element: <ToolsList /> },
    { path: "tools/:id", element: <ToolEditor /> },
  ],
});
