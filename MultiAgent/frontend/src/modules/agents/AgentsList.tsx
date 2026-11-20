import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, MessagesSquare, Play, Plus } from "lucide-react";
import { useAuth } from "@/lib/auth";
import type { Agent } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useAgents } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Button, EmptyState, PageLoader, Tabs } from "@/components/ui/primitives";
import { SearchInput } from "@/components/ui/inputs";
import { AgentAvatar } from "@/components/ui/icons";
import { Grid, ResourceCard, ScopeBadge } from "@/components/library";
import { RunLauncher } from "@/components/run/RunLauncher";
import { CapabilityBadges, modelLabel } from "./parts";

export default function AgentsList() {
  const agents = useAgents();
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"all" | "org" | "global">("all");
  const [running, setRunning] = useState<Agent | null>(null);

  const items = (agents.data ?? []).filter(
    (a) =>
      (scope === "all" || (scope === "global" ? a.org_id === null : a.org_id !== null)) &&
      (!q || `${a.name} ${a.description} ${a.tags.join(" ")}`.toLowerCase().includes(q.toLowerCase())),
  );

  return (
    <Page>
      <PageHeader
        title="Agents"
        description="Project-independent agents. Each run receives the organization and project context, documents, memory and policies."
        actions={can("member") && <Button icon={<Plus className="size-4" />} onClick={() => nav("/agents/new")}>New agent</Button>}
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={[
            { key: "all", label: "All", count: agents.data?.length },
            { key: "org", label: "My org" },
            { key: "global", label: "Global library" },
          ]}
          value={scope}
          onChange={setScope}
        />
        <SearchInput value={q} onChange={setQ} placeholder="Search agents…" className="sm:w-64" />
      </div>
      {agents.isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Bot className="size-5" />}
          title="No agents found"
          description="Create an agent, choose its model, give it skills, tools and knowledge."
          action={can("member") && <Button onClick={() => nav("/agents/new")}>New agent</Button>}
        />
      ) : (
        <Grid>
          {items.map((a) => (
            <ResourceCard
              key={a.id}
              to={`/agents/${a.id}`}
              icon={<AgentAvatar agent={a} />}
              title={a.name}
              subtitle={
                <span className="flex items-center gap-1.5">
                  <ScopeBadge orgId={a.org_id} />
                  <span className="truncate font-mono text-[11px]">{modelLabel(a)}</span>
                </span>
              }
              description={a.description}
              badges={<CapabilityBadges agent={a} />}
              footer={`Updated ${timeAgo(a.updated_at)}`}
              actions={
                <>
                  <Button
                    size="icon"
                    variant="outline"
                    className="size-8"
                    title="Chat"
                    aria-label="Chat"
                    onClick={(e) => {
                      e.preventDefault();
                      nav(`/chat?agent=${a.id}`);
                    }}
                  >
                    <MessagesSquare className="size-3.5" />
                  </Button>
                  {can("member") && (
                    <Button
                      size="icon"
                      variant="outline"
                      className="size-8"
                      title="Run"
                      aria-label="Run"
                      onClick={(e) => {
                        e.preventDefault();
                        setRunning(a);
                      }}
                    >
                      <Play className="size-3.5" />
                    </Button>
                  )}
                </>
              }
            />
          ))}
        </Grid>
      )}
      {running && <RunLauncher open={!!running} onClose={() => setRunning(null)} targetType="agent" targetId={running.id} targetName={running.name} />}
    </Page>
  );
}
