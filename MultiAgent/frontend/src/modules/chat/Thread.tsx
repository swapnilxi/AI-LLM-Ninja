import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronLeft, Copy, Ellipsis, ExternalLink, ListChecks, ListTree, LoaderCircle, Pencil, Sparkles, ThumbsDown, ThumbsUp, Trash2, Users } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Agent, ChatMessage, Conversation, Run, RunEvent, Team } from "@/lib/types";
import { cn, errMsg, formatNumber, timeAgo } from "@/lib/utils";
import { useAgents, useSkillCommands, useTeams } from "@/hooks/useData";
import { useRunStream } from "@/hooks/useRunStream";
import { ConfirmDialog, Dialog, Menu, MenuItem } from "@/components/ui/overlay";
import { Badge, Button, Input, PageLoader } from "@/components/ui/primitives";
import { Markdown } from "@/components/ui/Markdown";
import { AgentAvatar, IconTile } from "@/components/ui/icons";
import { RunTimeline } from "@/components/run/RunTimeline";
import { ExtractTasksDialog } from "@/components/tasks/ExtractTasksDialog";
import { Composer, type BuiltinCommand } from "./Composer";
import { CommandsHelpDialog, ConversationSkillsDialog } from "./ChatDialogs";

const SUGGESTIONS = [
  "Search the web for the latest news on AI agents and summarize the top 3 stories with sources",
  "What do the project documents say about our goals and constraints?",
  "Remember that our launch date is the first Monday of next month",
  "Calculate the compound growth of 12,000 at 7% per year for 5 years",
];

function statusLine(events: RunEvent[]): string {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.type === "tool_call") return `Using ${e.data.name}…`;
    if (e.type === "tool_result") return `Reading ${e.data.name} results…`;
    if (e.type === "agent_start") return `${e.agent} is thinking…`;
    if (e.type === "route") return `Routing to ${e.data.choice}…`;
    if (e.type === "team_message") return `${e.data.from} replied — continuing…`;
    if (e.type === "node_start") return `Running ${e.data.label}…`;
  }
  return "Thinking…";
}

export function Thread({ conversationId }: { conversationId: string }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { projectId, can } = useAuth();
  const agents = useAgents();
  const teams = useTeams();
  const conv = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => http.get<{ conversation: Conversation; messages: ChatMessage[] }>(`/conversations/${conversationId}`),
  });
  const [pendingRun, setPendingRun] = useState<string | null>(null);
  const [sendingText, setSendingText] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [suggestion, setSuggestion] = useState<string>("");
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [tasksFor, setTasksFor] = useState<ChatMessage | null>(null);
  const commands = useSkillCommands();
  const scrollRef = useRef<HTMLDivElement>(null);

  const messages = conv.data?.messages ?? [];
  const last = messages[messages.length - 1];
  const detectedRun = last && last.role === "user" && last.run_id ? last.run_id : null;
  const activeRunId = pendingRun ?? detectedRun;
  const stream = useRunStream(activeRunId);
  const running = !!activeRunId && !stream.done;

  useEffect(() => {
    setPendingRun(null);
    setSendingText(null);
  }, [conversationId]);

  useEffect(() => {
    if (stream.done && activeRunId) {
      qc.invalidateQueries({ queryKey: ["conversation", conversationId] }).then(() => setPendingRun(null));
      qc.invalidateQueries({ queryKey: ["conversations"] });
    }
  }, [stream.done, activeRunId, conversationId, qc]);

  const liveEntries = Object.entries(stream.live);
  const liveText = liveEntries.length ? liveEntries[liveEntries.length - 1] : null;

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, sendingText, liveText?.[1]?.length, stream.events.length]);

  const c = conv.data?.conversation;
  const target = useMemo(() => {
    if (!c) return null;
    return c.target_type === "agent" ? (agents.data ?? []).find((a) => a.id === c.target_id) ?? null : (teams.data ?? []).find((t) => t.id === c.target_id) ?? null;
  }, [c, agents.data, teams.data]);

  const send = async (text: string) => {
    setSending(true);
    setSendingText(text);
    try {
      const res = await http.post<{ message: ChatMessage; run: Run }>(`/conversations/${conversationId}/messages`, { content: text });
      setPendingRun(res.run.id);
      await qc.invalidateQueries({ queryKey: ["conversation", conversationId] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSendingText(null);
      setSending(false);
    }
  };

  const stop = async () => {
    if (!activeRunId) return;
    try {
      await http.post(`/runs/${activeRunId}/cancel`);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const rename = async () => {
    try {
      await http.patch(`/conversations/${conversationId}`, { title });
      qc.invalidateQueries({ queryKey: ["conversation", conversationId] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
      setRenaming(false);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const feedback = async (m: ChatMessage, rating: "up" | "down") => {
    const current = m.meta?.feedback?.rating;
    try {
      await http.patch(`/conversations/${conversationId}/messages/${m.id}`, { feedback: current === rating ? null : rating });
      qc.invalidateQueries({ queryKey: ["conversation", conversationId] });
      if (current !== rating) toast.success(rating === "up" ? "Thanks for the feedback" : "Feedback saved — we'll use it to improve");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const copy = async (m: ChatMessage) => {
    try {
      await navigator.clipboard.writeText(m.content);
      setCopied(m.id);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      toast.error("Clipboard not available");
    }
  };

  const onBuiltin = (cmd: BuiltinCommand) => {
    if (cmd === "skills") setSkillsOpen(true);
    else if (cmd === "help") setHelpOpen(true);
    else if (c) nav(`/chat?${c.target_type}=${c.target_id}`);
  };

  const remove = async () => {
    try {
      await http.del(`/conversations/${conversationId}`);
      qc.invalidateQueries({ queryKey: ["conversations"] });
      nav("/chat");
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  if (conv.isLoading) return <PageLoader />;
  if (!c) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-muted">This conversation could not be found.</p>
        <Button variant="outline" onClick={() => nav("/chat")}>Back to chats</Button>
      </div>
    );
  }
  const otherProject = projectId && c.project_id !== projectId;
  const avatar = c.target_type === "agent" ? <AgentAvatar agent={target as Agent | null} size="sm" /> : <IconTile icon={Users} color="violet" size="sm" />;
  const assistantAvatar = c.target_type === "agent" ? <AgentAvatar agent={target as Agent | null} size="xs" /> : <IconTile icon={Users} color="violet" size="xs" />;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-2 sm:px-4">
        <button onClick={() => nav("/chat")} className="cursor-pointer rounded-lg p-2 text-muted hover:bg-surface-2 md:hidden" aria-label="Back to chats">
          <ChevronLeft className="size-5" />
        </button>
        {avatar}
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">{c.title}</div>
          <div className="flex items-center gap-1.5 truncate text-xs text-muted">
            {target?.name ?? "Unknown target"}
            <Badge tone="muted" className="capitalize">{c.target_type}</Badge>
            {(target as Team | null)?.style && <span className="hidden sm:inline">· {(target as Team).style.replace("_", " ")}</span>}
          </div>
        </div>
        <button
          onClick={() => setSkillsOpen(true)}
          title="Skills for this chat"
          className={cn(
            "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium",
            (c.skill_ids?.length ?? 0) > 0 ? "border-indigo-500/30 bg-primary-soft text-primary" : "border-border text-muted hover:bg-surface-2 hover:text-fg",
          )}
        >
          <Sparkles className="size-3.5" />
          <span className="hidden sm:inline">Skills</span>
          {(c.skill_ids?.length ?? 0) > 0 && <span>{c.skill_ids!.length}</span>}
        </button>
        <Menu
          trigger={
            <button className="cursor-pointer rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Conversation options">
              <Ellipsis className="size-5" />
            </button>
          }
        >
          {(close) => (
            <>
              <MenuItem
                icon={<Pencil className="size-4" />}
                onClick={() => {
                  close();
                  setTitle(c.title);
                  setRenaming(true);
                }}
              >
                Rename
              </MenuItem>
              {target && (
                <MenuItem
                  icon={<ExternalLink className="size-4" />}
                  onClick={() => {
                    close();
                    nav(c.target_type === "agent" ? `/agents/${c.target_id}` : `/teams/${c.target_id}`);
                  }}
                >
                  Open {c.target_type}
                </MenuItem>
              )}
              <MenuItem
                danger
                icon={<Trash2 className="size-4" />}
                onClick={() => {
                  close();
                  setDeleting(true);
                }}
              >
                Delete
              </MenuItem>
            </>
          )}
        </Menu>
      </div>

      {otherProject && (
        <div className="border-b border-amber-500/20 bg-amber-500/5 px-4 py-2 text-xs text-muted">This conversation belongs to a different project than the one currently active; it keeps using its own project's context.</div>
      )}

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-5 px-3 py-6 sm:px-6">
          {messages.length === 0 && !sendingText && (
            <div className="py-8 text-center">
              <div className="mx-auto mb-3 flex justify-center">{c.target_type === "agent" ? <AgentAvatar agent={target as Agent | null} size="lg" /> : <IconTile icon={Users} color="violet" size="lg" />}</div>
              <h2 className="text-lg font-semibold">Chat with {target?.name ?? "the assistant"}</h2>
              <p className="mx-auto mt-1 max-w-md text-sm text-muted">{target?.description || "Ask anything. Answers use your project's brief, documents, memory and tools."}</p>
              <div className="mx-auto mt-6 grid max-w-2xl gap-2 text-left sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSuggestion(s)}
                    className="cursor-pointer rounded-xl border border-border bg-surface p-3 text-sm text-muted transition-colors hover:border-indigo-500/30 hover:text-fg"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-sm text-white shadow-sm shadow-indigo-500/20 dark:text-[#0b0d12]">
                  <UserText text={m.content} />
                </div>
              </div>
            ) : (
              <div key={m.id} className="flex gap-3">
                <div className="pt-0.5">{assistantAvatar}</div>
                <div className="min-w-0 flex-1">
                  <div className={cn("rounded-2xl rounded-tl-md border border-border bg-surface px-4 py-3", m.meta?.status && m.meta.status !== "succeeded" && "border-red-500/30 bg-red-500/5")}>
                    <Markdown>{m.content}</Markdown>
                  </div>
                  <div className="mt-1 flex items-center gap-3 px-1 text-[11px] text-muted">
                    {timeAgo(m.created_at)}
                    {m.meta?.usage && <span>{formatNumber((m.meta.usage.input_tokens ?? 0) + (m.meta.usage.output_tokens ?? 0))} tokens · {m.meta.usage.tool_calls ?? 0} tool call{(m.meta.usage.tool_calls ?? 0) === 1 ? "" : "s"}</span>}
                    {m.run_id && (
                      <Link to={`/runs/${m.run_id}`} className="inline-flex items-center gap-1 hover:text-fg">
                        <ListTree className="size-3" /> Steps
                      </Link>
                    )}
                    <span className="ml-auto flex items-center gap-0.5">
                      <button onClick={() => copy(m)} className="cursor-pointer rounded-md p-1 hover:bg-surface-2 hover:text-fg" aria-label="Copy answer" title="Copy">
                        {copied === m.id ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
                      </button>
                      {can("member") && (
                        <button onClick={() => setTasksFor(m)} className="cursor-pointer rounded-md p-1 hover:bg-surface-2 hover:text-fg" aria-label="Turn into tasks" title="Turn into tasks">
                          <ListChecks className="size-3.5" />
                        </button>
                      )}
                      <button
                        onClick={() => feedback(m, "up")}
                        className={cn("cursor-pointer rounded-md p-1 hover:bg-surface-2 hover:text-fg", m.meta?.feedback?.rating === "up" && "text-success")}
                        aria-label="Good answer"
                        aria-pressed={m.meta?.feedback?.rating === "up"}
                        title="Good answer"
                      >
                        <ThumbsUp className="size-3.5" />
                      </button>
                      <button
                        onClick={() => feedback(m, "down")}
                        className={cn("cursor-pointer rounded-md p-1 hover:bg-surface-2 hover:text-fg", m.meta?.feedback?.rating === "down" && "text-danger")}
                        aria-label="Bad answer"
                        aria-pressed={m.meta?.feedback?.rating === "down"}
                        title="Bad answer"
                      >
                        <ThumbsDown className="size-3.5" />
                      </button>
                    </span>
                  </div>
                </div>
              </div>
            ),
          )}

          {sendingText && (
            <div className="flex justify-end">
              <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-sm text-white opacity-70 dark:text-[#0b0d12]">{sendingText}</div>
            </div>
          )}

          {(running || (sending && !activeRunId)) && (
            <div className="flex gap-3">
              <div className="pt-0.5">{assistantAvatar}</div>
              <div className="min-w-0 flex-1">
                <div className="rounded-2xl rounded-tl-md border border-border bg-gradient-to-br from-primary-soft/40 to-surface px-4 py-3">
                  {liveText && liveText[1] ? (
                    <>
                      {c.target_type === "team" && <div className="mb-1 text-xs font-medium text-muted">{liveText[0]}</div>}
                      <Markdown>{liveText[1]}</Markdown>
                    </>
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-muted">
                      <LoaderCircle className="size-4 animate-spin text-primary" />
                      {statusLine(stream.events)}
                    </div>
                  )}
                </div>
                {stream.events.length > 0 && (
                  <details className="mt-1.5 px-1">
                    <summary className="cursor-pointer text-[11px] font-medium text-muted hover:text-fg">Steps ({stream.events.filter((e) => e.type === "tool_call").length} tool calls)</summary>
                    <div className="mt-2 rounded-xl border border-border bg-surface p-3">
                      <RunTimeline events={stream.events} />
                    </div>
                  </details>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <Composer
        disabled={!can("member")}
        busy={running || sending}
        onSend={send}
        onStop={running ? stop : undefined}
        initial={suggestion}
        commands={commands.data ?? []}
        onBuiltin={onBuiltin}
      />
      <ConversationSkillsDialog open={skillsOpen} onClose={() => setSkillsOpen(false)} conversation={c} />
      <CommandsHelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} commands={commands.data ?? []} onPick={(cmd) => setSuggestion((prev) => (prev === cmd ? `${cmd} ` : cmd))} />

      {tasksFor && <ExtractTasksDialog open onClose={() => setTasksFor(null)} projectId={c.project_id} initialText={tasksFor.content} conversationId={conversationId} messageId={tasksFor.id} />}
      <Dialog
        open={renaming}
        onClose={() => setRenaming(false)}
        title="Rename conversation"
        size="sm"
        footer={
          <>
            <Button variant="outline" onClick={() => setRenaming(false)}>Cancel</Button>
            <Button onClick={rename} disabled={!title.trim()}>Save</Button>
          </>
        }
      >
        <Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Enter" && title.trim() && rename()} />
      </Dialog>
      <ConfirmDialog open={deleting} onClose={() => setDeleting(false)} onConfirm={remove} title="Delete this conversation?" description="All messages in it will be removed. Run history is kept." />
    </div>
  );
}

/** Renders a user message, highlighting a leading /command. */
function UserText({ text }: { text: string }) {
  const m = /^(\/[\w-]+)(\s[\s\S]*)?$/.exec(text);
  if (!m) return <>{text}</>;
  return (
    <>
      <span className="mr-1 rounded-md bg-white/20 px-1.5 py-0.5 font-mono text-[12px] font-medium dark:bg-black/15">{m[1]}</span>
      {m[2]?.trimStart()}
    </>
  );
}
