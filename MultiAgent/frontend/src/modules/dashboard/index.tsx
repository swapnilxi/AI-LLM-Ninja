import { lazy } from "react";
import { LayoutDashboard } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const Dashboard = lazy(() => import("./Dashboard"));

export default defineModule({
  id: "dashboard",
  nav: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, section: "", order: 0, end: true }],
  routes: [{ index: true, element: <Dashboard /> }],
});
