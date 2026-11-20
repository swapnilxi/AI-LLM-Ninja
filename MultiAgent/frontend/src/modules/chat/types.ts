export interface Conversation {
  id: string;
  project_id: string;
  target_type: "agent" | "team";
  target_id: string;
  title: string;
  skill_ids?: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  run_id: string | null;
  meta: Record<string, any>;
  created_at: string;
}
