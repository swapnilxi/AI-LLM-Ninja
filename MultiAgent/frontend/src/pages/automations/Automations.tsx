import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Pencil, Play, Plus, Timer, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Automation } from "@/lib/types";
import { errMsg, timeAgo } from "@/lib/utils";
import { useAction, useAgents, useAutomations, useTeams, useWorkflows } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, Card, EmptyState, PageLoader, Switch } from "@/components/ui/primitives";
import { ConfirmDialog } from "@/components/ui/overlay";
import { IconTile } from "@/components/ui/icons";
import { RunStatusBadge } from "@/components/run/RunTimeline";
import { TargetIcon } from "../runs/common";
import { AutomationDialog, TRIGGERS } from "./AutomationDialog";

const TRIGGER_COLORS: Record<string, string> = { manual: "slate", schedule: "violet", interval: "sky", webhook: "emerald" };

function describeTrigger(a: Automation): string {
  if (a.trigger_type === "schedule") return `Cron ${a.cron} · ${a.timezone}`;
  if (a.trigger_type === "interval") return `Every ${a.interval_minutes} min`;
  if (a.trigger_type === "webhook") return "On webhook POST";
  return "Manual / API";
}

export default function Automations() {
  const { projectId, project, can } = useAuth();
  const autos = useAutomations(projectId);
  const agents = useAgents();
  const teams = useTeams();
  const workflows = useWorkflows();
  const nav = useNavigate();
  const [editing, setEditing] = useState<Automation | null>(null);
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState<Automation | null>(null);
  const names = useMemo(() => {
    const m: Record<string, string> = {};
    for (const a of agents.data ?? []) m[a.id] = a.name;
    for (const t of teams.data ?? []) m[t.id] = t.name;
    for (const w of workflows.data ?? []) m[w.id] = w.name;
    return m;
  }, [agents.data, teams.data, workflows.data]);

  const toggle = useAction((a: Automation) => http.patch(`/automations/${a.id}`, { enabled: !a.enabled }), { invalidate: [["automations"]] });
  const del = useAction((a: Automation) => http.del(`/automations/${a.id}`), { success: "Automation deleted", invalidate: [["automations"]], onSuccess: () => setDeleting(null) });
  const runNow = async (a: Automation) => {
    try {
      const r = await http.post<{ run_id: string }>(`/automations/${a.id}/run`);
      toast.success(`Started “${a.name}”`, { action: { label: "View run", onClick: () => nav(`/runs/${r.run_id}`) } });
      autos.refetch();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  const edit = (a: Automation | null) => {
    setEditing(a);
    setOpen(true);
  };

  const items = autos.data ?? [];

  return (
    <Page>
      <PageHeader
        title="Automations"
        description={`Run agents, teams and workflows on a schedule, at an interval or from webhooks${project ? ` in “${project.name}”` : ""}.`}
        actions={can("member") && <Button icon={<Plus className="size-4" />} onClick={() => edit(null)} disabled={!projectId}>New automation</Button>}
      />
      {autos.isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Timer className="size-5" />}
          title="No automations in this project"
          description="Schedule a daily research brief, poll an API every hour or trigger a workflow from another app."
          action={can("member") && <Button onClick={() => edit(null)}>Create automation</Button>}
        />
      ) : (
        <div className="space-y-3">
          {items.map((a) => {
            const trig = TRIGGERS.find((t) => t.key === a.trigger_type) ?? TRIGGERS[0];
            return (
              <Card key={a.id} className="p-4">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                  <div className="flex min-w-0 flex-1 items-start gap-3">
                    <IconTile icon={trig.icon} color={TRIGGER_COLORS[a.trigger_type]} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="truncate text-sm font-semibold">{a.name}</h3>
                        {!a.enabled && <Badge tone="muted">Paused</Badge>}
                        {a.last_status && (a.last_status.startsWith("skipped") ? <Badge tone="warning">{a.last_status}</Badge> : <RunStatusBadge status={a.last_status} />)}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                        <span className="inline-flex items-center gap-1.5">
                          <TargetIcon type={a.target_type} size="xs" />
                          <span className="font-medium text-fg">{names[a.target_id] ?? a.target_id}</span>
                        </span>
                        <span>·</span>
                        <span className="font-mono">{describeTrigger(a)}</span>
                      </div>
                      {a.description && <p className="mt-1.5 line-clamp-1 text-xs text-muted">{a.description}</p>}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-xs sm:w-72">
                    <div>
                      <div className="text-muted">Next run</div>
                      <div className="font-medium">{a.enabled && a.next_run_at ? timeAgo(a.next_run_at) : "—"}</div>
                    </div>
                    <div>
                      <div className="text-muted">Last run</div>
                      <div className="font-medium">{timeAgo(a.last_run_at)}</div>
                    </div>
                    <div>
                      <div className="text-muted">Runs</div>
                      <div className="font-medium tabular-nums">{a.run_count}</div>
                    </div>
                  </div>
                  {can("member") && (
                    <div className="flex items-center gap-1 border-t border-border pt-3 sm:border-0 sm:pt-0">
                      <Switch checked={a.enabled} onChange={() => toggle.mutate(a)} />
                      <div className="flex-1 sm:hidden" />
                      <Button variant="outline" size="sm" icon={<Play className="size-3.5" />} onClick={() => runNow(a)} className="ml-2">
                        Run now
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => edit(a)} aria-label="Edit">
                        <Pencil className="size-4 text-muted" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => setDeleting(a)} aria-label="Delete">
                        <Trash2 className="size-4 text-muted" />
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
      <AutomationDialog open={open} onClose={() => setOpen(false)} automation={editing} onCreated={() => autos.refetch()} />
      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} onConfirm={() => deleting && del.mutate(deleting)} loading={del.isPending} title={`Delete “${deleting?.name}”?`} description="Its schedule and webhook URL stop working immediately. Past runs are kept." />
    </Page>
  );
}
