import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, Cpu, History, Minus, Play, Plug, ScrollText, Sparkles, Wrench } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { cn, timeAgo } from "@/shared/lib/utils";
import { useRuns } from "@/modules/runs/api";
import { RunStatusBadge } from "@/modules/runs/RunTimeline";
import { Badge, Card, CardHeader, EmptyState, Spinner, Stat } from "@/shared/ui/primitives";
import { useAgentWorkspace } from "../context";
import { CAPABILITIES, capabilityOn, modelLabel, runAgentUrl } from "../parts";

function SectionLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
      {children} <ArrowRight className="size-3" />
    </Link>
  );
}

export default function Overview() {
  const { id, agent, form, leave } = useAgentWorkspace();
  const { can } = useAuth();
  const runs = useRuns({ target_type: "agent", target_id: id, limit: 6 });
  const base = `/agents/${id}`;
  const prompt = form.system_prompt.trim();

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Link to={`${base}/model`} className="min-w-0">
          <Stat label="Model" icon={<Cpu className="size-4 text-primary" />} value={<span className="block truncate text-base">{form.provider === "default" ? "Org default" : form.provider}</span>} hint={<span className="block truncate font-mono">{modelLabel(form)}</span>} />
        </Link>
        <Link to={`${base}/tools`} className="min-w-0">
          <Stat label="Tools" icon={<Wrench className="size-4 text-primary" />} value={form.tool_ids.length} hint="Built-in and custom" />
        </Link>
        <Link to={`${base}/skills`} className="min-w-0">
          <Stat label="Skills" icon={<Sparkles className="size-4 text-primary" />} value={form.skill_ids.length} hint="Instruction packs" />
        </Link>
        <Link to={`${base}/tools`} className="min-w-0">
          <Stat label="Connectors" icon={<Plug className="size-4 text-primary" />} value={form.connection_ids.length} hint="App connections" />
        </Link>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-5">
          <Card>
            <CardHeader title={<span className="inline-flex items-center gap-2"><ScrollText className="size-4 text-primary" />Instructions</span>} actions={<SectionLink to={`${base}/instructions`}>Edit</SectionLink>} />
            <div className="p-4 sm:p-5">
              {form.description && <p className="mb-3 text-sm">{form.description}</p>}
              {prompt ? (
                <pre className="line-clamp-[8] whitespace-pre-wrap break-words rounded-lg bg-surface-2/50 px-3 py-2.5 font-mono text-xs leading-5 text-muted">{prompt}</pre>
              ) : (
                <p className="text-sm text-muted">
                  No system prompt yet. <Link to={`${base}/instructions`} className="font-medium text-primary hover:underline">Write instructions</Link> to shape how this agent works.
                </p>
              )}
              {form.tags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {form.tags.map((t) => (
                    <Badge key={t} tone="muted">{t}</Badge>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader
              title={<span className="inline-flex items-center gap-2"><History className="size-4 text-primary" />Recent runs</span>}
              description={runs.data ? `${runs.data.total} total` : undefined}
              actions={<button type="button" onClick={() => leave(`/runs?target_type=agent&target_id=${id}`)} className="inline-flex cursor-pointer items-center gap-1 text-xs font-medium text-primary hover:underline">All runs <ArrowRight className="size-3" /></button>}
            />
            {runs.isLoading ? (
              <div className="flex justify-center p-6"><Spinner /></div>
            ) : !runs.data?.items.length ? (
              <div className="p-4">
                <EmptyState
                  icon={<Play className="size-5" />}
                  title="No runs yet"
                  description="Start a run to see this agent work end to end."
                  action={can("member") && (
                    <button type="button" onClick={() => leave(runAgentUrl(id))} className="cursor-pointer rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white dark:text-[#0b0d12]">
                      Run agent
                    </button>
                  )}
                />
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {runs.data.items.map((r) => (
                  <li key={r.id}>
                    <button type="button" onClick={() => leave(`/runs/${r.id}`)} className="flex w-full cursor-pointer items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-2/60 sm:px-5">
                      <RunStatusBadge status={r.status} />
                      <span className="min-w-0 flex-1 truncate text-sm">{runSummary(r.input) || <span className="text-muted">No input</span>}</span>
                      <span className="hidden shrink-0 text-xs text-muted sm:inline">{r.trigger}</span>
                      <span className="shrink-0 text-xs text-muted">{timeAgo(r.created_at)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader title="Capabilities" actions={<SectionLink to={`${base}/tools`}>Edit</SectionLink>} />
            <ul className="space-y-1 p-3">
              {CAPABILITIES.map((c) => {
                const on = capabilityOn(form.settings, c.key);
                return (
                  <li key={c.key} className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm">
                    <c.icon className={cn("size-4", on ? "text-primary" : "text-muted")} />
                    <span className={cn("flex-1", !on && "text-muted")}>{c.label}</span>
                    {on ? <Check className="size-4 text-success" /> : <Minus className="size-4 text-muted" />}
                  </li>
                );
              })}
            </ul>
          </Card>

          <Card>
            <CardHeader title="Settings at a glance" />
            <dl className="space-y-2 p-4 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-muted">Reasoning effort</dt><dd className="font-medium capitalize">{form.effort}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">Temperature</dt><dd className="font-medium">{form.temperature ?? "Default"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">Max output tokens</dt><dd className="font-medium tabular-nums">{form.max_tokens.toLocaleString()}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">Max steps</dt><dd className="font-medium tabular-nums">{form.max_steps}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-muted">Updated</dt><dd className="font-medium">{timeAgo(agent.updated_at)}</dd></div>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}

function runSummary(input: Record<string, any> | undefined): string {
  if (!input) return "";
  const v = input.message ?? input.input ?? input.prompt ?? input.task ?? Object.values(input).find((x) => typeof x === "string");
  return typeof v === "string" ? v : "";
}
