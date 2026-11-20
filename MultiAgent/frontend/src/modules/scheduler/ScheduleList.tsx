import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bot, CalendarClock, MessageSquareText, Play, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { errMsg, timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { Badge, Button, Card, EmptyState, PageLoader, Switch } from "@/shared/ui/primitives";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { IconTile } from "@/shared/ui/icons";
import { RunStatusBadge } from "@/modules/runs/RunTimeline";
import { TargetIcon } from "@/modules/runs/common";
import { useSchedules } from "./api";
import { describeSchedule, triggerMeta, useTargetNames } from "./lib";
import type { Automation } from "./types";

export function SourceBadge({ source }: { source: string }) {
  if (source === "chat") return <Badge tone="primary" icon={<MessageSquareText className="size-3" />}>via chat</Badge>;
  if (source === "agent") return <Badge tone="muted" icon={<Bot className="size-3" />}>by an agent</Badge>;
  return null;
}

export function statusOf(a: Automation): { label: string; tone: "muted" | "success" | "warning" } | null {
  if (a.trigger_type === "once" && a.run_count > 0 && !a.next_run_at) return { label: "Completed", tone: "success" };
  if (!a.enabled) return { label: "Paused", tone: "muted" };
  return null;
}

export default function ScheduleList() {
  const { projectId, can } = useAuth();
  const list = useSchedules(projectId);
  const names = useTargetNames();
  const nav = useNavigate();
  const [deleting, setDeleting] = useState<Automation | null>(null);

  const toggle = useAction((a: Automation) => http.patch(`/schedules/${a.id}`, { enabled: !a.enabled }), { invalidate: [["schedules"]] });
  const del = useAction((a: Automation) => http.del(`/schedules/${a.id}`), { success: "Schedule deleted", invalidate: [["schedules"]], onSuccess: () => setDeleting(null) });
  const runNow = async (a: Automation) => {
    try {
      const r = await http.post<{ run_id: string }>(`/schedules/${a.id}/run`);
      toast.success(`Started “${a.name}”`, { action: { label: "View run", onClick: () => nav(`/runs/${r.run_id}`) } });
      list.refetch();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  if (list.isLoading) return <PageLoader />;
  const items = list.data ?? [];
  if (!items.length)
    return (
      <EmptyState
        icon={<CalendarClock className="size-5" />}
        title="Nothing scheduled in this project"
        description="Try “every weekday at 9am summarise my GitHub PRs” or “tomorrow at 3pm remind me to send the invoice”."
        action={
          can("member") && (
            <div className="flex flex-wrap justify-center gap-2">
              <Button icon={<MessageSquareText className="size-4" />} onClick={() => nav("/scheduler/new/chat")}>Schedule by chat</Button>
              <Button variant="outline" onClick={() => nav("/scheduler/new/form")}>Use the form</Button>
            </div>
          )
        }
      />
    );

  return (
    <div className="space-y-3">
      {items.map((a) => {
        const trig = triggerMeta(a.trigger_type);
        const st = statusOf(a);
        return (
          <Card key={a.id} className="p-4 transition-colors hover:border-primary/30">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <Link to={`/scheduler/${a.id}`} className="flex min-w-0 flex-1 items-start gap-3">
                <IconTile icon={trig.icon} color={trig.color} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate text-sm font-semibold">{a.name}</h3>
                    {st && <Badge tone={st.tone}>{st.label}</Badge>}
                    <SourceBadge source={a.source} />
                    {a.last_status && (a.last_status.startsWith("skipped") ? <Badge tone="warning">{a.last_status}</Badge> : <RunStatusBadge status={a.last_status} />)}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                    <span className="inline-flex items-center gap-1.5">
                      <TargetIcon type={a.target_type} size="xs" />
                      <span className="font-medium text-fg">{names[a.target_id] ?? a.target_id}</span>
                    </span>
                    <span>·</span>
                    <span>{describeSchedule(a)}</span>
                  </div>
                  {typeof a.input?.task === "string" && a.input.task && <p className="mt-1.5 line-clamp-1 text-xs text-muted">{a.input.task}</p>}
                </div>
              </Link>
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
                  <Button variant="ghost" size="icon" onClick={() => setDeleting(a)} aria-label="Delete">
                    <Trash2 className="size-4 text-muted" />
                  </Button>
                </div>
              )}
            </div>
          </Card>
        );
      })}
      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} onConfirm={() => deleting && del.mutate(deleting)} loading={del.isPending} title={`Delete “${deleting?.name}”?`} description="It stops triggering immediately (and its webhook URL stops working). Past runs are kept." />
    </div>
  );
}
