import { lazy } from "react";
import { Plug } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const Connectors = lazy(() => import("./Connectors"));
const ConnectionPage = lazy(() => import("./Connectors").then((m) => ({ default: m.ConnectionPage })));

export default defineModule({
  id: "connectors",
  nav: [{ to: "/connectors", label: "Connectors", icon: Plug, section: "Build", order: 70, keywords: "apps integrations mcp" }],
  routes: [
    { path: "connectors", element: <Connectors /> },
    { path: "connectors/new/:connectorKey", element: <ConnectionPage /> },
    { path: "connectors/:id", element: <ConnectionPage /> },
  ],
});
