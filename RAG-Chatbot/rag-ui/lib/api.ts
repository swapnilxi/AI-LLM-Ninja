export type Source = {
  id: number; source: string; page: number | null; score: number; text: string;
  profile_id: string; profile_name: string; scope: "profile" | "common"; document_id: string;
  kind: "document" | "faq"; faq_id: string | null;
};
export type Faq = {
  id: string; question: string; answer: string; category: string; enabled: boolean; position: number;
  status: "PENDING" | "INDEXED" | "FAILED" | "DISABLED"; indexed_at: number | null; error_message: string; updated_at: number;
};
export type ChatMessage = { role: "user" | "assistant"; content: string; sources?: Source[]; steps?: AgentStep[]; graph?: string[]; error?: string; at?: number; searchOnly?: boolean };
export type AgentRole = "planner" | "researcher" | "critic" | "synthesizer";
export type Agent = {
  id: string; profile_id: string; profile_name: string; name: string; role: AgentRole; description: string;
  instructions: string; focus: string; model: string; enabled: boolean; position: number;
  run_count: number; error_count: number; last_run_at: number | null; last_error: string; updated_at: number;
};
export type Business = { id: string; name: string; is_common: boolean; agents: number };
export type AgentsResponse = { agents: Agent[]; businesses: Business[]; roles: Record<AgentRole, string>; max_researchers: number };
export type AgentStep = { agent_id: string; name: string; role: AgentRole; status: "running" | "done" | "error"; detail: string };
export type Settings = Record<string, string | number | boolean>;
export type ProviderInfo = { label: string; default_model?: string; models?: string[]; fields: string[] };
export type Catalog = {
  llm: Record<string, ProviderInfo>;
  embedding: Record<string, ProviderInfo>;
  vector_store: Record<string, ProviderInfo>;
  presets: Record<string, { label: string; values: Settings }>;
};
export type DocStatus = "DISCOVERED" | "PENDING" | "INDEXING" | "INDEXED" | "STALE" | "FAILED" | "DELETED";
export type DocRow = {
  id: string; filename: string; relative_path: string; folder: string; extension: string; size: number;
  modified: number | null; status: DocStatus; chunks: number; indexed_at: number | null; error: string;
  embedding_model: string; embedding_version: string; chunking_version: string; embedding_dimension: number;
  category_ids: string[];
};
export type Category = { id: string; profile_id: string; name: string; position: number; created_at: number; updated_at: number };
export type ProfileStats = { documents: number; indexed: number; pending: number; failed: number; bytes: number; faqs: number; faqs_enabled: number; faqs_indexed: number };
export type Profile = {
  id: string; name: string; folder: string; description: string; instructions: string; is_common: boolean;
  include_common: boolean; use_faqs: boolean; status: "active" | "missing"; last_sync_at: number | null; created_at: number;
  stats: ProfileStats; indexing: null | { state: string; message: string; error: string | null };
};
export type StoreStatus = { ok: boolean; backend?: string; location?: string; chunks?: number; sources?: number; error?: string };
export type AppStatus = {
  store: StoreStatus;
  profiles: number;
  sync: SyncStatus;
  flags: { allow_ui_config: boolean; allow_ui_upload: boolean };
  supported_extensions: string[];
};
export type SyncStatus = {
  state: "idle" | "running" | "done" | "error";
  message: string;
  profile?: string | null;
  queued?: string[];
  error: string | null;
  result: null | { added: string[]; updated: string[]; removed: string[]; unchanged: number; chunks: number; errors: Record<string, string>; seconds: number };
};

const TOKEN_KEY = "rag.apiToken";
export const getToken = () => (typeof window === "undefined" ? "" : localStorage.getItem(TOKEN_KEY) || "");
export const setToken = (t: string) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const t = getToken();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

async function fail(res: Response): Promise<never> {
  let detail = res.statusText;
  let code: string | undefined;
  try {
    const b = await res.json();
    detail = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail);
    code = b.code;
  } catch {}
  throw new ApiError(detail, res.status, code);
}

export async function api<T = any>(path: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, { method, headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) await fail(res);
  return res.json();
}

export async function upload(profileId: string, files: FileList | File[], folder = ""): Promise<{ saved: string[]; sync_started: boolean }> {
  const fd = new FormData();
  Array.from(files).forEach((f) => fd.append("files", f));
  fd.append("folder", folder);
  const res = await fetch(`/api/profiles/${encodeURIComponent(profileId)}/documents`, { method: "POST", headers: headers(false), body: fd });
  if (!res.ok) await fail(res);
  return res.json();
}

/** POST an SSE endpoint under /api and invoke `onEvent` for each `data: {...}` line. */
async function postSSE(path: string, body: unknown, onEvent: (ev: any) => void, signal: AbortSignal): Promise<void> {
  const res = await fetch(`/api${path}`, { method: "POST", headers: headers(), signal, body: JSON.stringify(body) });
  if (!res.ok) await fail(res);
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 2);
      if (!line.startsWith("data:")) continue;
      onEvent(JSON.parse(line.slice(5)));
    }
  }
}

/** POST /api/chat and invoke callbacks for each server-sent event. */
export async function streamChat(
  profileId: string,
  message: string,
  history: ChatMessage[],
  on: { sources: (s: Source[], graph?: { enabled: boolean; entities: string[] }) => void; token: (t: string) => void; agent?: (s: AgentStep) => void },
  signal: AbortSignal,
  override: { provider?: string; model?: string; multiAgent?: boolean; graphRag?: boolean } = {},
): Promise<void> {
  await postSSE("/chat", {
    profile_id: profileId, message, history: history.map(({ role, content }) => ({ role, content })), stream: true,
    provider: override.provider || undefined, model: override.model || undefined, multi_agent: override.multiAgent || undefined, graph_rag: override.graphRag,
  }, (ev) => {
    if (ev.type === "sources") on.sources(ev.sources, ev.graph);
    else if (ev.type === "token") on.token(ev.text);
    else if (ev.type === "agent") on.agent?.(ev);
    else if (ev.type === "error") throw new ApiError(ev.message, 502);
  }, signal);
}

// ---- Guides tab: analyze a codebase against the RAG checklist, explain individual items ----
export type GuideItemSpec = { id: string; title: string; detail: string; section: string };
export type GuideStatus = "done" | "partial" | "missing";
export type GuideAssessment = { status: GuideStatus; note: string };
export type GuideAnalysis = {
  target: string; files_reviewed: string[]; items: Record<string, GuideAssessment>; summary: string; next_steps: string[];
};

export async function analyzeGuides(checklist: GuideItemSpec[], repoUrl?: string): Promise<GuideAnalysis> {
  return api("/guides/analyze", "POST", { checklist, repo_url: repoUrl?.trim() || undefined });
}

/** POST /api/guides/explain and invoke `onToken` as the answer streams in. */
export async function streamGuideExplain(
  item: GuideItemSpec,
  question: string,
  history: { role: "user" | "assistant"; content: string }[],
  analysisNote: string,
  onToken: (t: string) => void,
  signal: AbortSignal,
): Promise<void> {
  await postSSE("/guides/explain", { item, question, history, analysis_note: analysisNote, stream: true }, (ev) => {
    if (ev.type === "token") onToken(ev.text);
    else if (ev.type === "error") throw new ApiError(ev.message, 502);
  }, signal);
}

/** Retrieval only (no LLM): the chunks that would be used as context. */
export async function queryContext(profileId: string, query: string, limit?: number): Promise<{ context: string; sources: Source[] }> {
  return api("/query-context", "POST", { profile_id: profileId, query, limit });
}

export const DOC_PENDING: DocStatus[] = ["DISCOVERED", "PENDING", "STALE", "INDEXING"];
export const profileUrl = (id: string, rest = "") => `/profiles/${encodeURIComponent(id)}${rest}`;
