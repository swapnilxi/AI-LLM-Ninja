import { MemoryPanel } from "@/modules/knowledge/MemoryPanel";
import type { TabProps } from "../AgentTraining";

export function MemoryTab({ agent, canEdit }: TabProps) {
  return (
    <MemoryPanel
      scope="agent"
      agentId={agent.id}
      readOnly={!canEdit}
      description="Everything this agent remembers across projects. Taught and approved lessons are always in its prompt; notes it saved itself need the memory capability."
    />
  );
}
