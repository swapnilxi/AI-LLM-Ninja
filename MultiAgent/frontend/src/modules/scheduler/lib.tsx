/** Shared scheduler helpers: trigger metadata, labels and timezone-safe date conversion. */
import { CalendarClock, CalendarCheck, Hand, Timer, Webhook, type LucideIcon } from "lucide-react";
import { useMemo } from "react";
import { useAgents } from "@/modules/agents/api";
import { useTeams } from "@/modules/teams/api";
import { useWorkflows } from "@/modules/workflows/api";
import type { Automation, TriggerType } from "./types";

export const TRIGGERS: { key: TriggerType; label: string; icon: LucideIcon; color: string; hint: string }[] = [
  { key: "once", label: "Once", icon: CalendarCheck, color: "amber", hint: "Runs one time at a date and time you pick." },
  { key: "schedule", label: "Recurring", icon: CalendarClock, color: "violet", hint: "Runs on a repeating schedule (cron) in your timezone." },
  { key: "interval", label: "Interval", icon: Timer, color: "sky", hint: "Runs every N minutes (minimum 5)." },
  { key: "webhook", label: "Webhook", icon: Webhook, color: "emerald", hint: "Runs when an external system POSTs JSON to a secret URL." },
  { key: "manual", label: "Manual", icon: Hand, color: "slate", hint: "Only runs when you click Run now (or via the API)." },
];
export const triggerMeta = (t: TriggerType) => TRIGGERS.find((x) => x.key === t) ?? TRIGGERS[TRIGGERS.length - 1];

export const CRON_PRESETS = [
  { label: "Hourly", cron: "0 * * * *" },
  { label: "Daily 09:00", cron: "0 9 * * *" },
  { label: "Weekdays 09:00", cron: "0 9 * * 1-5" },
  { label: "Mondays 09:00", cron: "0 9 * * 1" },
  { label: "Monthly, 1st", cron: "0 9 1 * *" },
];

export const TIMEZONES: string[] = (() => {
  try {
    return ((Intl as any).supportedValuesOf?.("timeZone") as string[]) ?? [];
  } catch {
    return [];
  }
})();

export const localTz = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/** Human label for a schedule's trigger. */
export function describeSchedule(a: Pick<Automation, "trigger_type" | "cron" | "interval_minutes" | "timezone" | "run_at">): string {
  const tz = a.timezone || "UTC";
  if (a.trigger_type === "once") return a.run_at ? `Once · ${formatInTz(a.run_at, tz)}` : "Once";
  if (a.trigger_type === "interval") {
    const m = a.interval_minutes;
    if (m % 1440 === 0) return m === 1440 ? "Every day" : `Every ${m / 1440} days`;
    if (m % 60 === 0) return m === 60 ? "Every hour" : `Every ${m / 60} hours`;
    return `Every ${m} minutes`;
  }
  if (a.trigger_type === "webhook") return "On webhook POST";
  if (a.trigger_type === "schedule") {
    const f = a.cron.trim().split(/\s+/);
    if (f.length === 5 && /^\d+$/.test(f[0]) && /^\d+$/.test(f[1]) && f[3] === "*") {
      const at = `${f[1].padStart(2, "0")}:${f[0].padStart(2, "0")}`;
      const [dom, dow] = [f[2], f[4]];
      if (dom === "*" && dow === "*") return `Every day at ${at} · ${tz}`;
      if (dom === "*" && dow === "1-5") return `Weekdays at ${at} · ${tz}`;
      if (dom === "*" && dow === "0,6") return `Weekends at ${at} · ${tz}`;
      if (dom === "*" && /^[0-6](,[0-6])*$/.test(dow)) return `${dow.split(",").map((d) => DAYS[+d]).join(", ")} at ${at} · ${tz}`;
      if (/^\d+$/.test(dom) && dow === "*") return `Monthly on day ${dom} at ${at} · ${tz}`;
    }
    return `Cron ${a.cron} · ${tz}`;
  }
  return "Manual / API";
}

export function formatInTz(iso: string, tz: string, opts: Intl.DateTimeFormatOptions = { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }): string {
  try {
    return new Date(iso).toLocaleString(undefined, { ...opts, timeZone: tz || "UTC" });
  } catch {
    return new Date(iso).toLocaleString(undefined, opts);
  }
}

/** Offset (ms) of `tz` from UTC at instant `ms`. */
function tzOffset(ms: number, tz: string): number {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }).formatToParts(new Date(ms));
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second")) - ms;
}

/** "2026-12-05T10:00" interpreted as wall-clock time in `tz` -> UTC ISO string. */
export function zonedLocalToIso(local: string, tz: string): string | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(local);
  if (!m) return null;
  const guess = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  try {
    let ms = guess - tzOffset(guess, tz);
    ms = guess - tzOffset(ms, tz); // second pass handles DST boundaries
    return new Date(ms).toISOString();
  } catch {
    return new Date(guess).toISOString();
  }
}

/** UTC ISO -> "YYYY-MM-DDTHH:mm" wall-clock value in `tz` (for <input type="datetime-local">). */
export function isoToZonedLocal(iso: string, tz: string): string {
  const ms = new Date(iso).getTime();
  let off = 0;
  try {
    off = tzOffset(ms, tz);
  } catch {
    /* keep UTC */
  }
  return new Date(ms + off).toISOString().slice(0, 16);
}

/** id -> name for every agent, team and workflow the user can see. */
export function useTargetNames(): Record<string, string> {
  const agents = useAgents();
  const teams = useTeams();
  const workflows = useWorkflows();
  return useMemo(() => {
    const m: Record<string, string> = {};
    for (const a of agents.data ?? []) m[a.id] = a.name;
    for (const t of teams.data ?? []) m[t.id] = t.name;
    for (const w of workflows.data ?? []) m[w.id] = w.name;
    return m;
  }, [agents.data, teams.data, workflows.data]);
}
