import type { TargetType } from "@/shared/lib/types";

export type TriggerType = "schedule" | "interval" | "once" | "webhook" | "manual";

/** A schedule (backend table `automations`). */
export interface Automation {
  id: string;
  project_id: string;
  name: string;
  description: string;
  target_type: TargetType;
  target_id: string;
  input: Record<string, any>;
  trigger_type: TriggerType;
  cron: string;
  interval_minutes: number;
  timezone: string;
  run_at: string | null;
  source: "form" | "chat" | "agent" | string;
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: string;
  run_count: number;
  created_at: string;
  webhook_url: string | null;
}
export type Schedule = Automation;

export interface ScheduleDraft {
  name: string;
  task: string;
  trigger_type: "schedule" | "interval" | "once" | "manual";
  cron: string;
  interval_minutes: number;
  run_at: string | null;
  timezone: string;
  summary: string;
  next_runs: string[];
  notes: string[];
  engine?: "ai" | "rules";
  target_type: "agent";
  target_id: string;
  target_name: string;
  project_id?: string;
  input?: Record<string, any>;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantReply {
  reply: string;
  draft: ScheduleDraft | null;
  ready: boolean;
  missing: ("task" | "when")[];
  action: "create" | null;
  engine: "ai" | "rules";
}

export interface UpcomingRun {
  automation_id: string;
  name: string;
  at: string;
  trigger_type: TriggerType;
  target_type: TargetType;
  target_id: string;
}
