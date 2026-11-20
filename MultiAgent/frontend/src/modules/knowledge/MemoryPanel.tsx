import { useState } from "react";
import { Brain, Plus, Trash2 } from "lucide-react";
import { http } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import { useAction, useMemories } from "@/hooks/useData";
import { Badge, Button, Card, CardHeader, EmptyState, Input, Spinner } from "@/components/ui/primitives";

/** Long-term memory for an agent (scope=agent) or a project (scope=project). */
export function MemoryPanel({ scope, agentId, projectId, readOnly, description }: { scope: "agent" | "project"; agentId?: string; projectId?: string; readOnly?: boolean; description?: string }) {
  const params = scope === "agent" ? { scope, agent_id: agentId } : { scope, project_id: projectId };
  const mems = useMemories(params);
  const [draft, setDraft] = useState("");
  const [key, setKey] = useState("");
  const inv = [["memories"]];
  const add = useAction(() => http.post("/memories", { ...params, key, content: draft }), { invalidate: inv, onSuccess: () => { setDraft(""); setKey(""); } });
  const del = useAction((id: string) => http.del(`/memories/${id}`), { invalidate: inv });

  return (
    <Card>
      <CardHeader
        title={scope === "agent" ? "Agent memory" : "Project memory"}
        description={description ?? (scope === "agent" ? "Private notes this agent keeps across all projects (enable the memory capability)." : "Facts shared by every agent working in this project. Recent items are added to each prompt.")}
      />
      {!readOnly && (
        <div className="flex flex-col gap-2 border-b border-border p-3 sm:flex-row">
          <Input value={key} onChange={(e) => setKey(e.target.value)} placeholder="Label (optional)" className="sm:w-40" />
          <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Add a fact to remember…" onKeyDown={(e) => e.key === "Enter" && draft.trim() && add.mutate()} className="flex-1" />
          <Button icon={<Plus className="size-4" />} disabled={!draft.trim()} loading={add.isPending} onClick={() => add.mutate()}>Add</Button>
        </div>
      )}
      <div className="p-2 sm:p-3">
        {mems.isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : !mems.data?.length ? (
          <EmptyState icon={<Brain className="size-5" />} title="No memories yet" description="Agents with the memory tool save durable facts here automatically." className="border-0" />
        ) : (
          <ul className="divide-y divide-border">
            {mems.data.map((m) => (
              <li key={m.id} className="flex items-start gap-3 px-2 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="text-sm">
                    {m.key && <span className="mr-1.5 font-medium">{m.key}:</span>}
                    {m.content}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] text-muted">
                    <Badge tone={m.source === "agent" ? "primary" : m.source === "learned" ? "success" : "muted"}>{m.source === "agent" ? "saved by agent" : m.source === "learned" ? "learned · approved" : "added by user"}</Badge>
                    {timeAgo(m.created_at)}
                  </div>
                </div>
                {!readOnly && (
                  <Button variant="ghost" size="icon" onClick={() => del.mutate(m.id)} aria-label="Delete memory">
                    <Trash2 className="size-4 text-muted" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
