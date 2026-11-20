import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Bot, Calendar, Check, ChevronRight, Circle, CircleCheck, ListChecks, MessageSquare, Play, Plus, Sparkles, Trash2, WandSparkles } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Task, TaskPriority, TaskStatus } from "@/modules/tasks/types";
import { cn, errMsg, formatDate } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useAgents } from "@/modules/agents/api";
import { useTasks } from "@/modules/tasks/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, EmptyState, Input, PageLoader, Select, Tabs, Textarea } from "@/shared/ui/primitives";
import { ConfirmDialog } from "@/shared/ui/overlay";

type Filter = "open" | "done" | "all";

const SOURCE: Record<Task["source"], { label: string; icon: typeof Bot }> = {
  manual: { label: "Added by hand", icon: Plus },
  chat: { label: "From a chat reply", icon: MessageSquare },
  text: { label: "From text", icon: WandSparkles },
  agent: { label: "Created by an agent", icon: Bot },
};
const PRIORITY_TONE: Record<TaskPriority, "danger" | "muted" | "default"> = { high: "danger", normal: "default", low: "muted" };
const GROUPS: { status: TaskStatus; label: string }[] = [
  { status: "doing", label: "In progress" },
  { status: "todo", label: "To do" },
  { status: "done", label: "Done" },
];

const overdue = (t: Task) => !!t.due_at && t.status !== "done" && new Date(t.due_at).getTime() < Date.now();

export default function Tasks() {
  const { projectId, project, can } = useAuth();
  const tasks = useTasks(projectId);
  const [filter, setFilter] = useState<Filter>("open");
  const [quick, setQuick] = useState("");
  const nav = useNavigate();
  const [open, setOpen] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Task | null>(null);
  const inv = [["tasks"]];
  const writable = can("member");

  const add = useAction((title: string) => http.post<Task>("/tasks", { project_id: projectId, title }), { invalidate: inv, onSuccess: () => setQuick("") });
  const update = useAction((v: { id: string; patch: Partial<Task> }) => http.patch<Task>(`/tasks/${v.id}`, v.patch), { invalidate: inv });
  const del = useAction((id: string) => http.del(`/tasks/${id}`), { success: "Task deleted", invalidate: inv, onSuccess: () => setDeleting(null) });

  const all = tasks.data ?? [];
  const counts = { open: all.filter((t) => t.status !== "done").length, done: all.filter((t) => t.status === "done").length, all: all.length };
  const visible = useMemo(() => all.filter((t) => (filter === "open" ? t.status !== "done" : filter === "done" ? t.status === "done" : true)), [all, filter]);

  return (
    <Page>
      <PageHeader
        title="Tasks"
        description={project ? `To-dos for “${project.name}”. Agents here can read and create them, and you can hand any task to an agent together with its context.` : "To-dos for the active project."}
        actions={writable && <Button variant="outline" icon={<WandSparkles className="size-4" />} onClick={() => nav("/tasks/extract")}>Text to tasks</Button>}
      />

      {writable && (
        <form
          className="mb-5 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (quick.trim()) add.mutate(quick.trim());
          }}
        >
          <Input value={quick} onChange={(e) => setQuick(e.target.value)} placeholder="Add a task and press Enter" aria-label="New task" maxLength={255} />
          <Button type="submit" icon={<Plus className="size-4" />} loading={add.isPending} disabled={!quick.trim()}>Add</Button>
        </form>
      )}

      <Tabs
        className="mb-5"
        value={filter}
        onChange={setFilter}
        tabs={[
          { key: "open", label: "Open", count: counts.open },
          { key: "done", label: "Done", count: counts.done },
          { key: "all", label: "All", count: counts.all },
        ]}
      />

      {tasks.isLoading ? (
        <PageLoader />
      ) : !visible.length ? (
        <EmptyState
          icon={<ListChecks className="size-5" />}
          title={filter === "done" ? "Nothing completed yet" : "No open tasks"}
          description="Add one above, convert an AI answer with the checklist button in chat, or paste notes and let us pull out the action items."
          action={writable && <Button icon={<WandSparkles className="size-4" />} onClick={() => nav("/tasks/extract")}>Text to tasks</Button>}
        />
      ) : (
        <div className="space-y-6">
          {GROUPS.filter((g) => visible.some((t) => t.status === g.status)).map((g) => (
            <section key={g.status}>
              <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                {g.label} <span className="ml-1 rounded bg-surface-2 px-1.5 normal-case">{visible.filter((t) => t.status === g.status).length}</span>
              </h2>
              <div className="space-y-2">
                {visible
                  .filter((t) => t.status === g.status)
                  .map((t) => (
                    <TaskRow
                      key={t.id}
                      task={t}
                      expanded={open === t.id}
                      writable={writable}
                      onToggleOpen={() => setOpen(open === t.id ? null : t.id)}
                      onToggleDone={() => update.mutate({ id: t.id, patch: { status: t.status === "done" ? "todo" : "done" } })}
                      onPatch={(patch) => update.mutate({ id: t.id, patch })}
                      onDelete={() => setDeleting(t)}
                    />
                  ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} onConfirm={() => deleting && del.mutate(deleting.id)} loading={del.isPending} title="Delete this task?" description={deleting?.title} />
    </Page>
  );
}

function TaskRow({ task: t, expanded, writable, onToggleOpen, onToggleDone, onPatch, onDelete }: {
  task: Task;
  expanded: boolean;
  writable: boolean;
  onToggleOpen: () => void;
  onToggleDone: () => void;
  onPatch: (p: Partial<Task>) => void;
  onDelete: () => void;
}) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { project } = useAuth();
  const agents = useAgents();
  const [agentId, setAgentId] = useState(project?.settings.default_agent_id ?? "");
  const [notes, setNotes] = useState(t.notes);
  const [context, setContext] = useState(t.context);
  const [running, setRunning] = useState(false);
  const Source = SOURCE[t.source];
  const done = t.status === "done";

  const run = async () => {
    setRunning(true);
    try {
      const r = await http.post<{ run_id: string; agent_name: string }>(`/tasks/${t.id}/run`, { agent_id: agentId || undefined });
      toast.success(`${r.agent_name} is working on it`, { action: { label: "View run", onClick: () => nav(`/runs/${r.run_id}`) } });
      qc.invalidateQueries({ queryKey: ["tasks"] });
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card className={cn("overflow-hidden transition-colors", expanded && "border-indigo-500/30")}>
      <div className="flex items-start gap-3 p-3 sm:px-4">
        <button
          onClick={onToggleDone}
          disabled={!writable}
          aria-label={done ? "Mark as to do" : "Mark as done"}
          className="mt-0.5 shrink-0 cursor-pointer text-muted transition-colors hover:text-primary disabled:cursor-default"
        >
          {done ? <CircleCheck className="size-5 text-success" /> : <Circle className="size-5" />}
        </button>
        <button onClick={onToggleOpen} className="min-w-0 flex-1 cursor-pointer text-left" aria-expanded={expanded}>
          <div className={cn("text-sm font-medium", done && "text-muted line-through")}>{t.title}</div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {t.priority !== "normal" && <Badge tone={PRIORITY_TONE[t.priority]} className="capitalize">{t.priority}</Badge>}
            {t.due_at && (
              <Badge tone={overdue(t) ? "danger" : "muted"} icon={<Calendar className="size-3" />}>
                {overdue(t) ? "Overdue · " : ""}
                {new Date(t.due_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </Badge>
            )}
            <Badge tone="muted" icon={<Source.icon className="size-3" />}>{Source.label}</Badge>
            {t.context && <Badge tone="primary" icon={<Sparkles className="size-3" />}>Has context</Badge>}
          </div>
        </button>
        <ChevronRight className={cn("mt-1 size-4 shrink-0 text-muted transition-transform", expanded && "rotate-90")} aria-hidden />
      </div>

      {expanded && (
        <div className="space-y-4 border-t border-border bg-surface-2/30 px-4 py-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-xs font-medium text-muted">
              Status
              <Select disabled={!writable} value={t.status} onChange={(e) => onPatch({ status: e.target.value as TaskStatus })} className="mt-1">
                <option value="todo">To do</option>
                <option value="doing">In progress</option>
                <option value="done">Done</option>
              </Select>
            </label>
            <label className="text-xs font-medium text-muted">
              Priority
              <Select disabled={!writable} value={t.priority} onChange={(e) => onPatch({ priority: e.target.value as TaskPriority })} className="mt-1">
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
              </Select>
            </label>
            <label className="text-xs font-medium text-muted">
              Due
              <Input
                type="date"
                disabled={!writable}
                value={t.due_at ? t.due_at.slice(0, 10) : ""}
                onChange={(e) => onPatch({ due_at: e.target.value ? `${e.target.value}T17:00:00Z` : null })}
                className="mt-1"
              />
            </label>
          </div>
          <label className="block text-xs font-medium text-muted">
            Notes
            <Textarea disabled={!writable} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={() => notes !== t.notes && onPatch({ notes })} className="mt-1" />
          </label>
          <label className="block text-xs font-medium text-muted">
            Context <span className="font-normal">(given to an agent when you run this task)</span>
            <Textarea disabled={!writable} rows={4} value={context} onChange={(e) => setContext(e.target.value)} onBlur={() => context !== t.context && onPatch({ context })} className="mt-1" />
          </label>

          <div className="flex flex-wrap items-center gap-2">
            {writable && (
              <>
                <Select value={agentId} onChange={(e) => setAgentId(e.target.value)} className="h-9 w-48" aria-label="Agent to run this task">
                  <option value="">Default agent</option>
                  {(agents.data ?? []).map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </Select>
                <Button size="sm" icon={<Play className="size-3.5" />} loading={running} onClick={run}>Run with agent</Button>
              </>
            )}
            {t.run_id && (
              <Link to={`/runs/${t.run_id}`} className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                <Check className="size-3" /> Last run
              </Link>
            )}
            {t.conversation_id && (
              <Link to={`/chat/${t.conversation_id}`} className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
                <MessageSquare className="size-3" /> Open chat
              </Link>
            )}
            <span className="ml-auto text-[11px] text-muted">Added {formatDate(t.created_at)}</span>
            {writable && (
              <Button size="icon" variant="ghost" aria-label="Delete task" onClick={onDelete}>
                <Trash2 className="size-4 text-muted" />
              </Button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
