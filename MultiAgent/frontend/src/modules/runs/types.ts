import type { TargetType } from "@/shared/lib/types";

export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Run {
  id: string;
  project_id: string;
  target_type: TargetType;
  target_id: string;
  target_name: string;
  status: RunStatus;
  input: Record<string, any>;
  output: string;
  error: string;
  trigger: string;
  automation_id: string | null;
  conversation_id: string | null;
  user_id: string | null;
  usage: { input_tokens?: number; output_tokens?: number; llm_calls?: number; tool_calls?: number };
  total_tokens: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunEvent {
  seq?: number;
  id?: number;
  type: string;
  agent: string;
  node_id: string;
  data: Record<string, any>;
  created_at: string;
}
