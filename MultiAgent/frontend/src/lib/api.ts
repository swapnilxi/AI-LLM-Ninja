/** Thin fetch client: bearer token + tenant header, typed errors. */
const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

const TOKEN_KEY = "af_token";
const ORG_KEY = "af_org";

export const session = {
  get token() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  get orgId() {
    try {
      return localStorage.getItem(ORG_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null, orgId?: string | null) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
      if (orgId !== undefined) {
        if (orgId) localStorage.setItem(ORG_KEY, orgId);
        else localStorage.removeItem(ORG_KEY);
      }
    } catch {
      /* storage unavailable */
    }
  },
  setOrg(orgId: string) {
    try {
      localStorage.setItem(ORG_KEY, orgId);
    } catch {
      /* ignore */
    }
  },
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Opts = { method?: string; body?: unknown; form?: FormData; signal?: AbortSignal; org?: string | null };

export function authHeaders(org?: string | null): Record<string, string> {
  const h: Record<string, string> = {};
  const t = session.token;
  if (t) h.Authorization = `Bearer ${t}`;
  const o = org === undefined ? session.orgId : org;
  if (o) h["X-Org-Id"] = o;
  return h;
}

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const headers = authHeaders(opts.org);
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`${BASE}/api${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body, signal: opts.signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Network error - is the API server running?");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/auth/login")) window.dispatchEvent(new Event("af:unauthorized"));
    const detail = typeof data === "object" && data?.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText;
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  return data as T;
}

export const http = {
  get: <T = any>(p: string, signal?: AbortSignal) => api<T>(p, { signal }),
  post: <T = any>(p: string, body?: unknown) => api<T>(p, { method: "POST", body: body ?? {} }),
  put: <T = any>(p: string, body?: unknown) => api<T>(p, { method: "PUT", body }),
  patch: <T = any>(p: string, body?: unknown) => api<T>(p, { method: "PATCH", body }),
  del: <T = any>(p: string) => api<T>(p, { method: "DELETE" }),
  upload: <T = any>(p: string, form: FormData) => api<T>(p, { method: "POST", form }),
};

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  const out = s.toString();
  return out ? `?${out}` : "";
}

export const apiBase = BASE;
