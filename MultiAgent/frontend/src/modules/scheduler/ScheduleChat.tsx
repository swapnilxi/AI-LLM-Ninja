/** Schedule by chatting: a short conversation with the scheduling assistant builds a draft you confirm. */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUp, CalendarClock, ClipboardList, RotateCcw, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { cn, errMsg } from "@/shared/lib/utils";
import { useQueryClient } from "@tanstack/react-query";
import { Badge, Button, Card, Textarea } from "@/shared/ui/primitives";
import { IconTile } from "@/shared/ui/icons";
import { Markdown } from "@/shared/ui/Markdown";
import { formatInTz, localTz, triggerMeta } from "./lib";
import type { AssistantReply, Automation, ChatTurn, ScheduleDraft } from "./types";

const GREETING = "Hi! Tell me what you'd like an agent to do and when, for example **“every weekday at 9am summarise my open GitHub PRs”** or **“tomorrow at 3pm remind me to send the invoice”**. I'll ask for anything missing.";
const SUGGESTIONS = [
  "Every weekday at 9am summarise my open GitHub pull requests",
  "Tomorrow at 3pm remind me to send the invoice",
  "Every 2 hours check the status page and report incidents",
  "Monthly on the 1st draft the investor update",
];

interface State {
  messages: ChatTurn[];
  draft: ScheduleDraft | null;
  ready: boolean;
  engine?: "ai" | "rules";
}
const EMPTY: State = { messages: [], draft: null, ready: false };

function load(key: string): State {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

export function ScheduleChat() {
  const { projectId, can } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const key = `af:schedule-chat:${projectId ?? "none"}`;
  const [state, setState] = useState<State>(() => load(key));
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const tz = localTz();

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(state));
    } catch {
      /* storage unavailable: the chat just won't survive a reload */
    }
  }, [key, state]);
  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }), [state.messages.length, busy]);

  const reset = () => {
    setState(EMPTY);
    setText("");
  };

  const create = async (d: ScheduleDraft) => {
    setCreating(true);
    try {
      const a = await http.post<Automation>("/schedules", {
        project_id: projectId,
        name: d.name || d.task.slice(0, 80),
        target_type: d.target_type,
        target_id: d.target_id,
        input: { task: d.task },
        trigger_type: d.trigger_type,
        cron: d.cron,
        interval_minutes: d.interval_minutes,
        run_at: d.run_at,
        timezone: d.timezone,
        source: "chat",
      });
      qc.invalidateQueries({ queryKey: ["schedules"] });
      toast.success(`Scheduled “${a.name}”`);
      try {
        sessionStorage.removeItem(key);
      } catch {
        /* ignore */
      }
      nav(`/scheduler/${a.id}`);
    } catch (e) {
      toast.error(errMsg(e));
      setState((s) => ({ ...s, messages: [...s.messages, { role: "assistant", content: `I couldn't create it: ${errMsg(e)}` }] }));
    } finally {
      setCreating(false);
    }
  };

  const send = async (raw: string) => {
    const content = raw.trim();
    if (!content || busy || !projectId) return;
    const messages: ChatTurn[] = [...state.messages, { role: "user", content }];
    setState((s) => ({ ...s, messages }));
    setText("");
    setBusy(true);
    try {
      const r = await http.post<AssistantReply>("/schedules/assistant", { project_id: projectId, messages: messages.slice(-30), draft: state.draft, timezone: tz });
      setState({ messages: [...messages, { role: "assistant", content: r.reply }], draft: r.draft, ready: r.ready, engine: r.engine });
      if (r.action === "create" && r.draft) await create(r.draft);
    } catch (e) {
      setState((s) => ({ ...s, messages: [...messages, { role: "assistant", content: `Something went wrong: ${errMsg(e)}` }] }));
    } finally {
      setBusy(false);
    }
  };

  const d = state.draft;
  const trig = d ? triggerMeta(d.trigger_type) : null;

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
      <Card className="flex min-h-[520px] flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto p-4 sm:p-5">
          <Bubble role="assistant" content={GREETING} />
          {state.messages.map((m, i) => (
            <Bubble key={i} role={m.role} content={m.content} />
          ))}
          {busy && <div className="flex items-center gap-2 pl-10 text-xs text-muted"><span className="size-1.5 animate-pulse rounded-full bg-primary" /> Thinking…</div>}
          {!state.messages.length && (
            <div className="flex flex-wrap gap-2 pl-10 pt-1">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)} className="cursor-pointer rounded-full border border-border px-3 py-1.5 text-left text-xs text-muted transition-colors hover:border-primary/40 hover:text-fg">
                  {s}
                </button>
              ))}
            </div>
          )}
          <div ref={endRef} />
        </div>
        <div className="border-t border-border p-3">
          <div className="flex items-end gap-2">
            <Textarea
              rows={2}
              value={text}
              disabled={!can("member") || !projectId}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(text);
                }
              }}
              placeholder={state.ready ? "Say “yes” to create it, or tell me what to change…" : "What should run, and when?"}
              className="resize-none"
              aria-label="Message the scheduling assistant"
            />
            <Button size="icon" onClick={() => send(text)} disabled={!text.trim() || busy} aria-label="Send">
              <ArrowUp className="size-4" />
            </Button>
          </div>
          <div className="mt-1.5 flex items-center justify-between text-[11px] text-muted">
            <span>Enter to send · Shift+Enter for a new line · times in {tz}</span>
            {state.messages.length > 0 && (
              <button onClick={reset} className="inline-flex cursor-pointer items-center gap-1 hover:text-fg">
                <RotateCcw className="size-3" /> Start over
              </button>
            )}
          </div>
        </div>
      </Card>

      <div className="space-y-3 lg:sticky lg:top-4 lg:self-start">
        <Card className="overflow-hidden">
          <div className="border-b border-border bg-gradient-to-br from-primary-soft/60 to-transparent px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold">Draft</span>
              {state.engine && <Badge tone={state.engine === "ai" ? "primary" : "muted"} icon={<Sparkles className="size-3" />}>{state.engine === "ai" ? "AI" : "Rules"}</Badge>}
            </div>
          </div>
          {!d ? (
            <div className="flex flex-col items-center gap-2 px-4 py-10 text-center text-sm text-muted">
              <CalendarClock className="size-6" />
              The schedule appears here as you chat.
            </div>
          ) : (
            <div className="space-y-3 p-4 text-sm">
              <Row label="Name">{d.name || "—"}</Row>
              <Row label="Task">{d.task || <span className="text-warning">Not set yet</span>}</Row>
              <Row label="Runs as">{d.target_name}</Row>
              <Row label="When">
                {d.trigger_type === "manual" ? (
                  <span className="text-warning">Not set yet</span>
                ) : (
                  <span className="inline-flex items-center gap-1.5">
                    {trig && <IconTile icon={trig.icon} color={trig.color} size="xs" />} {d.summary}
                  </span>
                )}
              </Row>
              {d.next_runs.length > 0 && (
                <Row label={d.trigger_type === "once" ? "Runs at" : "Next runs"}>
                  <ul className="space-y-0.5 text-xs">
                    {d.next_runs.map((r) => (
                      <li key={r}>{formatInTz(r, tz)}</li>
                    ))}
                  </ul>
                </Row>
              )}
              {d.notes.map((n) => (
                <p key={n} className="text-xs text-muted">{n}</p>
              ))}
              <div className="flex flex-col gap-2 pt-1">
                <Button disabled={!state.ready || !can("member")} loading={creating} onClick={() => d && create(d)}>
                  Create schedule
                </Button>
                <Button variant="outline" icon={<ClipboardList className="size-4" />} onClick={() => nav("/scheduler/new/form", { state: { draft: d } })}>
                  Edit in form
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 break-words">{children}</div>
    </div>
  );
}

function Bubble({ role, content }: ChatTurn) {
  const mine = role === "user";
  return (
    <div className={cn("flex gap-2.5", mine && "flex-row-reverse")}>
      {!mine && <IconTile icon={CalendarClock} color="indigo" size="sm" />}
      <div className={cn("max-w-[85%] rounded-2xl px-3.5 py-2 text-sm", mine ? "bg-primary text-white" : "bg-surface-2")}>
        {mine ? <span className="whitespace-pre-wrap">{content}</span> : <Markdown className="prose-sm">{content}</Markdown>}
      </div>
    </div>
  );
}
