import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessagesSquare, Play, Plus, Users } from "lucide-react";
import { useAuth } from "@/lib/auth";
import type { Agent, Team } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useAgents, useTeams } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, EmptyState, PageLoader, Tabs } from "@/components/ui/primitives";
import { SearchInput } from "@/components/ui/inputs";
import { AgentAvatar, IconTile } from "@/components/ui/icons";
import { Grid, ResourceCard, ScopeBadge } from "@/components/library";
import { RunLauncher } from "@/components/run/RunLauncher";
import { styleMeta } from "./styles";

export function MemberStack({ team, agents, max = 5 }: { team: Team; agents: Record<string, Agent>; max?: number }) {
  const members = team.members.map((m) => agents[m.agent_id]).filter(Boolean);
  const extra = members.length - max;
  return (
    <div className="flex items-center">
      {members.slice(0, max).map((a, i) => (
        <div key={`${a.id}-${i}`} className="-ml-1.5 rounded-lg ring-2 ring-[var(--surface)] first:ml-0" title={a.name}>
          <AgentAvatar agent={a} size="xs" />
        </div>
      ))}
      {extra > 0 && <span className="ml-1.5 text-xs text-muted">+{extra}</span>}
    </div>
  );
}

export default function TeamsList() {
  const teams = useTeams();
  const agents = useAgents();
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"all" | "org" | "global">("all");
  const [running, setRunning] = useState<Team | null>(null);
  const agentMap = useMemo(() => Object.fromEntries((agents.data ?? []).map((a) => [a.id, a])), [agents.data]);

  const items = (teams.data ?? []).filter(
    (t) => (scope === "all" || (scope === "global" ? t.org_id === null : t.org_id !== null)) && (!q || `${t.name} ${t.description}`.toLowerCase().includes(q.toLowerCase())),
  );

  return (
    <Page>
      <PageHeader
        title="Teams"
        description="Combine agents with an orchestration style: pipelines, parallel panels, supervisors, routers or group chats."
        actions={can("member") && <Button icon={<Plus className="size-4" />} onClick={() => nav("/teams/new")}>New team</Button>}
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={[
            { key: "all", label: "All", count: teams.data?.length },
            { key: "org", label: "My org" },
            { key: "global", label: "Global library" },
          ]}
          value={scope}
          onChange={setScope}
        />
        <SearchInput value={q} onChange={setQ} placeholder="Search teams…" className="sm:w-64" />
      </div>
      {teams.isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Users className="size-5" />}
          title="No teams found"
          description="Create a team to let several agents collaborate on a task."
          action={can("member") && <Button onClick={() => nav("/teams/new")}>New team</Button>}
        />
      ) : (
        <Grid>
          {items.map((t) => {
            const meta = styleMeta(t.style);
            return (
              <ResourceCard
                key={t.id}
                to={`/teams/${t.id}`}
                icon={<IconTile icon={meta.icon} color={meta.color} />}
                title={t.name}
                subtitle={
                  <span className="flex items-center gap-1.5">
                    <ScopeBadge orgId={t.org_id} />
                    <Badge tone="muted">{meta.label}</Badge>
                  </span>
                }
                description={t.description}
                badges={<MemberStack team={t} agents={agentMap} />}
                footer={`${t.members.length} member${t.members.length === 1 ? "" : "s"} · updated ${timeAgo(t.updated_at)}`}
                actions={
                  <>
                    <Button
                      size="icon"
                      variant="outline"
                      className="size-8"
                      title="Chat with team"
                      onClick={(e) => {
                        e.preventDefault();
                        nav(`/chat?team=${t.id}`);
                      }}
                    >
                      <MessagesSquare className="size-3.5" />
                    </Button>
                    {can("member") && (
                      <Button
                        size="icon"
                        className="size-8"
                        title="Run team"
                        onClick={(e) => {
                          e.preventDefault();
                          setRunning(t);
                        }}
                      >
                        <Play className="size-3.5" />
                      </Button>
                    )}
                  </>
                }
              />
            );
          })}
        </Grid>
      )}
      {running && <RunLauncher open={!!running} onClose={() => setRunning(null)} targetType="team" targetId={running.id} targetName={running.name} />}
    </Page>
  );
}
