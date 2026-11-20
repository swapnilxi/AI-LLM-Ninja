/**
 * 14-day stacked column chart of runs (succeeded / failed / other).
 * Palette validated with the dataviz validator (adjacent CVD ΔE ≥ 11.8 both modes);
 * the dark-mode gray sits under 3:1, so a table view is provided as relief.
 */
import { useMemo, useState } from "react";
import { Table2, ChartColumn } from "lucide-react";
import { cn, formatNumber } from "@/shared/lib/utils";

export interface DayPoint {
  date: string;
  succeeded: number;
  failed: number;
  other: number;
  tokens: number;
}

const SERIES = [
  { key: "succeeded", label: "Succeeded", cls: "bg-[#2a78d6] dark:bg-[#3987e5]" },
  { key: "failed", label: "Failed", cls: "bg-[#d03b3b] dark:bg-[#e66767]" },
  { key: "other", label: "Other", cls: "bg-[#8b8f9c] dark:bg-[#5b6070]" },
] as const;

const PLOT_H = 168;
const GAP = 2;

function niceMax(v: number): number {
  if (v <= 4) return 4;
  const mag = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * mag >= v) return m * mag;
  return 10 * mag;
}

function dayLabel(iso: string, opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" }) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, opts);
}

export function RunsChart({ data }: { data: DayPoint[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const totals = data.map((d) => d.succeeded + d.failed + d.other);
  const max = niceMax(Math.max(0, ...totals));
  const ticks = useMemo(() => [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(max * f)), [max]);
  const empty = totals.every((t) => t === 0);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
          {SERIES.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className={cn("inline-block size-2.5 rounded-[3px]", s.cls)} aria-hidden />
              {s.label}
              {s.key === "other" && <span className="hidden text-muted/80 sm:inline">(queued · running · cancelled)</span>}
            </li>
          ))}
        </ul>
        <button
          onClick={() => setTable((t) => !t)}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted hover:bg-surface-2 hover:text-fg"
          aria-pressed={table}
        >
          {table ? <ChartColumn className="size-3.5" /> : <Table2 className="size-3.5" />}
          {table ? "Chart" : "Table"}
        </button>
      </div>

      {table ? (
        <div className="max-h-[260px] overflow-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-surface-2 text-xs text-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Day</th>
                {SERIES.map((s) => (
                  <th key={s.key} className="px-3 py-2 text-right font-medium">{s.label}</th>
                ))}
                <th className="px-3 py-2 text-right font-medium">Tokens</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {[...data].reverse().map((d) => (
                <tr key={d.date} className="border-t border-border">
                  <td className="px-3 py-1.5">{dayLabel(d.date, { weekday: "short", month: "short", day: "numeric" })}</td>
                  <td className="px-3 py-1.5 text-right">{d.succeeded}</td>
                  <td className="px-3 py-1.5 text-right">{d.failed}</td>
                  <td className="px-3 py-1.5 text-right">{d.other}</td>
                  <td className="px-3 py-1.5 text-right">{formatNumber(d.tokens)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex">
          {/* y axis */}
          <div className="relative mr-2 w-7 shrink-0 text-right text-[10px] tabular-nums text-muted" style={{ height: PLOT_H }} aria-hidden>
            {ticks.map((t) => (
              <span key={t} className="absolute right-0 -translate-y-1/2" style={{ bottom: (t / max) * PLOT_H - 0 }}>
                {formatNumber(t)}
              </span>
            ))}
          </div>
          <div className="min-w-0 flex-1">
            <div className="relative" style={{ height: PLOT_H }}>
              {/* hairline grid, baseline slightly stronger */}
              {ticks.map((t) => (
                <div key={t} className={cn("absolute inset-x-0 h-px", t === 0 ? "bg-muted/40" : "bg-border")} style={{ bottom: (t / max) * PLOT_H }} aria-hidden />
              ))}
              {empty && <div className="absolute inset-0 flex items-center justify-center text-xs text-muted">No runs in the last 14 days</div>}
              <div className="absolute inset-0 flex" role="list" aria-label="Runs per day, last 14 days">
                {data.map((d, i) => {
                  let y = 0;
                  const segs = SERIES.map((s) => {
                    const v = d[s.key];
                    const h = (v / max) * PLOT_H;
                    const seg = { ...s, v, bottom: y, h };
                    y += h;
                    return seg;
                  }).filter((s) => s.v > 0);
                  const total = totals[i];
                  const showTipLeft = i > data.length / 2;
                  return (
                    <div
                      key={d.date}
                      role="listitem"
                      tabIndex={0}
                      aria-label={`${dayLabel(d.date)}: ${total} runs, ${d.succeeded} succeeded, ${d.failed} failed, ${d.other} other`}
                      onPointerEnter={() => setHover(i)}
                      onPointerLeave={() => setHover((h) => (h === i ? null : h))}
                      onFocus={() => setHover(i)}
                      onBlur={() => setHover(null)}
                      className="group relative h-full flex-1 cursor-default outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                    >
                      <div className={cn("absolute inset-x-0.5 inset-y-0 rounded-md transition-colors", hover === i && "bg-surface-2/70")} aria-hidden />
                      <div className="absolute inset-x-0 bottom-0 mx-auto h-full w-[62%] max-w-[24px]">
                        {segs.map((s, si) => {
                          const top = si === segs.length - 1;
                          const gap = si > 0 ? GAP : 0;
                          return (
                            <div
                              key={s.key}
                              className={cn("absolute inset-x-0 transition-[filter]", s.cls, top && "rounded-t-[4px]", hover === i && "brightness-110")}
                              style={{ bottom: s.bottom + gap, height: Math.max(s.h - gap, 1.5) }}
                              aria-hidden
                            />
                          );
                        })}
                      </div>
                      {hover === i && (
                        <div
                          className={cn(
                            "pointer-events-none absolute z-10 w-40 rounded-lg border border-border bg-surface p-2.5 text-xs shadow-lg",
                            showTipLeft ? "right-1/2" : "left-1/2",
                          )}
                          style={{ bottom: Math.min(PLOT_H - 40, (total / max) * PLOT_H + 8) }}
                          role="tooltip"
                        >
                          <div className="mb-1.5 font-medium text-muted">{dayLabel(d.date, { weekday: "short", month: "short", day: "numeric" })}</div>
                          {SERIES.map((s) => (
                            <div key={s.key} className="flex items-center gap-2 py-0.5">
                              <span className={cn("h-0.5 w-3 rounded-full", s.cls)} aria-hidden />
                              <span className="font-semibold tabular-nums text-fg">{d[s.key]}</span>
                              <span className="text-muted">{s.label.toLowerCase()}</span>
                            </div>
                          ))}
                          <div className="mt-1.5 border-t border-border pt-1.5 text-muted">
                            <span className="font-semibold text-fg">{formatNumber(d.tokens)}</span> tokens
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            {/* x labels: every other day on narrow screens */}
            <div className="mt-2 flex text-[10px] text-muted" aria-hidden>
              {data.map((d, i) => (
                <div key={d.date} className={cn("flex-1 truncate text-center", i % 2 === 1 && "max-sm:invisible")}>
                  {dayLabel(d.date, { day: "numeric" })}
                  {(i === 0 || new Date(`${d.date}T00:00:00`).getDate() === 1) && <span className="hidden sm:inline"> {dayLabel(d.date, { month: "short" })}</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
