export type Source = {
  id: number; source: string; page: number | null; score: number; text: string;
  profile_id: string; profile_name: string; scope: "profile" | "common"; document_id: string;
};
export type ChatMessage = { role: "user" | "assistant"; content: string; sources?: Source[]; error?: string; at?: number; searchOnly?: boolean };
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
};
export type ProfileStats = { documents: number; indexed: number; pending: number; failed: number; bytes: number };
export type Profile = {
  id: string; name: string; folder: string; description: string; instructions: string; is_common: boolean;
  include_common: boolean; status: "active" | "missing"; last_sync_at: number | null; created_at: number;
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

/** POST /api/chat and invoke callbacks for each server-sent event. */
export async function streamChat(
  profileId: string,
  message: string,
  history: ChatMessage[],
  on: { sources: (s: Source[]) => void; token: (t: string) => void },
  signal: AbortSignal,
  override: { provider?: string; model?: string } = {},
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: headers(),
    signal,
    body: JSON.stringify({
      profile_id: profileId, message, history: history.map(({ role, content }) => ({ role, content })), stream: true,
      provider: override.provider || undefined, model: override.model || undefined,
    }),
  });
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
      const ev = JSON.parse(line.slice(5));
      if (ev.type === "sources") on.sources(ev.sources);
      else if (ev.type === "token") on.token(ev.text);
      else if (ev.type === "error") throw new ApiError(ev.message, 502);
    }
  }
}

/** Retrieval only (no LLM): the chunks that would be used as context. */
export async function queryContext(profileId: string, query: string, limit?: number): Promise<{ context: string; sources: Source[] }> {
  return api("/query-context", "POST", { profile_id: profileId, query, limit });
}

export const DOC_PENDING: DocStatus[] = ["DISCOVERED", "PENDING", "STALE", "INDEXING"];
export const profileUrl = (id: string, rest = "") => `/profiles/${encodeURIComponent(id)}${rest}`;
