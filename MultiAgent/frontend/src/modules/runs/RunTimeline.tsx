import { useState, type ReactNode } from "react";
import {
  ArrowRightLeft,
  Bot,
  ChevronRight,
  CircleCheck,
  CircleX,
  Cpu,
  Flag,
  GitBranch,
  LoaderCircle,
  MessageSquareText,
  Play,
  SkipForward,
  Sparkles,
  Users,
  Wrench,
} from "lucide-react";
import type { RunEvent, RunStatus } from "@/modules/runs/types";
import { cn, formatNumber } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/primitives";
import { Markdown } from "@/shared/ui/Markdown";

export function RunStatusBadge({ status }: { status: RunStatus | string | null }) {
  if (!status) return null;
  const map: Record<string, { tone: "success" | "danger" | "warning" | "primary" | "muted"; icon: ReactNode }> = {
    succeeded: { tone: "success", icon: <CircleCheck className="size-3" /> },
    failed: { tone: "danger", icon: <CircleX className="size-3" /> },
    cancelled: { tone: "muted", icon: <CircleX className="size-3" /> },
    running: { tone: "primary", icon: <LoaderCircle className="size-3 animate-spin" /> },
    queued: { tone: "warning", icon: <LoaderCircle className="size-3" /> },
  };
  const m = map[status] ?? { tone: "muted" as const, icon: null };
  return (
    <Badge tone={m.tone} icon={m.icon} className="capitalize">
      {status}
    </Badge>
  );
}

function Row({ icon, title, meta, children, tone, defaultOpen = false }: { icon: ReactNode; title: ReactNode; meta?: ReactNode; children?: ReactNode; tone?: "danger" | "primary" | "muted"; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const expandable = !!children;
  return (
    <li className="relative pl-8">
      <span
        className={cn(
          "absolute left-0 top-1.5 flex size-6 items-center justify-center rounded-full border bg-surface",
          tone === "danger" ? "border-red-500/30 text-danger" : tone === "primary" ? "border-indigo-500/30 text-primary" : "border-border text-muted",
        )}
      >
        {icon}
      </span>
      <button
        type="button"
        disabled={!expandable}
        onClick={() => setOpen((o) => !o)}
        className={cn("flex w-full items-start gap-2 rounded-md py-1.5 text-left", expandable && "cursor-pointer hover:bg-surface-2/60")}
      >
        <div className="min-w-0 flex-1 text-sm">{title}</div>
        {meta && <div className="shrink-0 pt-0.5 text-[11px] text-muted">{meta}</div>}
        {expandable && <ChevronRight className={cn("mt-0.5 size-4 shrink-0 text-muted transition-transform", open && "rotate-90")} />}
      </button>
      {open && children && <div className="mb-2 mt-1 min-w-0">{children}</div>}
    </li>
  );
}

function Pre({ children, danger }: { children: ReactNode; danger?: boolean }) {
  return (
    <pre className={cn("max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-surface-2 p-2.5 font-mono text-[11px] leading-relaxed", danger && "border-red-500/30 text-danger")}>
      {children}
    </pre>
  );
}

const who = (ev: RunEvent) => (ev.agent ? <span className="font-medium">{ev.agent}</span> : null);

export function RunTimeline({ events, live = {}, className }: { events: RunEvent[]; live?: Record<string, string>; className?: string }) {
  const items = events.filter((e) => e.type !== "token" && e.type !== "thinking_token");
  return (
    <ol className={cn("relative space-y-0.5 before:absolute before:bottom-3 before:left-3 before:top-3 before:w-px before:bg-border", className)}>
      {items.map((ev, i) => {
        const d = ev.data ?? {};
        const key = ev.seq ?? i;
        switch (ev.type) {
          case "run_start":
            return <Row key={key} icon={<Play className="size-3" />} title={<span>Run started · <span className="text-muted">{d.target_type}</span> <span className="font-medium">{d.target_name}</span></span>} />;
          case "team_start":
            return (
              <Row key={key} icon={<Users className="size-3" />} tone="primary" title={<span>Team · <span className="font-medium capitalize">{String(d.style).replace("_", " ")}</span></span>} meta={`${d.members?.length ?? 0} members`}>
                <div className="flex flex-wrap gap-1">{(d.members ?? []).map((m: string) => <Badge key={m}>{m}</Badge>)}</div>
              </Row>
            );
          case "skill_command":
            return (
              <Row key={key} icon={<Sparkles className="size-3" />} tone="primary" title={<span>Command <span className="font-mono text-xs font-medium">/{d.command}</span> applied skill <span className="font-medium">{d.skill}</span></span>}>
                {d.args && <Pre>{d.args}</Pre>}
              </Row>
            );
          case "route":
            return <Row key={key} icon={<ArrowRightLeft className="size-3" />} tone="primary" title={<span>Routed to <span className="font-medium">{d.choice}</span></span>} />;
          case "agent_start":
            return (
              <Row key={key} icon={<Bot className="size-3" />} tone="primary" title={<span>{who(ev)} started</span>} meta={<span className="font-mono">{d.model}</span>}>
                <div className="space-y-2 text-xs">
                  {d.tools?.length > 0 && <div className="flex flex-wrap gap-1">{d.tools.map((t: string) => <Badge key={t} tone="muted" icon={<Wrench className="size-2.5" />}>{t}</Badge>)}</div>}
                  {d.skills?.length > 0 && <div className="text-muted">Skills: {d.skills.join(", ")}</div>}
                  <Pre>{d.task}</Pre>
                </div>
              </Row>
            );
          case "llm_response": {
            const calls = d.tool_calls ?? [];
            return (
              <Row
                key={key}
                icon={<Cpu className="size-3" />}
                title={
                  <span>
                    {who(ev)} {calls.length ? <>→ calls <span className="font-mono text-xs">{calls.map((c: any) => c.name).join(", ")}</span></> : "responded"}
                  </span>
                }
                meta={d.usage ? `${formatNumber((d.usage.input_tokens ?? 0) + (d.usage.output_tokens ?? 0))} tok` : undefined}
              >
                {d.thinking && <Pre>{d.thinking}</Pre>}
                {d.text && (
                  <div className="rounded-lg border border-border bg-surface p-3">
                    <Markdown>{d.text}</Markdown>
                  </div>
                )}
              </Row>
            );
          }
          case "tool_call":
            return (
              <Row key={key} icon={<Wrench className="size-3" />} title={<span><span className="font-mono text-xs font-medium">{d.name}</span> {ev.agent && <span className="text-muted">· {ev.agent}</span>}</span>}>
                <Pre>{JSON.stringify(d.arguments, null, 2)}</Pre>
              </Row>
            );
          case "tool_result":
            return (
              <Row
                key={key}
                icon={d.is_error ? <CircleX className="size-3" /> : <CircleCheck className="size-3" />}
                tone={d.is_error ? "danger" : undefined}
                title={<span className={cn(d.is_error && "text-danger")}><span className="font-mono text-xs">{d.name}</span> {d.is_error ? "failed" : "returned"}</span>}
                meta={d.duration_ms !== undefined ? `${d.duration_ms} ms` : undefined}
              >
                <Pre danger={d.is_error}>{d.output}</Pre>
              </Row>
            );
          case "team_message":
            return (
              <Row key={key} icon={<MessageSquareText className="size-3" />} title={<span><span className="font-medium">{d.from}</span>{d.round ? <span className="text-muted"> · round {d.round}</span> : null}</span>}>
                <div className="rounded-lg border border-border bg-surface p-3"><Markdown>{d.text ?? ""}</Markdown></div>
              </Row>
            );
          case "node_start":
            return <Row key={key} icon={<GitBranch className="size-3" />} title={<span>Node <span className="font-medium">{d.label}</span> <span className="text-muted">({d.type})</span></span>} />;
          case "node_end":
            return (
              <Row key={key} icon={d.status === "failed" ? <CircleX className="size-3" /> : <CircleCheck className="size-3" />} tone={d.status === "failed" ? "danger" : undefined}
                title={<span>Node <span className="font-medium">{d.label}</span> {d.status === "failed" ? "failed" : d.branch ? <>→ <Badge tone="primary">{d.branch}</Badge></> : "done"}</span>}
                meta={d.duration_ms !== undefined ? `${d.duration_ms} ms` : undefined}
              >
                <Pre danger={d.status === "failed"}>{d.error || d.output}</Pre>
              </Row>
            );
          case "node_skipped":
            return <Row key={key} icon={<SkipForward className="size-3" />} tone="muted" title={<span className="text-muted">Skipped <span className="font-medium">{d.label}</span></span>} />;
          case "agent_end":
            return <Row key={key} icon={<CircleCheck className="size-3" />} title={<span>{who(ev)} finished</span>} />;
          case "team_end":
            return <Row key={key} icon={<Users className="size-3" />} title="Team finished" />;
          case "run_end":
            return (
              <Row key={key} icon={<Flag className="size-3" />} tone={d.status === "failed" ? "danger" : "primary"} title={<span>Run <span className="font-medium">{d.status}</span></span>}
                meta={d.usage ? `${formatNumber((d.usage.input_tokens ?? 0) + (d.usage.output_tokens ?? 0))} tokens · ${d.usage.tool_calls ?? 0} tool calls` : undefined}
              >
                {d.error && <Pre danger>{d.error}</Pre>}
              </Row>
            );
          default:
            return <Row key={key} icon={<ChevronRight className="size-3" />} title={<span className="text-muted">{ev.type}</span>} />;
        }
      })}
      {Object.entries(live).map(([agent, text]) => (
        <li key={`live-${agent}`} className="relative pl-8">
          <span className="animate-pulse-ring absolute left-0 top-1.5 flex size-6 items-center justify-center rounded-full border border-indigo-500/40 bg-surface text-primary">
            <LoaderCircle className="size-3 animate-spin" />
          </span>
          <div className="py-1.5 text-sm"><span className="font-medium">{agent}</span> <span className="text-muted">is writing…</span></div>
          <div className="mb-2 rounded-lg border border-border bg-surface p-3"><Markdown>{text}</Markdown></div>
        </li>
      ))}
    </ol>
  );
}
