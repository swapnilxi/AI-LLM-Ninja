import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { AppShell } from "@/components/layout/AppShell";
import { PageLoader } from "@/components/ui/primitives";
import Login from "@/pages/auth/Login";
import Register from "@/pages/auth/Register";

const Dashboard = lazy(() => import("@/pages/dashboard/Dashboard"));
const AgentsList = lazy(() => import("@/pages/agents/AgentsList"));
const AgentEditor = lazy(() => import("@/pages/agents/AgentEditor"));
const SkillsList = lazy(() => import("@/pages/skills/SkillsList"));
const SkillEditor = lazy(() => import("@/pages/skills/SkillEditor"));
const ToolsList = lazy(() => import("@/pages/tools/ToolsList"));
const ToolEditor = lazy(() => import("@/pages/tools/ToolEditor"));
const Connectors = lazy(() => import("@/pages/connectors/Connectors"));
const Discover = lazy(() => import("@/pages/discover/Discover"));
const Tasks = lazy(() => import("@/pages/tasks/Tasks"));
const TeamsList = lazy(() => import("@/pages/teams/TeamsList"));
const TeamEditor = lazy(() => import("@/pages/teams/TeamEditor"));
const WorkflowsList = lazy(() => import("@/pages/workflows/WorkflowsList"));
const WorkflowBuilder = lazy(() => import("@/pages/workflows/WorkflowBuilder"));
const Chat = lazy(() => import("@/pages/chat/Chat"));
const Automations = lazy(() => import("@/pages/automations/Automations"));
const RunsList = lazy(() => import("@/pages/runs/RunsList"));
const RunDetail = lazy(() => import("@/pages/runs/RunDetail"));
const ProjectsList = lazy(() => import("@/pages/projects/ProjectsList"));
const ProjectDetail = lazy(() => import("@/pages/projects/ProjectDetail"));
const Settings = lazy(() => import("@/pages/settings/Settings"));

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route
          path="*"
          element={
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route index element={<Dashboard />} />
                <Route path="agents" element={<AgentsList />} />
                <Route path="agents/:id" element={<AgentEditor />} />
                <Route path="skills" element={<SkillsList />} />
                <Route path="skills/:id" element={<SkillEditor />} />
                <Route path="tools" element={<ToolsList />} />
                <Route path="tools/:id" element={<ToolEditor />} />
                <Route path="connectors" element={<Connectors />} />
                <Route path="discover" element={<Discover />} />
                <Route path="tasks" element={<Tasks />} />
                <Route path="teams" element={<TeamsList />} />
                <Route path="teams/:id" element={<TeamEditor />} />
                <Route path="workflows" element={<WorkflowsList />} />
                <Route path="workflows/:id" element={<WorkflowBuilder />} />
                <Route path="chat" element={<Chat />} />
                <Route path="chat/:conversationId" element={<Chat />} />
                <Route path="automations" element={<Automations />} />
                <Route path="runs" element={<RunsList />} />
                <Route path="runs/:id" element={<RunDetail />} />
                <Route path="projects" element={<ProjectsList />} />
                <Route path="projects/:id" element={<ProjectDetail />} />
                <Route path="settings" element={<Settings />} />
                <Route path="settings/:tab" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}
