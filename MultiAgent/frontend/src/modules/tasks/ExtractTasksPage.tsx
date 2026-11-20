import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, ListChecks, Sparkles, WandSparkles } from "lucide-react";
import { toast } from "sonner";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { ChatMessage, Conversation } from "@/modules/chat/types";
import type { Task, TaskExtraction, TaskPriority } from "@/modules/tasks/types";
import { cn, errMsg } from "@/shared/lib/utils";
import { useReturnTo } from "@/shared/hooks/useReturnTo";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, Checkbox, EmptyState, Field, Input, PageLoader, Select, Textarea } from "@/shared/ui/primitives";
import { IconTile } from "@/shared/ui/icons";

interface Row {
  key: number;
  selected: boolean;
  title: string;
  notes: string;
  priority: TaskPriority;
  due: string; // yyyy-mm-dd or ""
}

/**
 * /tasks/extract: "Text to tasks". Paste text, review the to-dos found, add context, save.
 * /tasks/extract?conversation=<id>&message=<id> converts one chat reply and links the saved tasks back to it.
 * Accepts ?return_to=<path> (defaults to /tasks).
 */
export default function ExtractTasksPage() {
  const [params] = useSearchParams();
  const conversationId = params.get("conversation") ?? undefined;
  const messageId = params.get("message") ?? undefined;
  const fromChat = !!(conversationId && messageId);
  const back = useReturnTo(fromChat ? `/chat/${conversationId}` : "/tasks");
  const { projectId: activeProject } = useAuth();
  const conv = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => http.get<{ conversation: Conversation; messages: ChatMessage[] }>(`/conversations/${conversationId}`),
    enabled: fromChat,
  });
  if (fromChat && conv.isLoading) return <PageLoader />;
  const message = conv.data?.messages.find((m) => m.id === messageId);
  const projectId = fromChat ? conv.data?.conversation.project_id : activeProject;
  if (fromChat && !message)
    return (
      <Page className="max-w-3xl">
        <PageHeader back={back} title="Turn a reply into tasks" />
        <EmptyState icon={<ListChecks className="size-5" />} title="Message not found" description="The chat reply may have been deleted, or it belongs to another organization." />
      </Page>
    );
  if (!projectId)
    return (
      <Page className="max-w-3xl">
        <PageHeader back={back} title="Text to tasks" />
        <EmptyState icon={<ListChecks className="size-5" />} title="No project selected" description="Pick a project in the header first; tasks belong to a project." />
      </Page>
    );
  return (
    <Extractor
      key={`${projectId}:${messageId ?? ""}`}
      projectId={projectId}
      back={back}
      initialText={message?.content ?? ""}
      conversationId={fromChat ? conversationId : undefined}
      messageId={fromChat ? messageId : undefined}
    />
  );
}

function Extractor({ projectId, back, initialText, conversationId, messageId }: { projectId: string; back: string; initialText: string; conversationId?: string; messageId?: string }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [step, setStep] = useState<"input" | "review">("input");
  const [text, setText] = useState(initialText);
  const [context, setContext] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [shared, setShared] = useState("");
  const [engine, setEngine] = useState<"ai" | "rules">("rules");
  const [busy, setBusy] = useState(false);
  const fromChat = !!(conversationId && messageId);
  const started = useRef(false);
  const onClose = () => nav(back);

  const find = async (t = text, ctx = context) => {
    setBusy(true);
    try {
      const r = await http.post<TaskExtraction>("/tasks/extract", {
        project_id: projectId,
        text: fromChat ? "" : t,
        context: ctx,
        conversation_id: fromChat ? conversationId : undefined,
        message_id: fromChat ? messageId : undefined,
      });
      setEngine(r.engine);
      setShared(r.context);
      setRows(r.items.map((i, n) => ({ key: n, selected: true, title: i.title, notes: i.notes, priority: i.priority, due: i.due_at ? i.due_at.slice(0, 10) : "" })));
      setStep("review");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (fromChat && !started.current) {
      started.current = true;
      setStep("review");
      void find(initialText, "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chosen = rows.filter((r) => r.selected && r.title.trim());
  const patch = (key: number, p: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));

  const save = async () => {
    setBusy(true);
    try {
      const res = await http.post<{ created: Task[]; skipped: string[] }>("/tasks/bulk", {
        project_id: projectId,
        items: chosen.map((r) => ({ title: r.title.trim(), notes: r.notes, priority: r.priority, due_at: r.due ? `${r.due}T17:00:00Z` : null })),
        context: shared,
        conversation_id: fromChat ? conversationId : undefined,
        message_id: fromChat ? messageId : undefined,
        source: fromChat ? "chat" : "text",
      });
      const dup = res.skipped.length ? ` (${res.skipped.length} already on your list)` : "";
      res.created.length ? toast.success(`Added ${res.created.length} task${res.created.length === 1 ? "" : "s"}${dup}`) : toast.info(`Nothing new to add${dup}`);
      qc.invalidateQueries({ queryKey: ["tasks"] });
      onClose();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const footer =
    step === "input" ? (
      <>
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button icon={<WandSparkles className="size-4" />} loading={busy} disabled={!text.trim()} onClick={() => find()}>
          Find tasks
        </Button>
      </>
    ) : (
      <>
        {!fromChat && (
          <Button variant="ghost" icon={<ArrowLeft className="size-4" />} onClick={() => setStep("input")} className="mr-auto">
            Back
          </Button>
        )}
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button loading={busy} disabled={!chosen.length} onClick={save}>
          Add {chosen.length || ""} task{chosen.length === 1 ? "" : "s"}
        </Button>
      </>
    );

  return (
    <Page className="max-w-3xl">
      <PageHeader
        back={back}
        icon={<IconTile icon={ListChecks} color="indigo" />}
        title={fromChat ? "Turn this reply into tasks" : "Text to tasks"}
        description={step === "input" ? "Paste notes, an email or an answer. We pull out the action items so you can review them." : "Review, edit and pick the ones to keep."}
      />
      <Card>
        <div className="p-4 sm:p-5">
          {step === "input" ? (
            <div className="space-y-4">
              <Field label="Text">
                <Textarea
                  autoFocus
                  rows={9}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={"Next steps:\n- Draft the announcement email by Friday\n- Ask legal to review the terms"}
                />
              </Field>
              <Field
                label="Context (optional)"
                hint="Background that travels with every task, so whoever picks one up (you or an agent) knows the why. Example: “Launch is 1 March, audience is EU retailers.”"
              >
                <Textarea rows={3} value={context} onChange={(e) => setContext(e.target.value)} />
              </Field>
            </div>
          ) : busy && !rows.length ? (
            <div className="py-10 text-center text-sm text-muted">Finding action items…</div>
          ) : !rows.length ? (
            <div className="py-10 text-center">
              <p className="text-sm font-medium">No action items found</p>
              <p className="mx-auto mt-1 max-w-sm text-sm text-muted">There was nothing here that someone still has to do. You can add a task by hand on the Tasks page.</p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-2 text-xs text-muted">
                <span>{rows.length} found</span>
                <Badge tone={engine === "ai" ? "primary" : "muted"} icon={<Sparkles className="size-3" />}>
                  {engine === "ai" ? "Found with AI" : "Found with rules (offline model)"}
                </Badge>
              </div>
              <ul className="space-y-2">
                {rows.map((r) => (
                  <li key={r.key} className={cn("rounded-xl border border-border p-3 transition-opacity", !r.selected && "opacity-50")}>
                    <div className="flex items-start gap-3">
                      <Checkbox checked={r.selected} onChange={(v) => patch(r.key, { selected: v })} className="mt-2" />
                      <div className="min-w-0 flex-1 space-y-2">
                        <Input value={r.title} onChange={(e) => patch(r.key, { title: e.target.value })} aria-label="Task title" />
                        <div className="flex flex-wrap gap-2">
                          <Select value={r.priority} onChange={(e) => patch(r.key, { priority: e.target.value as TaskPriority })} className="h-8 w-28 text-xs" aria-label="Priority">
                            <option value="low">Low</option>
                            <option value="normal">Normal</option>
                            <option value="high">High</option>
                          </Select>
                          <Input type="date" value={r.due} onChange={(e) => patch(r.key, { due: e.target.value })} className="h-8 w-40 text-xs" aria-label="Due date" />
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
              <Field label="Context saved with these tasks" hint="Shown on each task and given to the agent when you run it.">
                <Textarea rows={4} value={shared} onChange={(e) => setShared(e.target.value)} />
              </Field>
            </div>
          )}
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">{footer}</div>
      </Card>
    </Page>
  );
}
