import type { Effort } from "@/shared/lib/types";

export interface AgentSettings {
  browser_enabled?: boolean;
  memory_enabled?: boolean;
  knowledge_enabled?: boolean;
  show_thinking?: boolean;
  auto_learn?: boolean;
}

export interface Agent {
  id: string;
  org_id: string | null;
  name: string;
  description: string;
  avatar: string;
  color: string;
  provider: string;
  model: string;
  system_prompt: string;
  temperature: number | null;
  max_tokens: number;
  max_steps: number;
  effort: Effort;
  tool_ids: string[];
  skill_ids: string[];
  connection_ids: string[];
  settings: AgentSettings;
  tags: string[];
  created_at: string;
  updated_at: string;
}
