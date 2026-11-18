import { useState } from "react";
import { Bot, Users } from "lucide-react";
import type { Agent, Team } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAgents, useTeams } from "@/hooks/useData";
import { Dialog } from "@/components/ui/overlay";
import { Badge, Spinner, Tabs } from "@/components/ui/primitives";
import { SearchInput } from "@/components/ui/inputs";
import { AgentAvatar, IconTile } from "@/components/ui/icons";

export type ChatTarget = { type: "agent" | "team"; id: string };

const STYLE_LABEL: Record<string, string> = { sequential: "Pipeline", parallel: "Parallel", supervisor: "Supervisor", router: "Router", round_robin: "Debate" };

export function TargetList({ onPick, compact }: { onPick: (t: ChatTarget) => void; compact?: boolean }) {
  const agents = useAgents();
  const teams = useTeams();
  const [tab, setTab] = useState<"agent" | "team">("agent");
  const [q, setQ] = useState("");
  const match = (x: { name: string; description: string }) => !q || `${x.name} ${x.description}`.toLowerCase().includes(q.toLowerCase());
  const loading = tab === "agent" ? agents.isLoading : teams.isLoading;
  const items: (Agent | Team)[] = tab === "agent" ? (agents.data ?? []).filter(match) : (teams.data ?? []).filter(match);
  return (
    <div>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={[
            { key: "agent", label: <><Bot className="size-3.5" /> Agents</>, count: agents.data?.length },
            { key: "team", label: <><Users className="size-3.5" /> Teams</>, count: teams.data?.length },
          ]}
          value={tab}
          onChange={setTab}
        />
        <SearchInput value={q} onChange={setQ} placeholder="Search…" className="sm:w-52" />
      </div>
      {loading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">Nothing found.</p>
      ) : (
        <div className={cn("grid gap-2", compact ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3")}>
          {items.map((it) => (
            <button
              key={it.id}
              onClick={() => onPick({ type: tab, id: it.id })}
              className="flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-surface p-3 text-left transition-all hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-md hover:shadow-indigo-500/5"
            >
              {tab === "agent" ? <AgentAvatar agent={it as Agent} size="sm" /> : <IconTile icon={Users} color="violet" size="sm" />}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">{it.name}</span>
                  {tab === "team" && <Badge tone="muted">{STYLE_LABEL[(it as Team).style] ?? (it as Team).style}</Badge>}
                </div>
                <div className="line-clamp-2 text-xs text-muted">{it.description || "No description"}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function NewChatDialog({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (t: ChatTarget) => void }) {
  return (
    <Dialog open={open} onClose={onClose} title="Start a new chat" description="Pick an agent or a team. The chat runs inside your active project." size="xl">
      <TargetList
        compact
        onPick={(t) => {
          onPick(t);
          onClose();
        }}
      />
    </Dialog>
  );
}
