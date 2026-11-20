import { Brain, Globe, Library } from "lucide-react";
import type { Agent } from "@/lib/types";
import { Badge } from "@/components/ui/primitives";

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

