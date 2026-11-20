import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Check, CheckCheck, MessageSquareText, Pencil, Wand2, X } from "lucide-react";
import { http } from "@/shared/lib/api";
import { timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Select, Spinner, Textarea } from "@/shared/ui/primitives";
import type { TabProps } from "../AgentTraining";
import { trainingKeys, useLessons, useTraining } from "../api";
import { KIND_ORDER, KINDS, KindIcon, LessonBody, SOURCE } from "../parts";
import type { Lesson, LessonKind } from "../types";

interface Draft {
  id: string;
  kind: LessonKind;
  prompt: string;
  content: string;
}

export function ReviewTab({ agent, canEdit }: TabProps) {
  const pending = useLessons(agent.id, "pending");
  const overview = useTraining(agent.id);
  const [editing, setEditing] = useState<Draft | null>(null);
  const inv = trainingKeys(agent.id);

  const approve = useAction((id: string) => http.post(`/lessons/${id}/approve`), { invalidate: inv });
  const reject = useAction((id: string) => http.post(`/lessons/${id}/reject`), { invalidate: inv });
  const approveAll = useAction(() => http.post<{ approved: number }>(`/agents/${agent.id}/lessons/approve-all`), {
    invalidate: inv,
    onSuccess: (r) => toast.success(`${r.approved} lesson${r.approved === 1 ? "" : "s"} approved`),
  });
  const save = useAction((d: Draft) => http.patch<Lesson>(`/lessons/${d.id}`, { kind: d.kind, content: d.content.trim(), prompt: d.prompt.trim() }), { invalidate: inv, onSuccess: () => setEditing(null) });
  const mine = useAction(() => http.post<{ conversations: number; proposed: number }>(`/agents/${agent.id}/training/reflect`, {}), {
    invalidate: inv,
    onSuccess: (r) => toast.success(r.proposed ? `${r.proposed} new lesson${r.proposed > 1 ? "s" : ""} to review` : "Nothing new to learn from your recent chats"),
  });

  const items = pending.data ?? [];
  const draftValid = !!editing?.content.trim() && (editing.kind !== "example" || !!editing.prompt.trim());

  return (
    <div className="space-y-5">
      <Card className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-primary-soft/60 via-transparent to-transparent" />
        <div className="relative flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold">Learn from my recent chats</h3>
            <p className="mt-0.5 text-xs text-muted">
              Scans your last five conversations with {agent.name} for reusable lessons. Nothing reaches its memory until you approve it.
              {overview.data && !overview.data.auto_learn && <> Turn on auto-learn in <Link to={`/training/${agent.id}/settings`} className="font-medium text-primary hover:underline">Settings</Link> to do this after every chat.</>}
            </p>
          </div>
          <Button variant="outline" icon={<MessageSquareText className="size-4" />} disabled={!canEdit} loading={mine.isPending} onClick={() => mine.mutate()}>
            Learn from my chats
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2">Pending lessons {items.length > 0 && <Badge tone="primary">{items.length}</Badge>}</span>}
          description="Proposed from chats and thumbs-down feedback. Edit, approve or reject each one."
          actions={canEdit && items.length > 1 ? <Button size="sm" variant="outline" icon={<CheckCheck className="size-4" />} loading={approveAll.isPending} onClick={() => approveAll.mutate()}>Approve all</Button> : undefined}
        />
        <div className="p-2 sm:p-3">
          {pending.isLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : !items.length ? (
            <EmptyState icon={<Wand2 className="size-5" />} title="Nothing to review" description="Turn on auto-learn, chat with the agent, or rate an answer with a thumbs-down and a note. Proposed lessons show up here." className="border-0" />
          ) : (
            <ul className="divide-y divide-border">
              {items.map((l) => {
                const src = SOURCE[l.source] ?? SOURCE.auto;
                const isEditing = editing?.id === l.id;
                return (
                  <li key={l.id} className="flex flex-col gap-3 px-2 py-3 sm:flex-row sm:items-start">
                    <KindIcon kind={isEditing ? editing.kind : l.kind ?? "rule"} className="hidden sm:inline-flex" />
                    <div className="min-w-0 flex-1 space-y-2">
                      {isEditing ? (
                        <div className="space-y-3">
                          <Field label="Type">
                            <Select value={editing.kind} onChange={(e) => setEditing({ ...editing, kind: e.target.value as LessonKind })} className="sm:w-56">
                              {KIND_ORDER.map((k) => <option key={k} value={k}>{KINDS[k].label}</option>)}
                            </Select>
                          </Field>
                          {(editing.kind === "example" || editing.kind === "correction") && (
                            <Field label={editing.kind === "example" ? "Question" : "What it got wrong (optional)"}>
                              <Textarea rows={2} maxLength={2000} value={editing.prompt} onChange={(e) => setEditing({ ...editing, prompt: e.target.value })} />
                            </Field>
                          )}
                          <Field label={editing.kind === "example" ? "Ideal answer" : editing.kind === "correction" ? "What it should do instead" : "Lesson"}>
                            <Textarea rows={3} maxLength={2000} value={editing.content} onChange={(e) => setEditing({ ...editing, content: e.target.value })} autoFocus />
                          </Field>
                        </div>
                      ) : (
                        <LessonBody lesson={l} />
                      )}
                      {l.rationale && !isEditing && <div className="text-xs text-muted">Why: {l.rationale}</div>}
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                        <Badge tone="muted">{KINDS[l.kind ?? "rule"].label}</Badge>
                        <Badge tone={src.tone} icon={<src.icon className="size-3" />}>{src.label}</Badge>
                        {timeAgo(l.created_at)}
                        {l.conversation_id && <Link className="hover:text-fg hover:underline" to={`/chat/${l.conversation_id}`}>view chat</Link>}
                      </div>
                    </div>
                    {canEdit && (
                      <div className="flex shrink-0 items-center gap-1.5">
                        {isEditing ? (
                          <>
                            <Button size="sm" loading={save.isPending} disabled={!draftValid} onClick={() => save.mutate(editing)}>Save</Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                          </>
                        ) : (
                          <>
                            <Button size="sm" icon={<Check className="size-4" />} loading={approve.isPending && approve.variables === l.id} onClick={() => approve.mutate(l.id)}>Approve</Button>
                            <Button size="icon" variant="ghost" aria-label="Edit lesson" title="Edit" onClick={() => setEditing({ id: l.id, kind: l.kind ?? "rule", prompt: l.prompt ?? "", content: l.content })}>
                              <Pencil className="size-4 text-muted" />
                            </Button>
                            <Button size="icon" variant="ghost" aria-label="Reject lesson" title="Reject" loading={reject.isPending && reject.variables === l.id} onClick={() => reject.mutate(l.id)}>
                              {!(reject.isPending && reject.variables === l.id) && <X className="size-4 text-muted" />}
                            </Button>
                          </>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}
