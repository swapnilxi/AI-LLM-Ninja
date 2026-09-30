/**
 * PDF utilities (frontend). Mirrors rag-be/app/utils/pdf.py — read that file's checklist first.
 *
 * WHAT THE FRONTEND DOES FOR PDFs
 *   1. pre-upload check ........ checkPdf(file)              header + "password protected?" warning
 *   2. show PDF metadata ....... fetchDocInfo(name)           pages, title, author, scanned? (from the backend)
 *   3. open at a cited page .... openDocument(name, page)     citations "manual.pdf p.7" become clickable
 *   4. download ................ downloadDocument(name)
 * Everything heavy (text extraction, cleaning, OCR detection, split/merge) stays on the backend on purpose:
 * no pdf.js bundle in the browser, and one implementation to trust.
 * Want an in-app viewer instead of a new tab? Add `react-pdf` and render <Document file={blobUrl}> at `page`.
 */
import { getToken } from "@/lib/api";
import { kindOf, sniff, startsWith } from "./filetypes";

export type CheckResult = { ok: boolean; reason?: string; warning?: string };

const PDF_MAGIC = [0x25, 0x50, 0x44, 0x46];
const latin1 = (b: Uint8Array) => new TextDecoder("latin1").decode(b);

/** Quick client-side sanity check. The server does the real validation (page limit, corruption...). */
export async function checkPdf(file: File): Promise<CheckResult> {
  const head = await sniff(file, 1024);
  if (!startsWith(head, PDF_MAGIC)) return { ok: false, reason: "not a real PDF (missing %PDF header)" };
  // The trailer of an encrypted PDF contains /Encrypt. Owner-locked files still work; user-locked ones fail on the server.
  const tail = latin1(new Uint8Array(await file.slice(Math.max(0, file.size - 4096)).arrayBuffer()));
  if (tail.includes("/Encrypt")) return { ok: true, warning: "PDF is encrypted; indexing fails if it needs a password" };
  return { ok: true };
}

export type DocInfo = {
  name: string;
  type: string;
  mime: string;
  size: number;
  pages?: number;
  title?: string;
  author?: string;
  created?: string;
  encrypted?: boolean;
  scanned?: boolean;
  paragraphs?: number;
  tables?: number;
  error?: string;
};

/** Identifies a document inside its profile (the server never accepts raw paths). */
export type DocRef = { profileId: string; documentId: string; name: string };
const docUrl = (r: DocRef, what: "info" | "file") => `/api/profiles/${encodeURIComponent(r.profileId)}/documents/${encodeURIComponent(r.documentId)}/${what}`;

async function authedFetch(path: string): Promise<Response> {
  const token = getToken();
  const res = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res;
}

export async function fetchDocInfo(ref: DocRef): Promise<DocInfo> {
  return (await authedFetch(docUrl(ref, "info"))).json();
}

async function fetchBlobUrl(ref: DocRef): Promise<string> {
  const res = await authedFetch(docUrl(ref, "file"));
  return URL.createObjectURL(await res.blob());
}

/**
 * Open a document in a new tab; PDFs jump to `page` (1-based). Types a browser cannot render are downloaded.
 * The request goes through fetch() so the API token is sent — a plain <a href> would fail when ADMIN_TOKEN is set.
 */
export async function openDocument(ref: DocRef, page?: number | null): Promise<void> {
  const name = ref.name;
  if (!kindOf(name)?.inline) return downloadDocument(ref);
  const tab = window.open("", "_blank"); // open synchronously: popup blockers reject window.open after an await
  try {
    const url = await fetchBlobUrl(ref);
    const target = page && name.toLowerCase().endsWith(".pdf") ? `${url}#page=${page}` : url;
    if (tab) tab.location.href = target;
    else window.location.href = target;
  } catch (e) {
    tab?.close();
    throw e;
  }
}

export async function downloadDocument(ref: DocRef): Promise<void> {
  const name = ref.name;
  const url = await fetchBlobUrl(ref);
  const a = document.createElement("a");
  a.href = url;
  a.download = name.split("/").pop() ?? name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** "manual.pdf · p.7" style label for a citation. */
export const citationLabel = (source: string, page?: number | null): string => (page ? `${source} · p.${page}` : source);
