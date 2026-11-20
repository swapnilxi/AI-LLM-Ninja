import { useMemo, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Bot, Copy, MessagesSquare, Pencil, Play, Plus, X } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { cn, timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import type { Agent } from "@/modules/agents/types";
import { useAgents } from "@/modules/agents/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Button, EmptyState, PageLoader, Tabs } from "@/shared/ui/primitives";
import { SearchInput } from "@/shared/ui/inputs";
import { AgentAvatar } from "@/shared/ui/icons";
import { Grid, ResourceCard, ScopeBadge } from "@/shared/components/library";
import { CapabilityBadges, modelLabel, runAgentUrl } from "./parts";

type Scope = "all" | "org" | "global";

export default function AgentsList() {
  const agents = useAgents();
  const { can } = useAuth();
  const nav = useNavigate();
  // filters live in the URL so a filtered list is linkable
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const scope = (["all", "org", "global"].includes(params.get("scope") ?? "") ? params.get("scope") : "all") as Scope;
  const tag = params.get("tag") ?? "";
  const update = (k: string, v: string) =>
    setParams(
      (p) => {
        const n = new URLSearchParams(p);
        if (v && !(k === "scope" && v === "all")) n.set(k, v);
        else n.delete(k);
        return n;
      },
      { replace: true },
    );

  const dup = useAction((id: string) => http.post<Agent>(`/agents/${id}/duplicate`), {
    success: "Duplicated into your org",
    invalidate: [["agents"]],
    onSuccess: (a) => nav(`/agents/${a.id}`),
  });

  const all = agents.data ?? [];
  const tags = useMemo(() => {
    const counts = new Map<string, number>();
    all.forEach((a) => a.tags.forEach((t) => counts.set(t, (counts.get(t) ?? 0) + 1)));
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 20);
  }, [all]);

  const items = all.filter(
    (a) =>
      (scope === "all" || (scope === "global" ? a.org_id === null : a.org_id !== null)) &&
      (!tag || a.tags.includes(tag)) &&
      (!q || `${a.name} ${a.description} ${a.tags.join(" ")}`.toLowerCase().includes(q.toLowerCase())),
  );
  const filtered = !!(q || tag || scope !== "all");

  const iconAction = (label: string, icon: ReactNode, onClick: () => void, busy?: boolean) => (
    <Button
      size="icon"
      variant="outline"
      className="size-8"
      title={label}
      aria-label={label}
      loading={busy}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onClick();
      }}
    >
      {!busy && icon}
    </Button>
  );

  return (
    <Page>
      <PageHeader
        title="Agents"
        description="Project-independent agents. Manage their instructions, model, tools and skills; each run adds the organization and project context, documents and memory."
        actions={can("member") && <Button icon={<Plus className="size-4" />} onClick={() => nav("/agents/new")}>New agent</Button>}
      />
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={[
            { key: "all", label: "All", count: all.length },
            { key: "org", label: "My org", count: all.filter((a) => a.org_id !== null).length },
            { key: "global", label: "Global library", count: all.filter((a) => a.org_id === null).length },
          ]}
          value={scope}
          onChange={(v) => update("scope", v)}
        />
        <SearchInput value={q} onChange={(v) => update("q", v)} placeholder="Search agents…" className="sm:w-64" />
      </div>
      {tags.length > 0 && (
        <div className="mb-4 flex gap-1.5 overflow-x-auto pb-1">
          {tags.map(([t, n]) => (
            <button
              key={t}
              type="button"
              onClick={() => update("tag", tag === t ? "" : t)}
              className={cn(
                "inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                tag === t ? "border-primary/40 bg-primary-soft text-primary" : "border-border bg-surface text-muted hover:text-fg",
              )}
            >
              {t}
              <span className="opacity-60">{n}</span>
              {tag === t && <X className="size-3" />}
            </button>
          ))}
        </div>
      )}
      {agents.isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Bot className="size-5" />}
          title={filtered ? "No agents match these filters" : "No agents yet"}
          description={filtered ? "Try a different search, tag or scope." : "Create an agent, choose its model, give it skills, tools and knowledge."}
          action={
            filtered ? (
              <Button variant="outline" onClick={() => setParams({}, { replace: true })}>Clear filters</Button>
            ) : (
              can("member") && <Button onClick={() => nav("/agents/new")}>New agent</Button>
            )
          }
        />
      ) : (
        <Grid>
          {items.map((a) => {
            const editable = a.org_id !== null;
            return (
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
                    {iconAction("Chat", <MessagesSquare className="size-3.5" />, () => nav(`/chat?agent=${a.id}`))}
                    {can("member") && iconAction("Run", <Play className="size-3.5" />, () => nav(runAgentUrl(a.id)))}
                    {can("member") && editable && iconAction("Edit", <Pencil className="size-3.5" />, () => nav(`/agents/${a.id}/profile`))}
                    {can("member") && iconAction("Duplicate", <Copy className="size-3.5" />, () => dup.mutate(a.id), dup.isPending && dup.variables === a.id)}
                  </>
                }
              />
            );
          })}
        </Grid>
      )}
    </Page>
  );
}
