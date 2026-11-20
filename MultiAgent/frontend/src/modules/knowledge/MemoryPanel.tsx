import { useState } from "react";
import { Brain, Pencil, Plus, Trash2 } from "lucide-react";
import { http } from "@/shared/lib/api";
import { timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useMemories } from "@/modules/knowledge/api";
import type { Memory } from "@/modules/knowledge/types";
import { SearchInput } from "@/shared/ui/inputs";
import { Badge, Button, Card, CardHeader, EmptyState, Input, Spinner, Textarea } from "@/shared/ui/primitives";

const SOURCE: Record<Memory["source"], { label: string; tone: "primary" | "success" | "muted" }> = {
  agent: { label: "saved by agent", tone: "primary" },
  learned: { label: "learned · approved", tone: "success" },
  user: { label: "added by user", tone: "muted" },
};

/** Long-term memory for an agent (scope=agent) or a project (scope=project): add, edit, delete. */
export function MemoryPanel({ scope, agentId, projectId, readOnly, description }: { scope: "agent" | "project"; agentId?: string; projectId?: string; readOnly?: boolean; description?: string }) {
  const params = scope === "agent" ? { scope, agent_id: agentId } : { scope, project_id: projectId };
  const mems = useMemories(params);
  const [draft, setDraft] = useState("");
  const [key, setKey] = useState("");
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<{ id: string; key: string; content: string } | null>(null);
  const inv = [["memories"], ["training"]];
  const add = useAction(() => http.post("/memories", { ...params, key, content: draft }), { invalidate: inv, onSuccess: () => { setDraft(""); setKey(""); } });
  const save = useAction((v: { id: string; key: string; content: string }) => http.patch(`/memories/${v.id}`, { key: v.key, content: v.content }), { invalidate: inv, onSuccess: () => setEditing(null) });
  const del = useAction((id: string) => http.del(`/memories/${id}`), { invalidate: inv });
  const items = (mems.data ?? []).filter((m) => !q || `${m.key} ${m.content}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            {scope === "agent" ? "Agent memory" : "Project memory"}
            {!!mems.data?.length && <Badge tone="muted">{mems.data.length}</Badge>}
          </span>
        }
        description={description ?? (scope === "agent" ? "Private notes this agent keeps across all projects (enable the memory capability)." : "Facts shared by every agent working in this project. Recent items are added to each prompt.")}
        actions={(mems.data?.length ?? 0) > 5 ? <SearchInput value={q} onChange={setQ} placeholder="Filter…" className="w-40 sm:w-52" /> : undefined}
      />
      {!readOnly && (
        <div className="flex flex-col gap-2 border-b border-border p-3 sm:flex-row">
          <Input value={key} maxLength={120} onChange={(e) => setKey(e.target.value)} placeholder="Label (optional)" className="sm:w-40" />
          <Input value={draft} maxLength={4000} onChange={(e) => setDraft(e.target.value)} placeholder="Add a fact to remember…" onKeyDown={(e) => e.key === "Enter" && draft.trim() && add.mutate()} className="flex-1" />
          <Button icon={<Plus className="size-4" />} disabled={!draft.trim()} loading={add.isPending} onClick={() => add.mutate()}>Add</Button>
        </div>
      )}
      <div className="p-2 sm:p-3">
        {mems.isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : !items.length ? (
          <EmptyState icon={<Brain className="size-5" />} title={q ? "No matching memories" : "No memories yet"} description={q ? "Try another filter." : "Agents with the memory tool save durable facts here automatically. Approved lessons land here too."} className="border-0" />
        ) : (
          <ul className="divide-y divide-border">
            {items.map((m) => {
              const src = SOURCE[m.source] ?? SOURCE.user;
              const isEditing = editing?.id === m.id;
              return (
                <li key={m.id} className="flex flex-col gap-2 px-2 py-2.5 sm:flex-row sm:items-start sm:gap-3">
                  <div className="min-w-0 flex-1">
                    {isEditing ? (
                      <div className="space-y-2">
                        <Input value={editing.key} maxLength={120} onChange={(e) => setEditing({ ...editing, key: e.target.value })} placeholder="Label (optional)" />
                        <Textarea rows={3} value={editing.content} maxLength={4000} onChange={(e) => setEditing({ ...editing, content: e.target.value })} autoFocus />
                      </div>
                    ) : (
                      <div className="whitespace-pre-wrap break-words text-sm">
                        {m.key && <span className="mr-1.5 font-medium">{m.key}:</span>}
                        {m.content}
                      </div>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted">
                      <Badge tone={src.tone}>{src.label}</Badge>
                      {m.tags.filter((t) => t.startsWith("kind:")).map((t) => <Badge key={t} tone="muted">{t.slice(5)}</Badge>)}
                      {timeAgo(m.created_at)}
                    </div>
                  </div>
                  {!readOnly && (
                    <div className="flex shrink-0 items-center gap-1">
                      {isEditing ? (
                        <>
                          <Button size="sm" loading={save.isPending} disabled={!editing.content.trim()} onClick={() => save.mutate(editing)}>Save</Button>
                          <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                        </>
                      ) : (
                        <>
                          <Button variant="ghost" size="icon" onClick={() => setEditing({ id: m.id, key: m.key, content: m.content })} aria-label="Edit memory" title="Edit">
                            <Pencil className="size-4 text-muted" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => del.mutate(m.id)} loading={del.isPending && del.variables === m.id} aria-label="Delete memory" title="Delete">
                            {!(del.isPending && del.variables === m.id) && <Trash2 className="size-4 text-muted" />}
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
  );
}
