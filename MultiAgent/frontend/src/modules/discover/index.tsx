import { lazy } from "react";
import { Compass, Plug } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const Discover = lazy(() => import("./Discover"));
const McpInstallPage = lazy(() => import("./McpServers").then((m) => ({ default: m.McpInstallPage })));

export default defineModule({
  id: "discover",
  nav: [{ to: "/discover", label: "Discover", icon: Compass, section: "Build", order: 80, keywords: "install skills mcp connectors marketplace browser use find skill top skills" }],
  commands: [{ id: "p-mcp", label: "Popular MCP servers", icon: Plug, to: "/discover?tab=connectors", keywords: "connect tools github context7 deepwiki browser use" }],
  routes: [
    { path: "discover", element: <Discover /> },
    { path: "discover/mcp/:serverId", element: <McpInstallPage /> },
  ],
});
