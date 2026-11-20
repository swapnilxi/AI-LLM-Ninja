import { lazy } from "react";
import { Activity } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const RunsList = lazy(() => import("./RunsList"));
const RunDetail = lazy(() => import("./RunDetail"));
const NewRun = lazy(() => import("./NewRun"));

export default defineModule({
  id: "runs",
  nav: [{ to: "/runs", label: "Runs", icon: Activity, section: "Operate", order: 30, keywords: "history logs" }],
  routes: [
    { path: "runs", element: <RunsList /> },
    { path: "runs/new", element: <NewRun /> },
    { path: "runs/:id", element: <RunDetail /> },
  ],
});
