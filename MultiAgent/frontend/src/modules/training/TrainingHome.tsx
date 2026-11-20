import { useState } from "react";
import { Link } from "react-router-dom";
import { Bot, Brain, FileText, FlaskConical, GraduationCap, Inbox, Lock, Upload } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { useAgents } from "@/modules/agents/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Card, EmptyState, PageLoader, Tabs } from "@/shared/ui/primitives";
import { SearchInput } from "@/shared/ui/inputs";
import { AgentAvatar } from "@/shared/ui/icons";
import { ScopeBadge } from "@/shared/components/library";
import { useTrainingGrid } from "./api";
import { canTrain } from "./parts";

const STEPS = [
  { icon: Upload, title: "Ingest", text: "Upload files, paste text or import pages the agent should know." },
  { icon: GraduationCap, title: "Teach", text: "Add rules, facts, Q&A examples and corrections in plain language." },
  { icon: FlaskConical, title: "Test", text: "Search the knowledge exactly as the agent would and check the results." },
];

/** /training: choose the agent to train. */
export default function TrainingHome() {
  const agents = useAgents();
  const grid = useTrainingGrid();
  const { user, can } = useAuth();
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"all" | "org" | "global">("all");
  const items = (agents.data ?? []).filter(
    (a) =>
      (scope === "all" || (scope === "global" ? a.org_id === null : a.org_id !== null)) &&
      (!q || `${a.name} ${a.description} ${a.tags.join(" ")}`.toLowerCase().includes(q.toLowerCase())),
  );

  return (
    <Page>
      <PageHeader title="Training" description="Teach your agents and give them knowledge. Pick an agent to ingest documents, add lessons, review what it learned and test retrieval." />

      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        {STEPS.map((s, i) => (
          <div key={s.title} className="relative overflow-hidden rounded-xl border border-border bg-surface p-4">
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary-soft/70 via-transparent to-transparent" />
            <div className="relative flex items-start gap-3">
              <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/15 to-violet-500/10 text-primary ring-1 ring-inset ring-indigo-500/15">
                <s.icon className="size-4" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold"><span className="mr-1.5 text-muted tabular-nums">{i + 1}.</span>{s.title}</div>
                <p className="mt-0.5 text-xs text-muted">{s.text}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={[
            { key: "all", label: "All", count: agents.data?.length },
            { key: "org", label: "My org" },
            { key: "global", label: "Global library" },
          ]}
          value={scope}
          onChange={setScope}
        />
        <SearchInput value={q} onChange={setQ} placeholder="Search agents…" className="sm:w-64" />
      </div>

      {agents.isLoading ? (
        <PageLoader />
      ) : !items.length ? (
        <EmptyState icon={<Bot className="size-5" />} title="No agents found" description="Create an agent first, then come back to train it." />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((a) => {
            const s = grid.data?.[a.id];
            const locked = !canTrain(a, user, can("member"));
            return (
              <Link key={a.id} to={`/training/${a.id}`} className="group block">
                <Card className="flex h-full flex-col p-4 transition-all group-hover:-translate-y-0.5 group-hover:border-indigo-500/30 group-hover:shadow-lg group-hover:shadow-indigo-500/5">
                  <div className="flex items-start gap-3">
                    <AgentAvatar agent={a} />
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate text-sm font-semibold">{a.name}</h3>
                      <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                        <ScopeBadge orgId={a.org_id} />
                        {locked && <Badge tone="muted" icon={<Lock className="size-2.5" />}>Read-only</Badge>}
                        {a.settings?.auto_learn && <Badge tone="success">Auto-learn</Badge>}
                      </div>
                    </div>
                    {!!s?.pending && <Badge tone="warning" icon={<Inbox className="size-2.5" />}>{s.pending} to review</Badge>}
                  </div>
                  {a.description && <p className="mt-3 line-clamp-2 text-sm text-muted">{a.description}</p>}
                  <div className="min-h-4 flex-1" />
                  <div className="grid grid-cols-3 gap-2 border-t border-border pt-3 text-xs">
                    <Metric icon={FileText} value={s?.documents ?? 0} label="docs" />
                    <Metric icon={GraduationCap} value={s?.approved ?? 0} label="lessons" />
                    <Metric icon={Brain} value={s?.memories ?? 0} label="memories" />
                  </div>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </Page>
  );
}

function Metric({ icon: Icon, value, label }: { icon: typeof FileText; value: number; label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-muted">
      <Icon className="size-3.5 shrink-0" />
      <span className="font-semibold tabular-nums text-fg">{value}</span>
      <span className="truncate">{label}</span>
    </div>
  );
}
