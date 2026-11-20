import { Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { Brain, FlaskConical, GraduationCap, Inbox, Lock, MessagesSquare, Settings2, SlidersHorizontal, Upload } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { useAction } from "@/shared/hooks/useAction";
import type { Agent } from "@/modules/agents/types";
import { useAgent } from "@/modules/agents/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { RouteTabs } from "@/shared/ui/RouteTabs";
import { AgentAvatar } from "@/shared/ui/icons";
import { Button, EmptyState, PageLoader } from "@/shared/ui/primitives";
import { ScopeBadge } from "@/shared/components/library";
import { useTraining } from "./api";
import { canTrain } from "./parts";
import { IngestTab } from "./tabs/IngestTab";
import { TeachTab } from "./tabs/TeachTab";
import { ReviewTab } from "./tabs/ReviewTab";
import { MemoryTab } from "./tabs/MemoryTab";
import { TestTab } from "./tabs/TestTab";
import { SettingsTab } from "./tabs/SettingsTab";

export interface TabProps {
  agent: Agent;
  canEdit: boolean;
}

/** /training/:agentId/* - one agent's training window, every section is its own URL. */
export default function AgentTraining() {
  const { agentId = "" } = useParams();
  const agent = useAgent(agentId);
  const overview = useTraining(agentId);
  const { user, can } = useAuth();
  const nav = useNavigate();
  const dup = useAction(() => http.post<Agent>(`/agents/${agentId}/duplicate`), { success: "Duplicated into your org", invalidate: [["agents"], ["training", "grid"]], onSuccess: (a) => nav(`/training/${a.id}`) });

  if (agent.isLoading) return <PageLoader />;
  if (!agent.data)
    return (
      <Page>
        <PageHeader title="Agent not found" back="/training" />
        <EmptyState icon={<GraduationCap className="size-5" />} title="This agent does not exist or is not visible in this organization." action={<Button variant="outline" onClick={() => nav("/training")}>Back to Training</Button>} />
      </Page>
    );

  const a = agent.data;
  const canEdit = canTrain(a, user, can("member"));
  const o = overview.data;
  const base = `/training/${a.id}`;
  const props: TabProps = { agent: a, canEdit };

  return (
    <Page>
      <PageHeader
        back="/training"
        icon={<AgentAvatar agent={a} />}
        title={a.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <ScopeBadge orgId={a.org_id} />
            <span>Teach, ingest and test what this agent knows.</span>
          </span>
        }
        actions={
          <>
            <Button variant="outline" size="sm" icon={<MessagesSquare className="size-4" />} onClick={() => nav(`/chat?agent=${a.id}`)}>Chat</Button>
            <Button variant="outline" size="sm" icon={<Settings2 className="size-4" />} onClick={() => nav(`/agents/${a.id}`)}>Manage agent</Button>
          </>
        }
      />

      {!canEdit && (
        <div className="mb-5 flex flex-col gap-3 rounded-xl border border-indigo-500/20 bg-gradient-to-r from-primary-soft to-transparent p-4 sm:flex-row sm:items-center">
          <Lock className="size-5 shrink-0 text-primary" />
          <div className="flex-1 text-sm">
            <span className="font-medium">Read-only.</span>{" "}
            <span className="text-muted">
              {a.org_id === null ? "This is a global library agent. Duplicate it into your organization to train it." : "Your role can view this agent's training but not change it."}
            </span>
          </div>
          {a.org_id === null && can("member") && (
            <Button size="sm" loading={dup.isPending} onClick={() => dup.mutate()}>Duplicate to my org</Button>
          )}
        </div>
      )}

      <RouteTabs
        className="mb-5"
        tabs={[
          { to: `${base}/ingest`, label: "Ingest", icon: Upload, count: o?.documents },
          { to: `${base}/teach`, label: "Teach", icon: GraduationCap, count: o?.approved },
          { to: `${base}/review`, label: "Review", icon: Inbox, count: o?.pending || undefined },
          { to: `${base}/memory`, label: "Memory", icon: Brain, count: o?.memories },
          { to: `${base}/test`, label: "Test", icon: FlaskConical },
          { to: `${base}/settings`, label: "Settings", icon: SlidersHorizontal },
        ]}
      />

      <Routes>
        <Route index element={<Navigate to={`${base}/ingest`} replace />} />
        <Route path="ingest" element={<IngestTab {...props} />} />
        <Route path="teach" element={<TeachTab {...props} />} />
        <Route path="review" element={<ReviewTab {...props} />} />
        <Route path="memory" element={<MemoryTab {...props} />} />
        <Route path="test" element={<TestTab {...props} />} />
        <Route path="settings" element={<SettingsTab {...props} />} />
        <Route path="*" element={<Navigate to={`${base}/ingest`} replace />} />
      </Routes>
    </Page>
  );
}
