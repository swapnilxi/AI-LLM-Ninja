import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CircleX, Clock, Coins, Cpu, MessagesSquare, RotateCcw, Square, Timer, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Run } from "@/modules/runs/types";
import { duration, formatDate, formatNumber } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useRunStream } from "@/modules/runs/useRunStream";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, CardHeader, EmptyState, PageLoader } from "@/shared/ui/primitives";
import { CopyButton } from "@/shared/ui/inputs";
import { Markdown } from "@/shared/ui/Markdown";
import { RunStatusBadge, RunTimeline } from "@/modules/runs/RunTimeline";
import { TARGET_META, TargetIcon } from "./common";

function Meta({ icon, label, value }: { icon: ReactNode; label: string; value: ReactNode }) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-border bg-surface px-3 py-2.5">
      <span className="text-muted">{icon}</span>
      <div className="min-w-0">
        <div className="text-[11px] text-muted">{label}</div>
        <div className="truncate text-sm font-medium tabular-nums">{value}</div>
      </div>
    </div>
  );
}

export default function RunDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const runQ = useQuery({ queryKey: ["run", id], queryFn: () => http.get<Run>(`/runs/${id}`), enabled: !!id });
  const stream = useRunStream(id);
  const cancel = useAction(() => http.post(`/runs/${id}/cancel`), { success: "Cancellation requested", invalidate: [["run", id!]] });
  const navigate = useNavigate();
  const rerun = useAction(() => http.post<Run>(`/runs/${id}/rerun`), { success: "Started a new run", invalidate: [["runs"]], onSuccess: (r) => navigate(`/runs/${r.id}`) });

  if (runQ.isLoading) return <PageLoader />;
  const run = runQ.data;
  if (!run) return <Page><EmptyState icon={<CircleX className="size-5" />} title="Run not found" description="It may belong to another organization." /></Page>;

  const status = stream.status && !["queued"].includes(stream.status) ? stream.status : run.status;
  const finished = !["queued", "running"].includes(status);
  const output = run.output || stream.output;
  const error = run.error || stream.error;
  const meta = TARGET_META[run.target_type];
  const usage = run.usage ?? {};

  return (
    <Page>
      <PageHeader
        back="/runs"
        icon={<TargetIcon type={run.target_type} size="md" />}
        title={run.target_name || run.target_id}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <RunStatusBadge status={status} />
            <Link to={`${meta.path}/${run.target_id}`} className="hover:text-fg hover:underline">{meta.label}</Link>
            <Badge tone="muted">{run.trigger}</Badge>
            <span className="font-mono text-xs">{run.id}</span>
          </span>
        }
        actions={
          <>
            {run.conversation_id && (
              <Link to={`/chat/${run.conversation_id}`}>
                <Button variant="outline" icon={<MessagesSquare className="size-4" />}>Conversation</Button>
              </Link>
            )}
            {!finished && can("member") && (
              <Button variant="outline" icon={<Square className="size-3.5" />} loading={cancel.isPending} onClick={() => cancel.mutate()}>
                Cancel
              </Button>
            )}
            {finished && can("member") && (
              <Button variant="outline" icon={<RotateCcw className="size-3.5" />} loading={rerun.isPending} onClick={() => rerun.mutate()} title="Run again with the same input">
                Re-run
              </Button>
            )}
          </>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Meta icon={<Clock className="size-4" />} label="Started" value={formatDate(run.started_at ?? run.created_at)} />
        <Meta icon={<Timer className="size-4" />} label="Duration" value={duration(run.started_at, run.finished_at)} />
        <Meta icon={<Coins className="size-4" />} label="Tokens" value={formatNumber(run.total_tokens || (usage.input_tokens ?? 0) + (usage.output_tokens ?? 0))} />
        <Meta icon={<Cpu className="size-4" />} label="Model calls" value={usage.llm_calls ?? "—"} />
        <Meta icon={<Wrench className="size-4" />} label="Tool calls" value={usage.tool_calls ?? "—"} />
        <Meta icon={<Coins className="size-4" />} label="In / out" value={`${formatNumber(usage.input_tokens ?? 0)} / ${formatNumber(usage.output_tokens ?? 0)}`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_420px]">
        <div className="min-w-0 space-y-5">
          {error && (
            <div className="flex items-start gap-2.5 rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-danger">
              <CircleX className="mt-0.5 size-4 shrink-0" />
              <div className="min-w-0 whitespace-pre-wrap break-words">{error}</div>
            </div>
          )}
          <Card className="overflow-hidden">
            <CardHeader title="Output" actions={output && <CopyButton text={output} label="Copy" />} />
            <div className="bg-gradient-to-br from-primary-soft/40 to-transparent p-4 sm:p-5">
              {output ? <Markdown>{output}</Markdown> : <p className="text-sm text-muted">{finished ? "No output." : "Waiting for output…"}</p>}
            </div>
          </Card>
          <Card>
            <CardHeader title="Trace" description={`${stream.events.length} events${finished ? "" : " · live"}`} />
            <div className="p-4">
              {stream.events.length === 0 && !Object.keys(stream.live).length ? (
                <p className="text-sm text-muted">Loading trace…</p>
              ) : (
                <RunTimeline events={stream.events} live={stream.live} />
              )}
            </div>
          </Card>
        </div>
        <div className="space-y-5">
          <Card>
            <CardHeader title="Input" actions={<CopyButton text={JSON.stringify(run.input, null, 2)} />} />
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed">{JSON.stringify(run.input, null, 2)}</pre>
          </Card>
          <Card className="space-y-2 p-4 text-xs text-muted">
            <div className="flex justify-between gap-2"><span>Created</span><span className="text-fg">{formatDate(run.created_at)}</span></div>
            <div className="flex justify-between gap-2"><span>Finished</span><span className="text-fg">{formatDate(run.finished_at)}</span></div>
            {run.automation_id && (
              <div className="flex justify-between gap-2"><span>Schedule</span><Link to={`/scheduler/${run.automation_id}`} className="font-mono text-primary hover:underline">{run.automation_id}</Link></div>
            )}
          </Card>
        </div>
      </div>
    </Page>
  );
}
