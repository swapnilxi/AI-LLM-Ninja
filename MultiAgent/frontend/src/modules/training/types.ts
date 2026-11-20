export type LessonKind = "rule" | "fact" | "example" | "correction";

export interface Lesson {
  id: string;
  agent_id: string;
  status: "pending" | "approved" | "rejected";
  source: "user" | "feedback" | "auto";
  kind: LessonKind;
  title: string;
  content: string;
  /** Q&A example: the question. Correction: what the agent got wrong. */
  prompt: string | null;
  rationale: string;
  conversation_id: string | null;
  memory_id: string | null;
  created_at: string;
}

export interface TrainingOverview {
  auto_learn: boolean;
  can_configure: boolean;
  pending: number;
  approved: number;
  rejected: number;
  approved_by_kind: Record<LessonKind, number>;
  memories: number;
  documents: number;
  chunks: number;
  pinned_documents: number;
  document_bytes: number;
}

export interface AgentTrainingStats {
  documents: number;
  chunks: number;
  pending: number;
  approved: number;
  memories: number;
}

export interface SearchHit {
  document_id: string;
  title: string;
  scope: "org" | "project" | "agent";
  chunk: number;
  score: number;
  text: string;
}
