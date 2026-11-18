import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Check, GraduationCap, MessageSquareText, Pencil, Plus, ScrollText, ThumbsDown, Wand2, Sparkles, X } from "lucide-react";
import { http } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { Lesson, Skill } from "@/lib/types";
import { useAction, useLessons, useTraining } from "@/hooks/useData";
import { Badge, Button, Card, CardHeader, EmptyState, Spinner, Switch, Textarea } from "@/components/ui/primitives";

const SOURCE: Record<Lesson["source"], { label: string; tone: "primary" | "warning" | "muted"; icon: typeof Sparkles }> = {
  auto: { label: "Learned from chat", tone: "primary", icon: Sparkles },
  feedback: { label: "From thumbs-down", tone: "warning", icon: ThumbsDown },
  user: { label: "Taught by you", tone: "muted", icon: GraduationCap },
};

/** Train an agent: teach lessons, auto-learn from chats, review proposals, distill into a skill. */
export function TrainPanel({ agentId, readOnly, onAutoLearnChange }: { agentId: string; readOnly?: boolean; onAutoLearnChange?: (v: boolean) => void }) {
  const overview = useTraining(agentId);
  const pending = useLessons(agentId, "pending");
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);
  const inv = [["training", agentId], ["lessons", agentId], ["memories"]];

  const teach = useAction(() => http.post(`/agents/${agentId}/lessons`, { content: draft }), { success: "Lesson saved to memory", invalidate: inv, onSuccess: () => setDraft("") });
  const toggle = useAction((v: boolean) => http.put(`/agents/${agentId}/training/settings`, { auto_learn: v }), {
    invalidate: [["training", agentId], ["agents"]],
    onSuccess: (_r, v) => onAutoLearnChange?.(v),
  });
  const approve = useAction((id: string) => http.post(`/lessons/${id}/approve`), { invalidate: inv });
  const reject = useAction((id: string) => http.post(`/lessons/${id}/reject`), { invalidate: inv });
  const approveAll = useAction(() => http.post<{ approved: number }>(`/agents/${agentId}/lessons/approve-all`), { invalidate: inv });
  const save = useAction((v: { id: string; text: string }) => http.patch(`/lessons/${v.id}`, { content: v.text }), { invalidate: inv, onSuccess: () => setEditing(null) });
  const mine = useAction(() => http.post<{ conversations: number; proposed: number }>(`/agents/${agentId}/training/reflect`, {}), {
    invalidate: inv,
    onSuccess: (r) => toast.success(r.proposed ? `${r.proposed} new lesson${r.proposed > 1 ? "s" : ""} to review` : "Nothing new to learn from your recent chats"),
  });
  const distill = useAction(() => http.post<Skill>(`/agents/${agentId}/training/distill`), { invalidate: [["skills"], ["agents"]] });

  const o = overview.data;
  const items = pending.data ?? [];
  const canEdit = !readOnly;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Teach this agent" description="Write a rule, preference or fact in plain language. It is saved to the agent's memory and used in every future prompt." />
          <div className="space-y-3 p-3 sm:p-4">
            <Textarea
              rows={4}
              value={draft}
              maxLength={2000}
              onChange={(e) => setDraft(e.target.value)}
              disabled={!canEdit}
              placeholder={'e.g. "Always open with a one-line summary, then details."\n"Our fiscal year starts in April."\n"Never promise delivery dates."'}
            />
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs text-muted">{o ? `${o.memories} memor${o.memories === 1 ? "y" : "ies"} · ${o.approved} approved lesson${o.approved === 1 ? "" : "s"}` : ""}</span>
              <Button icon={<Plus className="size-4" />} disabled={!canEdit || !draft.trim()} loading={teach.isPending} onClick={() => teach.mutate()}>Teach</Button>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Learn from chats" description="The agent proposes lessons from your conversations. Nothing reaches its memory until you approve it." />
          <div className="space-y-4 p-3 sm:p-4">
            <Switch
              checked={!!o?.auto_learn}
              disabled={!canEdit || !o?.can_configure || toggle.isPending}
              onChange={(v) => toggle.mutate(v)}
              label="Auto-learn after every chat"
              description={o && !o.can_configure ? "This is a global agent. Duplicate it into your organization to turn this on." : "After each answer the agent reflects on the exchange (one extra short model call) and queues lessons below. Thumbs-down feedback always queues a lesson, even with this off."}
            />
            <div className="flex flex-wrap gap-2 border-t border-border pt-3">
              <Button variant="outline" icon={<MessageSquareText className="size-4" />} disabled={!canEdit} loading={mine.isPending} onClick={() => mine.mutate()}>Learn from my recent chats</Button>
              <Button variant="outline" icon={<ScrollText className="size-4" />} disabled={!canEdit || !o?.memories} loading={distill.isPending} onClick={() => distill.mutate()}>Distill into a skill</Button>
            </div>
            {distill.data && (
              <p className="text-xs text-muted">
                Skill <Link className="font-medium text-primary hover:underline" to={`/skills/${distill.data.id}`}>{distill.data.name}</Link> updated and attached to this agent.
              </p>
            )}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2">Review queue {items.length > 0 && <Badge tone="primary">{items.length}</Badge>}</span>}
          description="Proposed lessons from chats and thumbs-down feedback. Edit, approve or reject each one."
          actions={canEdit && items.length > 1 ? <Button size="sm" variant="outline" loading={approveAll.isPending} onClick={() => approveAll.mutate()}>Approve all</Button> : undefined}
        />
        <div className="p-2 sm:p-3">
          {pending.isLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : !items.length ? (
            <EmptyState icon={<Wand2 className="size-5" />} title="Nothing to review" description="Turn on auto-learn, chat with the agent, or rate an answer with a thumbs-down and a note. Proposed lessons show up here." className="border-0" />
          ) : (
            <ul className="divide-y divide-border">
              {items.map((l) => {
                const src = SOURCE[l.source];
                const isEditing = editing?.id === l.id;
                return (
                  <li key={l.id} className="flex flex-col gap-2 px-2 py-3 sm:flex-row sm:items-start sm:gap-3">
                    <div className="min-w-0 flex-1 space-y-1.5">
                      {isEditing ? (
                        <Textarea rows={3} value={editing.text} onChange={(e) => setEditing({ id: l.id, text: e.target.value })} autoFocus />
                      ) : (
                        <div className="text-sm">{l.content}</div>
                      )}
                      {l.rationale && !isEditing && <div className="text-xs text-muted">Why: {l.rationale}</div>}
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                        <Badge tone={src.tone} icon={<src.icon className="size-3" />}>{src.label}</Badge>
                        {timeAgo(l.created_at)}
                        {l.conversation_id && <Link className="hover:text-fg hover:underline" to={`/chat/${l.conversation_id}`}>view chat</Link>}
                      </div>
                    </div>
                    {canEdit && (
                      <div className="flex shrink-0 items-center gap-1.5">
                        {isEditing ? (
                          <>
                            <Button size="sm" loading={save.isPending} disabled={!editing.text.trim()} onClick={() => save.mutate(editing)}>Save</Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                          </>
                        ) : (
                          <>
                            <Button size="sm" icon={<Check className="size-4" />} loading={approve.isPending && approve.variables === l.id} onClick={() => approve.mutate(l.id)}>Approve</Button>
                            <Button size="icon" variant="ghost" aria-label="Edit lesson" onClick={() => setEditing({ id: l.id, text: l.content })}><Pencil className="size-4 text-muted" /></Button>
                            <Button size="icon" variant="ghost" aria-label="Reject lesson" onClick={() => reject.mutate(l.id)}><X className="size-4 text-muted" /></Button>
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
