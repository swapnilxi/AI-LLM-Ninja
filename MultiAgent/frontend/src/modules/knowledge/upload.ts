/** Document upload with real progress (fetch has no upload progress, so this uses XHR with the same auth headers). */
import { apiBase, ApiError, authHeaders } from "@/shared/lib/api";
import type { Doc } from "./types";

export const MAX_UPLOAD_MB = 15;
export const ACCEPT_EXTS = [".pdf", ".docx", ".md", ".markdown", ".txt", ".csv", ".tsv", ".json", ".html", ".htm", ".yaml", ".yml", ".xml", ".log", ".ini", ".toml", ".py", ".js", ".ts", ".sql"];

export function fileProblem(f: File): string | null {
  const name = f.name.toLowerCase();
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  if (!ACCEPT_EXTS.includes(ext)) return `Unsupported type ${ext || "(none)"}`;
  if (f.size > MAX_UPLOAD_MB * 1024 * 1024) return `Larger than ${MAX_UPLOAD_MB} MB`;
  if (f.size === 0) return "File is empty";
  return null;
}

export function uploadDocument(
  file: File,
  opts: { ownerType: string; ownerId: string; pinned?: boolean; title?: string; onProgress?: (fraction: number) => void; signal?: AbortSignal },
): Promise<Doc> {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("owner_type", opts.ownerType);
    fd.append("owner_id", opts.ownerId);
    fd.append("pinned", String(!!opts.pinned));
    if (opts.title) fd.append("title", opts.title);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${apiBase}/api/documents/upload`);
    for (const [k, v] of Object.entries(authHeaders())) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => e.lengthComputable && opts.onProgress?.(e.loaded / e.total);
    xhr.onerror = () => reject(new ApiError(0, "Network error - is the API server running?"));
    xhr.onabort = () => reject(new ApiError(0, "Cancelled"));
    xhr.onload = () => {
      let data: any = null;
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        data = xhr.responseText;
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data as Doc);
      if (xhr.status === 401) window.dispatchEvent(new Event("af:unauthorized"));
      const detail = data && typeof data === "object" && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : xhr.statusText;
      reject(new ApiError(xhr.status, detail || `Upload failed (${xhr.status})`));
    };
    opts.signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(fd);
  });
}
