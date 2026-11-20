/** Agenda of every run the enabled schedules will start, grouped by day. Range in the URL: ?days=1|7|30. */
import { Link, useSearchParams } from "react-router-dom";
import { CalendarDays } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { cn } from "@/shared/lib/utils";
import { Card, EmptyState, PageLoader } from "@/shared/ui/primitives";
import { IconTile } from "@/shared/ui/icons";
import { TargetIcon } from "@/modules/runs/common";
import { useUpcoming } from "./api";
import { triggerMeta, useTargetNames } from "./lib";
import type { UpcomingRun } from "./types";

const RANGES = [1, 7, 30];

function dayLabel(d: Date): string {
  const today = new Date();
  const tomorrow = new Date(Date.now() + 86_400_000);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === tomorrow.toDateString()) return "Tomorrow";
  return d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
}

export default function Upcoming() {
  const { projectId } = useAuth();
  const [params, setParams] = useSearchParams();
  const days = RANGES.includes(Number(params.get("days"))) ? Number(params.get("days")) : 7;
  const upcoming = useUpcoming(projectId, days);
  const names = useTargetNames();

  const groups: { label: string; items: UpcomingRun[] }[] = [];
  for (const u of upcoming.data ?? []) {
    const label = dayLabel(new Date(u.at));
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(u);
    else groups.push({ label, items: [u] });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted">Times are shown in your browser's timezone.</p>
        <div className="flex gap-1 rounded-lg border border-border bg-surface-2/60 p-0.5">
          {RANGES.map((d) => (
            <button
              key={d}
              onClick={() => setParams({ days: String(d) }, { replace: true })}
              className={cn("cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium", d === days ? "bg-surface text-fg shadow-sm" : "text-muted hover:text-fg")}
            >
              {d === 1 ? "24 hours" : `${d} days`}
            </button>
          ))}
        </div>
      </div>
      {upcoming.isLoading ? (
        <PageLoader />
      ) : !groups.length ? (
        <EmptyState icon={<CalendarDays className="size-5" />} title="Nothing coming up" description={`No enabled schedule runs in the next ${days === 1 ? "24 hours" : `${days} days`}.`} />
      ) : (
        groups.map((g) => (
          <div key={g.label}>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{g.label}</h3>
            <Card className="divide-y divide-border">
              {g.items.map((u) => {
                const trig = triggerMeta(u.trigger_type);
                return (
                  <Link key={`${u.automation_id}-${u.at}`} to={`/scheduler/${u.automation_id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2/50">
                    <div className="w-14 shrink-0 text-sm font-semibold tabular-nums">{new Date(u.at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</div>
                    <IconTile icon={trig.icon} color={trig.color} size="xs" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{u.name}</div>
                    </div>
                    <span className="hidden items-center gap-1.5 text-xs text-muted sm:inline-flex">
                      <TargetIcon type={u.target_type} size="xs" /> {names[u.target_id] ?? u.target_id}
                    </span>
                  </Link>
                );
              })}
            </Card>
          </div>
        ))
      )}
    </div>
  );
}
