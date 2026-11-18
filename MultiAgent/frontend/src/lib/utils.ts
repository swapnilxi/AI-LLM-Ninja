import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso).getTime();
  const s = Math.round((Date.now() - d) / 1000);
  const abs = Math.abs(s);
  const fmt = (n: number, u: string) => `${n}${u}`;
  let out: string;
  if (abs < 45) out = "just now";
  else if (abs < 3600) out = fmt(Math.round(abs / 60), "m");
  else if (abs < 86400) out = fmt(Math.round(abs / 3600), "h");
  else if (abs < 86400 * 30) out = fmt(Math.round(abs / 86400), "d");
  else return new Date(iso).toLocaleDateString();
  if (out === "just now") return out;
  return s >= 0 ? `${out} ago` : `in ${out}`;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatNumber(n?: number | null): string {
  if (n === undefined || n === null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 10_000) return `${(n / 1000).toFixed(0)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function duration(start?: string | null, end?: string | null): string {
  if (!start) return "—";
  const ms = (end ? new Date(end).getTime() : Date.now()) - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** Tailwind-safe accent palette for agent avatars. */
export const COLORS: Record<string, string> = {
  indigo: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-300",
  sky: "bg-sky-500/15 text-sky-600 dark:text-sky-300",
  violet: "bg-violet-500/15 text-violet-600 dark:text-violet-300",
  emerald: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
  amber: "bg-amber-500/15 text-amber-600 dark:text-amber-300",
  rose: "bg-rose-500/15 text-rose-600 dark:text-rose-300",
  slate: "bg-slate-500/15 text-slate-600 dark:text-slate-300",
  teal: "bg-teal-500/15 text-teal-600 dark:text-teal-300",
};

export const isGlobal = (x: { org_id: string | null }) => x.org_id === null;
