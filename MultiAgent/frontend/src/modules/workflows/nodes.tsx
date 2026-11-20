import { createContext, memo, useContext } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { LucideIcon } from "lucide-react";
import { Bot, Braces, CircleCheck, CircleX, Cpu, FileText, Flag, GitBranch, LoaderCircle, LogIn, SkipForward, Users, Wrench } from "lucide-react";
import type { Agent } from "@/modules/agents/types";
import type { Team } from "@/modules/teams/types";
import type { Tool } from "@/modules/tools/types";
import { cn } from "@/shared/lib/utils";
import { AgentAvatar, IconTile } from "@/shared/ui/icons";

export type NodeData = Record<string, any>;
export type FlowNode = Node<NodeData>;
export type NodeStatus = "running" | "done" | "failed" | "skipped";

export const NODE_META: Record<string, { label: string; icon: LucideIcon; color: string; description: string; defaults: NodeData }> = {
  input: { label: "Input", icon: LogIn, color: "slate", description: "Start of the workflow - exposes the run input.", defaults: { label: "Input" } },
  agent: { label: "Agent", icon: Bot, color: "indigo", description: "Run an agent with a prompt template.", defaults: { label: "Agent", agent_id: "", prompt: "{{ last }}" } },
  team: { label: "Team", icon: Users, color: "violet", description: "Hand the task to a multi-agent team.", defaults: { label: "Team", team_id: "", prompt: "{{ last }}" } },
  tool: { label: "Tool", icon: Wrench, color: "amber", description: "Call a built-in or custom tool directly.", defaults: { label: "Tool", tool_key: "", tool_id: "", args: "{}" } },
  llm: { label: "LLM", icon: Cpu, color: "sky", description: "A single model call (classify, extract, rewrite…).", defaults: { label: "LLM", provider: "default", model: "", system: "You are a helpful assistant.", prompt: "{{ last }}" } },
  condition: { label: "Condition", icon: GitBranch, color: "rose", description: "Branch on a Jinja expression (true / false).", defaults: { label: "Condition", expression: "'yes' in (last | lower)" } },
  template: { label: "Template", icon: Braces, color: "teal", description: "Compose text from previous outputs.", defaults: { label: "Template", template: "{{ last }}" } },
  output: { label: "Output", icon: Flag, color: "emerald", description: "Final result of the workflow.", defaults: { label: "Output", template: "{{ last }}" } },
};

export const PALETTE_ORDER = ["agent", "team", "tool", "llm", "condition", "template", "input", "output"];

export interface Lookups {
  agents: Record<string, Agent>;
  teams: Record<string, Team>;
  tools: Record<string, Tool>;
}

export const StatusCtx = createContext<Record<string, NodeStatus>>({});
export const LookupCtx = createContext<Lookups>({ agents: {}, teams: {}, tools: {} });

function summary(type: string, d: NodeData, l: Lookups): string {
  switch (type) {
    case "input":
      return "Run input";
    case "agent":
      return d.agent_id ? l.agents[d.agent_id]?.name ?? "Unknown agent" : "Select an agent";
    case "team":
      return d.team_id ? l.teams[d.team_id]?.name ?? "Unknown team" : "Select a team";
    case "tool":
      return d.tool_key ? `built-in · ${d.tool_key}` : d.tool_id ? l.tools[d.tool_id]?.display_name || l.tools[d.tool_id]?.name || "Custom tool" : "Select a tool";
    case "llm":
      return `${d.provider && d.provider !== "default" ? d.provider : "org default"}${d.model ? ` · ${d.model}` : ""}`;
    case "condition":
      return d.expression || "true";
    default:
      return d.template || "{{ last }}";
  }
}

function StatusIcon({ status }: { status?: NodeStatus }) {
  if (!status) return null;
  if (status === "running") return <LoaderCircle className="size-4 animate-spin text-primary" />;
  if (status === "done") return <CircleCheck className="size-4 text-success" />;
  if (status === "failed") return <CircleX className="size-4 text-danger" />;
  return <SkipForward className="size-4 text-muted" />;
}

const handleCls = "!size-3 !border-2 !border-[var(--surface)] !bg-[var(--primary)]";

function BaseNode({ id, type, data, selected }: NodeProps<FlowNode>) {
  const meta = NODE_META[type] ?? NODE_META.template;
  const status = useContext(StatusCtx)[id];
  const lookups = useContext(LookupCtx);
  const agent = type === "agent" && data.agent_id ? lookups.agents[data.agent_id] : undefined;
  return (
    <div
      className={cn(
        "relative w-[220px] rounded-xl border bg-surface shadow-sm transition-all",
        selected ? "border-primary ring-2 ring-[var(--ring)]" : "border-border",
        status === "running" && "animate-pulse-ring border-primary",
        status === "done" && "border-emerald-500/60",
        status === "failed" && "border-red-500/70",
        status === "skipped" && "opacity-50",
      )}
    >
      {type !== "input" && <Handle type="target" position={Position.Left} className={handleCls} />}
      <div className="flex items-center gap-2.5 p-2.5">
        {agent ? <AgentAvatar agent={agent} size="sm" /> : <IconTile icon={meta.icon} color={meta.color} size="sm" />}
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-medium uppercase tracking-wide text-muted">{meta.label}</div>
          <div className="truncate text-sm font-semibold">{data.label || meta.label}</div>
        </div>
        <StatusIcon status={status} />
      </div>
      <div className={cn("flex items-start gap-1.5 border-t border-border px-2.5 py-2 text-[11px] text-muted", type === "condition" && "pr-12")}>
        {(type === "template" || type === "output" || type === "condition") && <FileText className="mt-px size-3 shrink-0" />}
        <span className="line-clamp-2 break-all font-mono">{summary(type, data, lookups)}</span>
      </div>
      {type === "condition" ? (
        <>
          <Handle type="source" id="true" position={Position.Right} className={cn(handleCls, "!bg-emerald-500")} style={{ top: "62%" }} />
          <Handle type="source" id="false" position={Position.Right} className={cn(handleCls, "!bg-rose-500")} style={{ top: "86%" }} />
          <span className="pointer-events-none absolute right-3 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400" style={{ top: "calc(62% - 7px)" }}>true</span>
          <span className="pointer-events-none absolute right-3 text-[10px] font-semibold text-rose-600 dark:text-rose-400" style={{ top: "calc(86% - 7px)" }}>false</span>
        </>
      ) : (
        type !== "output" && <Handle type="source" position={Position.Right} className={handleCls} />
      )}
    </div>
  );
}

const Memo = memo(BaseNode);
export const nodeTypes = Object.fromEntries(Object.keys(NODE_META).map((k) => [k, Memo]));
