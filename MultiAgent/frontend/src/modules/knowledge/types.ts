export interface Doc {
  id: string;
  owner_type: "org" | "project" | "agent";
  owner_id: string;
  title: string;
  source: string;
  source_ref: string;
  mime: string;
  size: number;
  chunk_count: number;
  pinned: boolean;
  created_at: string;
  updated_at: string;
  content?: string;
}

export interface Memory {
  id: string;
  scope: "agent" | "project";
  agent_id: string | null;
  project_id: string | null;
  key: string;
  content: string;
  tags: string[];
  source: "agent" | "user" | "learned";
  run_id: string | null;
  created_at: string;
}
