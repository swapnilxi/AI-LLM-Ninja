import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Bot,
  Brain,
  CircleCheck,
  Coins,
  FileText,
  FolderKanban,
  LoaderCircle,
  MessagesSquare,
  Plug,
  Sparkles,
  Timer,
  TriangleAlert,
  Users,
  Workflow as WorkflowIcon,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { http, qs } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Run } from "@/modules/runs/types";
import type { TargetType } from "@/shared/lib/types";
import { cn, formatNumber, timeAgo } from "@/shared/lib/utils";
import { useProviders } from "@/modules/settings/api";
import { Page } from "@/shared/layout/PageHeader";
import { Card, CardHeader, EmptyState, PageLoader, Stat } from "@/shared/ui/primitives";
import { IconTile } from "@/shared/ui/icons";
import { RunStatusBadge } from "@/modules/runs/RunTimeline";
import { RunsChart, type DayPoint } from "./RunsChart";

interface DashboardData {
  counts: Record<"agents" | "teams" | "workflows" | "skills" | "tools" | "projects" | "connections" | "automations_active" | "documents" | "memories" | "running", number>;
  week: { runs: number; success_rate: number | null; tokens: number };
  tokens_today: number;
  daily_token_limit: number;
  series: DayPoint[];
  top_targets: { target_type: TargetType; target_id: string; name: string; runs: number }[];
  recent_runs: Run[];
}

const TARGET_ICON: Record<string, LucideIcon> = { agent: Bot, team: Users, workflow: WorkflowIcon };
const TARGET_COLOR: Record<string, string> = { agent: "indigo", team: "violet", workflow: "teal" };
const targetLink = (t: string, id: string) => (t === "agent" ? `/agents/${id}` : t === "team" ? `/teams/${id}` : `/workflows/${id}`);

function greeting() {
  const h = new Date().getHours();
  return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

function TokenMeter({ used, limit }: { used: number; limit: number }) {
  if (!limit) return <div className="mt-2 text-xs text-muted">No daily limit</div>;
  const pct = Math.min(100, (used / limit) * 100);
  const tone = pct >= 90 ? "bg-[#d03b3b] dark:bg-[#e66767]" : pct >= 70 ? "bg-[#fab219]" : "bg-[#2a78d6] dark:bg-[#3987e5]";
  return (
    <div className="mt-2">
      <div className="h-1.5 overflow-hidden rounded-full bg-[#cde2fb] dark:bg-[#184f95]/50" role="meter" aria-valuemin={0} aria-valuemax={limit} aria-valuenow={used} aria-label="Daily token budget used">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${Math.max(pct, used > 0 ? 2 : 0)}%` }} />
      </div>
      <div className="mt-1 text-xs text-muted">
        {Math.round(pct)}% of {formatNumber(limit)} daily budget
      </div>
    </div>
  );
}

function QuickAction({ to, icon, title, text, color }: { to: string; icon: LucideIcon; title: string; text: string; color: string }) {
  return (
    <Link to={to} className="group flex items-center gap-3 rounded-xl border border-border bg-surface p-3 transition-all hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-md hover:shadow-indigo-500/5">
      <IconTile icon={icon} color={color} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{title}</div>
        <div className="truncate text-xs text-muted">{text}</div>
      </div>
      <ArrowRight className="size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

function CountLink({ to, icon: Icon, label, value }: { to: string; icon: LucideIcon; label: string; value: number }) {
  return (
    <Link to={to} className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 hover:bg-surface-2">
      <Icon className="size-4 text-muted" />
      <span className="flex-1 text-sm">{label}</span>
      <span className="text-sm font-semibold tabular-nums">{formatNumber(value)}</span>
    </Link>
  );
}

function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { key: T; label: ReactNode }[] }) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={cn("cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium transition-colors", value === o.key ? "bg-primary-soft text-primary" : "text-muted hover:text-fg")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { user, org, project, projectId } = useAuth();
  const providers = useProviders();
  const [scope, setScope] = useState<"project" | "all">("project");
  const pid = scope === "project" ? projectId ?? undefined : undefined;
  const dash = useQuery({
    queryKey: ["dashboard", scope, pid],
    queryFn: () => http.get<DashboardData>(`/dashboard${qs({ project_id: pid })}`),
    refetchInterval: 20_000,
    placeholderData: (prev) => prev,
    enabled: scope === "all" || !!projectId,
  });
  const d = dash.data;
  const usingMock = providers.data?.default.provider === "mock";
  const firstName = user?.name?.split(" ")[0] ?? "";
  const maxTop = Math.max(1, ...(d?.top_targets ?? []).map((t) => t.runs));

  return (
    <Page>
      <div className="relative mb-6 overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-primary-soft via-surface to-surface p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-16 -top-20 size-64 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm text-muted">{org?.name}</p>
            <h1 className="mt-0.5 text-2xl font-semibold tracking-tight sm:text-[28px]">
              {greeting()}, <span className="text-brand">{firstName}</span>
            </h1>
            <p className="mt-1 text-sm text-muted">
              {project ? (
                <>
                  Working in <span className="font-medium text-fg">{project.name}</span> — every run inherits its brief, documents, memory and policies.
                </>
              ) : (
                "Select a project to get started."
              )}
            </p>
          </div>
          <Segmented
            value={scope}
            onChange={setScope}
            options={[
              { key: "project", label: "This project" },
              { key: "all", label: "All projects" },
            ]}
          />
        </div>
      </div>

      {usingMock && (
        <Link
          to="/settings/models"
          className="mb-5 flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3.5 text-sm transition-colors hover:bg-amber-500/10"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" />
          <div className="flex-1">
            <span className="font-medium">Using the offline mock model</span>
            <span className="text-muted"> — add an API key in Settings → Models to get real answers.</span>
          </div>
          <ArrowRight className="mt-0.5 size-4 shrink-0 text-muted" />
        </Link>
      )}

      {!d && dash.isLoading ? (
        <PageLoader />
      ) : !d ? (
        <EmptyState icon={<Activity className="size-5" />} title="Dashboard unavailable" description="Could not load dashboard data." />
      ) : (
        <div className={cn("space-y-5 transition-opacity", dash.isFetching && dash.isPlaceholderData && "opacity-60")}>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Runs this week" value={formatNumber(d.week.runs)} icon={<Activity className="size-4" />} hint={`${formatNumber(d.week.tokens)} tokens`} />
            <Stat
              label="Success rate"
              value={d.week.success_rate === null ? "—" : `${d.week.success_rate}%`}
              icon={<CircleCheck className="size-4" />}
              hint="Finished runs, last 7 days"
            />
            <Card className="relative col-span-2 overflow-hidden p-4 lg:col-span-1">
              <div className="pointer-events-none absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-primary-soft/70 to-transparent" />
              <div className="relative flex items-center justify-between text-xs font-medium text-muted">
                Tokens today
                <Coins className="size-4" />
              </div>
              <div className="relative mt-2 text-2xl font-semibold tracking-tight">{formatNumber(d.tokens_today)}</div>
              <div className="relative">
                <TokenMeter used={d.tokens_today} limit={d.daily_token_limit} />
              </div>
            </Card>
            <Stat label="Active schedules" value={d.counts.automations_active} icon={<Timer className="size-4" />} hint={<Link to="/scheduler" className="hover:text-fg">Manage →</Link>} />
            <Stat
              label="Running now"
              value={
                <span className="inline-flex items-center gap-2">
                  {d.counts.running}
                  {d.counts.running > 0 && <LoaderCircle className="size-4 animate-spin text-primary" />}
                </span>
              }
              icon={<LoaderCircle className="size-4" />}
              hint={<Link to="/runs" className="hover:text-fg">View runs →</Link>}
            />
          </div>

          <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
            <Card>
              <CardHeader title="Runs per day" description="Last 14 days, by outcome" />
              <div className="p-4 sm:p-5">
                <RunsChart data={d.series} />
              </div>
            </Card>
            <Card>
              <CardHeader title="Quick actions" />
              <div className="space-y-2 p-3">
                <QuickAction to="/agents/new" icon={Bot} color="indigo" title="New agent" text="Model, skills, tools and knowledge" />
                <QuickAction to="/workflows/new" icon={WorkflowIcon} color="teal" title="Build a workflow" text="Visual DAG with branches" />
                <QuickAction to="/chat" icon={MessagesSquare} color="violet" title="Open chat" text="Talk to any agent or team" />
                <QuickAction to="/connectors" icon={Plug} color="emerald" title="Connect an app" text="GitHub, Slack, Notion, MCP…" />
              </div>
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
            <Card>
              <CardHeader title="Recent runs" actions={<Link to="/runs" className="text-xs font-medium text-muted hover:text-fg">View all</Link>} />
              {d.recent_runs.length === 0 ? (
                <EmptyState icon={<Activity className="size-5" />} title="No runs yet" description="Run an agent, team or workflow and it will show up here." className="m-4 border-0" />
              ) : (
                <ul className="divide-y divide-border">
                  {d.recent_runs.map((r) => (
                    <li key={r.id}>
                      <Link to={`/runs/${r.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2/60">
                        <IconTile icon={TARGET_ICON[r.target_type] ?? Bot} color={TARGET_COLOR[r.target_type]} size="sm" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-medium">{r.target_name || r.target_type}</div>
                          <div className="truncate text-xs text-muted">
                            <span className="capitalize">{r.target_type}</span> · {r.trigger} · {timeAgo(r.created_at)}
                            {r.total_tokens > 0 && <> · {formatNumber(r.total_tokens)} tok</>}
                          </div>
                        </div>
                        <RunStatusBadge status={r.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <div className="space-y-5">
              <Card>
                <CardHeader title="Most active" description="Agents, teams & workflows · 14 days" />
                {d.top_targets.length === 0 ? (
                  <p className="px-4 py-6 text-center text-xs text-muted">Nothing yet</p>
                ) : (
                  <ul className="space-y-3 p-4">
                    {d.top_targets.map((t) => (
                      <li key={`${t.target_type}-${t.target_id}`}>
                        <Link to={targetLink(t.target_type, t.target_id)} className="group block">
                          <div className="flex items-center justify-between gap-2 text-sm">
                            <span className="flex min-w-0 items-center gap-2">
                              <IconTile icon={TARGET_ICON[t.target_type] ?? Bot} color={TARGET_COLOR[t.target_type]} size="xs" />
                              <span className="truncate group-hover:underline">{t.name}</span>
                            </span>
                            <span className="font-semibold tabular-nums">{t.runs}</span>
                          </div>
                          <div className="mt-1.5 h-1.5 rounded-full bg-surface-2">
                            <div className="h-full rounded-full bg-[#2a78d6] dark:bg-[#3987e5]" style={{ width: `${(t.runs / maxTop) * 100}%` }} />
                          </div>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card>
                <CardHeader title="Library" />
                <div className="p-1.5">
                  <CountLink to="/agents" icon={Bot} label="Agents" value={d.counts.agents} />
                  <CountLink to="/teams" icon={Users} label="Teams" value={d.counts.teams} />
                  <CountLink to="/workflows" icon={WorkflowIcon} label="Workflows" value={d.counts.workflows} />
                  <CountLink to="/skills" icon={Sparkles} label="Skills" value={d.counts.skills} />
                  <CountLink to="/tools" icon={Wrench} label="Tools" value={d.counts.tools} />
                  <CountLink to="/connectors" icon={Plug} label="Connections" value={d.counts.connections} />
                  <CountLink to="/projects" icon={FolderKanban} label="Projects" value={d.counts.projects} />
                  <CountLink to={projectId ? `/projects/${projectId}` : "/projects"} icon={FileText} label="Documents" value={d.counts.documents} />
                  <CountLink to={projectId ? `/projects/${projectId}` : "/projects"} icon={Brain} label="Memories" value={d.counts.memories} />
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}
    </Page>
  );
}
