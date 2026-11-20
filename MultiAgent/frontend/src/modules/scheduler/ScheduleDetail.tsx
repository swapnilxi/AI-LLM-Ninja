/** /scheduler/:id (overview), /scheduler/:id/edit and /scheduler/:id/runs. */
import { useState } from "react";
import { Link, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { Activity, LayoutGrid, Pencil, Play, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { duration, errMsg, formatDate, timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, PageLoader, Stat, Switch } from "@/shared/ui/primitives";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { CopyButton } from "@/shared/ui/inputs";
import { IconTile } from "@/shared/ui/icons";
import { RouteTabs } from "@/shared/ui/RouteTabs";
import { RunStatusBadge } from "@/modules/runs/RunTimeline";
import { TARGET_META, TargetIcon } from "@/modules/runs/common";
import { useSchedule, useScheduleRuns, useUpcoming } from "./api";
import { describeSchedule, formatInTz, localTz, triggerMeta, useTargetNames } from "./lib";
import { ScheduleForm } from "./ScheduleForm";
import { SourceBadge, statusOf } from "./ScheduleList";
import type { Automation } from "./types";

function Overview({ a }: { a: Automation }) {
  const { can } = useAuth();
  const names = useTargetNames();
  const upcoming = useUpcoming(a.project_id, 30);
  const next = (upcoming.data ?? []).filter((u) => u.automation_id === a.id).slice(0, 5);
  const rotate = useAction(() => http.post<Automation>(`/schedules/${a.id}/rotate-token`), { success: "Webhook token rotated - update your integrations", invalidate: [["schedules"]] });
  const curl = a.webhook_url ? `curl -X POST '${a.webhook_url}' \\\n  -H 'Content-Type: application/json' \\\n  -d '{"task": "Summarise the latest tickets"}'` : "";
  const meta = TARGET_META[a.target_type];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Next run" value={a.enabled && a.next_run_at ? timeAgo(a.next_run_at) : "—"} hint={a.next_run_at ? formatInTz(a.next_run_at, localTz()) : undefined} />
        <Stat label="Last run" value={timeAgo(a.last_run_at)} hint={a.last_status || undefined} />
        <Stat label="Runs" value={a.run_count} />
        <Stat label="Created" value={timeAgo(a.created_at)} hint={a.source === "chat" ? "via chat" : a.source === "agent" ? "by an agent" : "with the form"} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="What runs" />
          <div className="space-y-3 p-4 text-sm sm:p-5">
            <Link to={`${meta.path}/${a.target_id}`} className="inline-flex items-center gap-2 font-medium hover:text-primary">
              <TargetIcon type={a.target_type} size="sm" /> {names[a.target_id] ?? a.target_id}
              <span className="text-xs font-normal text-muted">{meta.label}</span>
            </Link>
            {typeof a.input?.task === "string" && Object.keys(a.input).length === 1 ? (
              <p className="whitespace-pre-wrap rounded-lg bg-surface-2 px-3 py-2">{a.input.task || "No task text"}</p>
            ) : (
              <pre className="overflow-x-auto rounded-lg bg-surface-2 px-3 py-2 font-mono text-xs">{JSON.stringify(a.input, null, 2)}</pre>
            )}
            {a.description && <p className="text-xs text-muted">{a.description}</p>}
          </div>
        </Card>
        <Card>
          <CardHeader title="When" description={describeSchedule(a)} />
          <div className="p-4 sm:p-5">
            {a.trigger_type === "webhook" ? (
              a.webhook_url ? (
                <div className="space-y-3">
                  <Field label="Webhook URL" hint="Keep it secret: anyone with this URL can trigger the schedule. Requests are rate limited.">
                    <div className="flex gap-2">
                      <Input readOnly value={a.webhook_url} className="font-mono text-xs" onFocus={(e) => e.target.select()} />
                      <CopyButton text={a.webhook_url} />
                    </div>
                  </Field>
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs font-medium text-muted">
                      Example <CopyButton text={curl} className="size-7" />
                    </div>
                    <pre className="overflow-x-auto rounded-lg border border-border bg-surface-2/50 p-2.5 font-mono text-[11px] leading-relaxed">{curl}</pre>
                    <p className="mt-1 text-[11px] text-muted">Add <span className="font-mono">?wait=true</span> to wait up to 60s and get the output in the response.</p>
                  </div>
                  {can("member") && (
                    <Button variant="outline" size="sm" icon={<RefreshCw className="size-3.5" />} loading={rotate.isPending} onClick={() => rotate.mutate()}>
                      Rotate token
                    </Button>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted">Only members can see the webhook URL.</p>
              )
            ) : next.length ? (
              <ul className="space-y-1.5 text-sm">
                {next.map((u) => (
                  <li key={u.at} className="flex items-center justify-between gap-2">
                    <span>{formatInTz(u.at, localTz())}</span>
                    <span className="text-xs text-muted">{timeAgo(u.at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">{statusOf(a)?.label === "Completed" ? "This one-time schedule has already run." : a.enabled ? "No runs in the next 30 days." : "Paused: it will not run until you resume it."}</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Runs({ a }: { a: Automation }) {
  const runs = useScheduleRuns(a.id);
  if (runs.isLoading) return <PageLoader />;
  const items = runs.data?.items ?? [];
  if (!items.length) return <EmptyState icon={<Activity className="size-5" />} title="No runs yet" description="Runs started by this schedule (and Run now) show up here." />;
  return (
    <Card className="divide-y divide-border">
      {items.map((r) => (
        <Link key={r.id} to={`/runs/${r.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2/50">
          <RunStatusBadge status={r.status} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm">{r.output || r.error || r.target_name}</div>
            <div className="text-xs text-muted">{formatDate(r.created_at)} · {r.trigger} · {duration(r.started_at, r.finished_at)}</div>
          </div>
          <span className="text-xs tabular-nums text-muted">{r.total_tokens} tok</span>
        </Link>
      ))}
    </Card>
  );
}

export default function ScheduleDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const nav = useNavigate();
  const q = useSchedule(id);
  const [deleting, setDeleting] = useState(false);
  const toggle = useAction((a: Automation) => http.patch(`/schedules/${a.id}`, { enabled: !a.enabled }), { invalidate: [["schedules"]] });
  const del = useAction(() => http.del(`/schedules/${id}`), { success: "Schedule deleted", invalidate: [["schedules"]], onSuccess: () => nav("/scheduler") });
  const runNow = async () => {
    try {
      const r = await http.post<{ run_id: string }>(`/schedules/${id}/run`);
      toast.success("Run started", { action: { label: "View run", onClick: () => nav(`/runs/${r.run_id}`) } });
      q.refetch();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  if (q.isLoading) return <PageLoader />;
  const a = q.data;
  if (!a)
    return (
      <Page>
        <PageHeader back="/scheduler" title="Schedule not found" />
      </Page>
    );
  const trig = triggerMeta(a.trigger_type);
  const st = statusOf(a);
  const base = `/scheduler/${a.id}`;

  return (
    <Page>
      <PageHeader
        back="/scheduler"
        icon={<IconTile icon={trig.icon} color={trig.color} />}
        title={a.name}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            {describeSchedule(a)}
            {st && <Badge tone={st.tone}>{st.label}</Badge>}
            <SourceBadge source={a.source} />
          </span>
        }
        actions={
          can("member") && (
            <>
              <Switch checked={a.enabled} onChange={() => toggle.mutate(a)} label={a.enabled ? "Enabled" : "Paused"} />
              <Button variant="outline" icon={<Play className="size-4" />} onClick={runNow}>Run now</Button>
              <Button variant="ghost" size="icon" onClick={() => setDeleting(true)} aria-label="Delete">
                <Trash2 className="size-4 text-muted" />
              </Button>
            </>
          )
        }
      />
      <RouteTabs
        className="mb-5"
        tabs={[
          { to: base, label: "Overview", icon: LayoutGrid, end: true },
          ...(can("member") ? [{ to: `${base}/edit`, label: "Edit", icon: Pencil }] : []),
          { to: `${base}/runs`, label: "Runs", icon: Activity, count: a.run_count },
        ]}
      />
      <Routes>
        <Route index element={<Overview a={a} />} />
        <Route path="edit" element={<div className="mx-auto max-w-3xl"><ScheduleForm key={a.id} schedule={a} onSaved={() => nav(base)} onCancel={() => nav(base)} /></div>} />
        <Route path="runs" element={<Runs a={a} />} />
      </Routes>
      <ConfirmDialog open={deleting} onClose={() => setDeleting(false)} onConfirm={() => del.mutate()} loading={del.isPending} title={`Delete “${a.name}”?`} description="It stops triggering immediately (and its webhook URL stops working). Past runs are kept." />
    </Page>
  );
}
