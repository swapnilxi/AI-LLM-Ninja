export type TaskStatus = "todo" | "doing" | "done";

export type TaskPriority = "low" | "normal" | "high";

export interface Task {
  id: string;
  project_id: string;
  title: string;
  notes: string;
  context: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_at: string | null;
  completed_at: string | null;
  source: "manual" | "chat" | "agent" | "text";
  conversation_id: string | null;
  message_id: string | null;
  run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskDraft {
  title: string;
  notes: string;
  priority: TaskPriority;
  due_at: string | null;
}

export interface TaskExtraction {
  engine: "ai" | "rules";
  context: string;
  items: TaskDraft[];
}

// ---------------------------------------------------------------- AI scheduler
