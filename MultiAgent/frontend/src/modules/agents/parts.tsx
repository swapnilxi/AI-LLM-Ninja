import { Brain, Eye, Globe, Library, type LucideIcon } from "lucide-react";
import type { Agent, AgentSettings } from "@/modules/agents/types";
import { Badge } from "@/shared/ui/primitives";

export function modelLabel(a: Pick<Agent, "provider" | "model">) {
  if (!a.provider || a.provider === "default") return a.model ? `Org default · ${a.model}` : "Org default";
  return `${a.provider}${a.model ? ` · ${a.model}` : ""}`;
}

export function CapabilityBadges({ agent }: { agent: Agent }) {
  const s = agent.settings ?? {};
  return (
    <>
      {s.browser_enabled && <Badge tone="primary" icon={<Globe className="size-2.5" />}>Web</Badge>}
      {s.memory_enabled && <Badge tone="primary" icon={<Brain className="size-2.5" />}>Memory</Badge>}
      {s.knowledge_enabled !== false && <Badge tone="muted" icon={<Library className="size-2.5" />}>Knowledge</Badge>}
      {agent.skill_ids.length > 0 && <Badge tone="muted">{agent.skill_ids.length} skill{agent.skill_ids.length === 1 ? "" : "s"}</Badge>}
      {agent.tool_ids.length > 0 && <Badge tone="muted">{agent.tool_ids.length} tool{agent.tool_ids.length === 1 ? "" : "s"}</Badge>}
    </>
  );
}


/** The run launcher page (owned by the runs module). */
export const runAgentUrl = (id: string) => `/runs/new?target_type=agent&target_id=${encodeURIComponent(id)}`;

/** Training window pages (owned by the training module). */
export const trainingUrl = (id: string, sub: "" | "ingest" | "teach" | "memory" = "") => `/training/${id}${sub ? `/${sub}` : ""}`;

export const CAPABILITIES: { key: Exclude<keyof AgentSettings, "auto_learn">; label: string; description: string; icon: LucideIcon }[] = [
  { key: "browser_enabled", label: "Web search & browser", description: "Adds web_search and browse_webpage (JS rendering when available).", icon: Globe },
  { key: "memory_enabled", label: "Long-term memory", description: "Adds the memory tool and injects this agent's recent memories.", icon: Brain },
  { key: "knowledge_enabled", label: "Document knowledge", description: "Searches agent, project and organization documents when any exist.", icon: Library },
  { key: "show_thinking", label: "Show reasoning summaries", description: "Records summarized thinking in the run trace when the model supports it.", icon: Eye },
];

export const capabilityOn = (settings: AgentSettings | undefined, key: keyof AgentSettings) =>
  key === "knowledge_enabled" ? settings?.knowledge_enabled !== false : !!settings?.[key];
