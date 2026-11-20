/** `/agents/:id/*` - agent layout: header, URL tabs and one shared form for every sub-page. */
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Bot, BookOpen, Cpu, GraduationCap, LayoutDashboard, MessagesSquare, Play, Save, ScrollText, Settings2, Sparkles, UserRound, Wrench } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { useAction } from "@/shared/hooks/useAction";
import { useProviders } from "@/modules/settings/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Button, EmptyState, PageLoader } from "@/shared/ui/primitives";
import { RouteTabs } from "@/shared/ui/RouteTabs";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { AgentAvatar } from "@/shared/ui/icons";
import { GlobalNotice, SaveBar, ScopeBadge } from "@/shared/components/library";
import { useAgent } from "./api";
import type { Agent, AgentSettings } from "./types";
import { sameForm, toForm, toPayload, type AgentForm } from "./form";
import { AgentWorkspaceContext, type AgentWorkspaceCtx } from "./context";
import { modelLabel, runAgentUrl } from "./parts";

const Overview = lazy(() => import("./sections/Overview"));
const Profile = lazy(() => import("./sections/Profile"));
const Instructions = lazy(() => import("./sections/Instructions"));
const ModelSection = lazy(() => import("./sections/ModelSection"));
const ToolsSection = lazy(() => import("./sections/ToolsSection"));
const SkillsSection = lazy(() => import("./sections/SkillsSection"));
const KnowledgeSection = lazy(() => import("./sections/KnowledgeSection"));
const SettingsSection = lazy(() => import("./sections/SettingsSection"));

export default function AgentWorkspaceRoute() {
  const { id } = useParams();
  if (!id) return <Navigate to="/agents" replace />;
  // keyed so switching agents (e.g. after duplicating) starts with fresh form state
  return <AgentWorkspace key={id} id={id} />;
}

function AgentWorkspace({ id }: { id: string }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { can, user } = useAuth();
  const agent = useAgent(id);
  const providers = useProviders();

  const [form, setFormState] = useState<AgentForm | null>(null);
  const [baseline, setBaseline] = useState<AgentForm | null>(null);
  const baseRef = useRef<AgentForm | null>(null);
  const [pendingNav, setPendingNav] = useState<string | null>(null);

  // Load once; later refetches only replace the form when the user has no unsaved edits.
  useEffect(() => {
    if (!agent.data) return;
    const next = toForm(agent.data);
    setFormState((f) => (!f || sameForm(f, baseRef.current) ? next : f));
    baseRef.current = next;
    setBaseline(next);
  }, [agent.data]);

  const dirty = !!form && !!baseline && !sameForm(form, baseline);
  const readOnly = !can("member") || (!!agent.data && agent.data.org_id === null && !user?.is_superadmin);

  useEffect(() => {
    if (!dirty) return;
    const h = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [dirty]);

  const applySaved = useCallback(
    (a: Agent) => {
      const next = toForm(a);
      baseRef.current = next;
      setBaseline(next);
      setFormState(next);
      qc.setQueryData(["agents", id], a);
    },
    [qc, id],
  );

  const saveM = useAction(() => http.put<Agent>(`/agents/${id}`, toPayload(form!, providers.data)), {
    success: "Agent saved",
    invalidate: [["agents"]],
    onSuccess: applySaved,
  });
  const dupM = useAction(() => http.post<Agent>(`/agents/${id}/duplicate`), {
    success: "Duplicated into your org",
    invalidate: [["agents"]],
    onSuccess: (a) => nav(`/agents/${a.id}`),
  });

  const ctx = useMemo<AgentWorkspaceCtx | null>(() => {
    if (!agent.data || !form) return null;
    const setForm = (fn: (f: AgentForm) => AgentForm) => setFormState((f) => (f ? fn(f) : f));
    return {
      id,
      agent: agent.data,
      form,
      setForm,
      set: (k, v) => setForm((f) => ({ ...f, [k]: v })),
      setSetting: (k: keyof AgentSettings, v: boolean) => setForm((f) => ({ ...f, settings: { ...f.settings, [k]: v } })),
      dirty,
      readOnly,
      saving: saveM.isPending,
      save: async () => (dirty && !readOnly && form.name.trim() ? saveM.mutateAsync() : undefined),
      discard: () => baseline && setFormState(baseline),
      leave: (to) => (dirty && !readOnly ? setPendingNav(to) : nav(to)),
      saveThen: (to) => {
        if (!dirty || readOnly) return nav(to);
        saveM.mutateAsync().then(() => nav(to), () => undefined);
      },
      duplicate: () => dupM.mutate(),
      duplicating: dupM.isPending,
    };
  }, [agent.data, form, baseline, dirty, readOnly, id, nav, saveM, dupM]);

  if (agent.isLoading || (agent.data && !form)) return <PageLoader />;
  if (!agent.data || !ctx || !form) {
    return (
      <Page>
        <EmptyState
          icon={<Bot className="size-5" />}
          title="Agent not found"
          description="It may have been deleted, or it belongs to another organization."
          action={
            <Link to="/agents">
              <Button variant="outline">Back to agents</Button>
            </Link>
          }
        />
      </Page>
    );
  }

  const a = agent.data;
  const base = `/agents/${id}`;
  const tabs = [
    { to: base, label: "Overview", icon: LayoutDashboard, end: true },
    { to: `${base}/profile`, label: "Profile", icon: UserRound },
    { to: `${base}/instructions`, label: "Instructions", icon: ScrollText },
    { to: `${base}/model`, label: "Model", icon: Cpu },
    { to: `${base}/tools`, label: "Tools", icon: Wrench, count: form.tool_ids.length + form.connection_ids.length || undefined },
    { to: `${base}/skills`, label: "Skills", icon: Sparkles, count: form.skill_ids.length || undefined },
    { to: `${base}/knowledge`, label: "Knowledge", icon: BookOpen },
    { to: `${base}/settings`, label: "Settings", icon: Settings2 },
  ];

  return (
    <AgentWorkspaceContext.Provider value={ctx}>
      <Page>
        <PageHeader
          back="/agents"
          icon={<AgentAvatar agent={{ avatar: form.avatar, color: form.color }} size="md" />}
          title={form.name || a.name || "Agent"}
          description={
            <span className="flex flex-wrap items-center gap-2">
              <ScopeBadge orgId={a.org_id} />
              <span className="font-mono text-xs">{modelLabel(a)}</span>
              {dirty && <span className="text-xs font-medium text-warning">Unsaved changes</span>}
            </span>
          }
          actions={
            <>
              <Button variant="outline" icon={<MessagesSquare className="size-4" />} onClick={() => ctx.leave(`/chat?agent=${id}`)}>
                Chat
              </Button>
              {can("member") && (
                <Button variant="outline" icon={<GraduationCap className="size-4" />} onClick={() => ctx.leave(`/training/${id}`)}>
                  Train
                </Button>
              )}
              {can("member") && (
                <Button icon={<Play className="size-4" />} onClick={() => ctx.leave(runAgentUrl(id))}>
                  Run
                </Button>
              )}
            </>
          }
        />
        {readOnly && a.org_id === null && can("member") && <GlobalNotice onDuplicate={ctx.duplicate} busy={ctx.duplicating} />}

        <RouteTabs tabs={tabs} className="mb-5" />

        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route index element={<Overview />} />
            <Route path="profile" element={<Profile />} />
            <Route path="instructions" element={<Instructions />} />
            <Route path="model" element={<ModelSection />} />
            <Route path="tools" element={<ToolsSection />} />
            <Route path="skills" element={<SkillsSection />} />
            <Route path="knowledge" element={<KnowledgeSection />} />
            <Route path="settings" element={<SettingsSection />} />
            <Route path="*" element={<Navigate to={base} replace />} />
          </Routes>
        </Suspense>

        {!readOnly && dirty && (
          <SaveBar>
            <span className="mr-auto hidden items-center text-sm text-muted sm:flex">You have unsaved changes</span>
            <Button variant="outline" onClick={ctx.discard}>
              Discard
            </Button>
            <Button icon={<Save className="size-4" />} loading={saveM.isPending} disabled={!form.name.trim()} onClick={() => saveM.mutate()}>
              Save agent
            </Button>
          </SaveBar>
        )}

        <ConfirmDialog
          open={!!pendingNav}
          onClose={() => setPendingNav(null)}
          onConfirm={() => {
            const to = pendingNav;
            setPendingNav(null);
            if (baseline) setFormState(baseline);
            if (to) nav(to);
          }}
          title="Leave without saving?"
          description="You have unsaved changes to this agent. They will be lost if you leave now."
          confirmLabel="Discard changes"
        />
      </Page>
    </AgentWorkspaceContext.Provider>
  );
}
