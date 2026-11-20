import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useAuth } from "@/lib/auth";
import type { Run } from "@/lib/types";
import { duration, formatNumber, timeAgo } from "@/lib/utils";
import { useRuns } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, Card, Checkbox, EmptyState, PageLoader, Select } from "@/components/ui/primitives";
import { RunStatusBadge } from "@/components/run/RunTimeline";
import { STATUSES, TARGET_META, TargetIcon, TRIGGERS } from "./common";

const PAGE = 25;

export default function RunsList() {
  const { projectId, project } = useAuth();
  const nav = useNavigate();
  const [status, setStatus] = useState("");
  const [targetType, setTargetType] = useState("");
  const [trigger, setTrigger] = useState("");
  const [onlyProject, setOnlyProject] = useState(false);
  const [offset, setOffset] = useState(0);
  const [live, setLive] = useState(false);

  const params = {
    status: status || undefined,
    target_type: targetType || undefined,
    trigger: trigger || undefined,
    project_id: onlyProject ? projectId ?? undefined : undefined,
    limit: PAGE,
    offset,
  };
  const runs = useRuns(params, { refetchInterval: live ? 3000 : undefined });
  const items = runs.data?.items ?? [];
  const total = runs.data?.total ?? 0;

  useEffect(() => {
    setLive(items.some((r) => r.status === "queued" || r.status === "running"));
  }, [items]);
  useEffect(() => setOffset(0), [status, targetType, trigger, onlyProject]);

  return (
    <Page>
      <PageHeader
        title="Runs"
        description="Every execution of an agent, team or workflow - from chat, the API, schedules or webhooks - with a full trace."
        actions={
          <Button variant="outline" icon={<RefreshCw className={live ? "size-4 animate-spin [animation-duration:2.5s]" : "size-4"} />} onClick={() => runs.refetch()}>
            {live ? "Live" : "Refresh"}
          </Button>
        }
      />
      <Card className="mb-4 flex flex-col gap-3 p-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="grid grid-cols-3 gap-2 sm:flex">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="sm:w-40" aria-label="Status">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s} className="capitalize">{s}</option>)}
          </Select>
          <Select value={targetType} onChange={(e) => setTargetType(e.target.value)} className="sm:w-36" aria-label="Type">
            <option value="">All types</option>
            <option value="agent">Agents</option>
            <option value="team">Teams</option>
            <option value="workflow">Workflows</option>
          </Select>
          <Select value={trigger} onChange={(e) => setTrigger(e.target.value)} className="sm:w-36" aria-label="Trigger">
            <option value="">All triggers</option>
            {TRIGGERS.map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
        </div>
        <Checkbox checked={onlyProject} onChange={setOnlyProject} label={<span className="truncate">Only {project ? `“${project.name}”` : "active project"}</span>} className="sm:ml-auto" />
      </Card>

      {runs.isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <EmptyState icon={<Activity className="size-5" />} title="No runs yet" description="Run an agent, team or workflow, chat with a bot or set up an automation." />
      ) : (
        <>
          {/* desktop table */}
          <Card className="hidden overflow-hidden md:block">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-surface-2/50 text-left text-xs text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Target</th>
                  <th className="px-4 py-2.5 font-medium">Trigger</th>
                  <th className="px-4 py-2.5 font-medium">Started</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 text-right font-medium">Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((r) => (
                  <tr key={r.id} onClick={() => nav(`/runs/${r.id}`)} className="cursor-pointer transition-colors hover:bg-surface-2/50">
                    <td className="px-4 py-2.5"><RunStatusBadge status={r.status} /></td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2.5">
                        <TargetIcon type={r.target_type} size="xs" />
                        <div className="min-w-0">
                          <Link to={`/runs/${r.id}`} className="block truncate font-medium hover:underline" onClick={(e) => e.stopPropagation()}>{r.target_name || r.target_id}</Link>
                          <div className="truncate text-xs text-muted">{r.error ? <span className="text-danger">{r.error}</span> : r.output.replace(/[#*_`>]/g, "").slice(0, 80) || TARGET_META[r.target_type]?.label}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2.5"><Badge tone="muted">{r.trigger}</Badge></td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-muted">{timeAgo(r.created_at)}</td>
                    <td className="whitespace-nowrap px-4 py-2.5 tabular-nums text-muted">{duration(r.started_at, r.finished_at)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-muted">{formatNumber(r.total_tokens)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          {/* mobile cards */}
          <div className="space-y-2 md:hidden">
            {items.map((r: Run) => (
              <Link key={r.id} to={`/runs/${r.id}`} className="block">
                <Card className="p-3 transition-colors active:bg-surface-2">
                  <div className="flex items-center gap-2.5">
                    <TargetIcon type={r.target_type} size="sm" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{r.target_name || r.target_id}</div>
                      <div className="text-xs text-muted">{r.trigger} · {timeAgo(r.created_at)} · {duration(r.started_at, r.finished_at)}</div>
                    </div>
                    <RunStatusBadge status={r.status} />
                  </div>
                  {(r.error || r.output) && <p className="mt-2 line-clamp-2 text-xs text-muted">{r.error || r.output.replace(/[#*_`>]/g, "")}</p>}
                </Card>
              </Link>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between text-sm text-muted">
            <span>
              {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" icon={<ChevronLeft className="size-3.5" />} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                Prev
              </Button>
              <Button variant="outline" size="sm" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
                Next <ChevronRight className="size-3.5" />
              </Button>
            </div>
          </div>
        </>
      )}
    </Page>
  );
}
