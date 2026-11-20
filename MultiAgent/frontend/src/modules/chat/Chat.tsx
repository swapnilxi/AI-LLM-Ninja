import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, MessagesSquare, Plus, Users } from "lucide-react";
import { toast } from "sonner";
import { http, qs } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Agent } from "@/modules/agents/types";
import type { Conversation } from "@/modules/chat/types";
import { cn, errMsg, timeAgo } from "@/shared/lib/utils";
import { useAgents } from "@/modules/agents/api";
import { useTeams } from "@/modules/teams/api";
import { Button, EmptyState, Spinner } from "@/shared/ui/primitives";
import { SearchInput } from "@/shared/ui/inputs";
import { AgentAvatar, IconTile } from "@/shared/ui/icons";
import { TargetList, type ChatTarget } from "./TargetPicker";
import { Thread } from "./Thread";
import { CommandsPane, ConversationSkillsPane } from "./ChatPanes";

/**
 * One route (`chat/*`) so the conversation list and an open thread stay mounted while sub-pages change:
 * /chat, /chat/new, /chat/:conversationId, /chat/:conversationId/skills, /chat/:conversationId/commands.
 */
export default function Chat() {
  const splat = (useParams()["*"] ?? "").split("/").filter(Boolean);
  const isNew = splat[0] === "new";
  const conversationId = isNew ? undefined : splat[0];
  const sub = conversationId ? splat[1] : undefined;
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { projectId, project, can } = useAuth();
  const agents = useAgents();
  const teams = useTeams();
  const [q, setQ] = useState("");
  const creating = useRef(false);

  const convs = useQuery({
    queryKey: ["conversations", projectId],
    queryFn: () => http.get<Conversation[]>(`/conversations${qs({ project_id: projectId })}`),
    enabled: !!projectId,
  });

  const create = async (t: ChatTarget) => {
    if (!projectId) {
      toast.error("Select a project first");
      return;
    }
    try {
      const c = await http.post<Conversation>("/conversations", { project_id: projectId, target_type: t.type, target_id: t.id });
      qc.invalidateQueries({ queryKey: ["conversations"] });
      nav(`/chat/${c.id}`);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  // Deep links: /chat?agent=<id> or /chat?team=<id> start a new conversation with that target.
  useEffect(() => {
    const agent = params.get("agent");
    const team = params.get("team");
    if ((!agent && !team) || !projectId || creating.current) return;
    creating.current = true;
    const t: ChatTarget = agent ? { type: "agent", id: agent } : { type: "team", id: team! };
    setParams({}, { replace: true });
    create(t).finally(() => {
      creating.current = false;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, projectId]);

  const names = useMemo(() => {
    const m: Record<string, { name: string; agent?: Agent }> = {};
    for (const a of agents.data ?? []) m[a.id] = { name: a.name, agent: a };
    for (const t of teams.data ?? []) m[t.id] = { name: t.name };
    return m;
  }, [agents.data, teams.data]);

  const list = (convs.data ?? []).filter((c) => !q || `${c.title} ${names[c.target_id]?.name ?? ""}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="flex h-full min-h-0">
      {/* conversation list */}
      <aside className={cn("flex w-full min-w-0 flex-col border-r border-border bg-surface/60 md:w-72 md:shrink-0 lg:w-80", (conversationId || isNew) && "hidden md:flex")}>
        <div className="space-y-3 border-b border-border p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <h1 className="text-base font-semibold">Chats</h1>
              <p className="truncate text-xs text-muted">{project ? `in ${project.name}` : "No project selected"}</p>
            </div>
            {can("member") && (
              <Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => nav("/chat/new")}>
                New
              </Button>
            )}
          </div>
          {(convs.data?.length ?? 0) > 5 && <SearchInput value={q} onChange={setQ} placeholder="Search chats…" />}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {convs.isLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : list.length === 0 ? (
            <div className="px-3 py-10 text-center text-sm text-muted">
              No conversations yet.
              {can("member") && (
                <button onClick={() => nav("/chat/new")} className="mt-2 block w-full cursor-pointer font-medium text-primary hover:underline">
                  Start one
                </button>
              )}
            </div>
          ) : (
            <ul className="space-y-0.5">
              {list.map((c) => {
                const info = names[c.target_id];
                return (
                  <li key={c.id}>
                    <NavLink
                      to={`/chat/${c.id}`}
                      className={({ isActive }) => cn("flex items-center gap-2.5 rounded-lg px-2.5 py-2 transition-colors", isActive ? "bg-gradient-to-r from-primary-soft to-primary-soft/30" : "hover:bg-surface-2")}
                    >
                      {c.target_type === "agent" ? <AgentAvatar agent={info?.agent} size="xs" /> : <IconTile icon={Users} color="violet" size="xs" />}
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium">{c.title}</div>
                        <div className="truncate text-[11px] text-muted">
                          {info?.name ?? c.target_type} · {timeAgo(c.updated_at)}
                        </div>
                      </div>
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>

      {/* thread */}
      <section className={cn("min-w-0 flex-1", !conversationId && !isNew && "hidden md:block")}>
        {conversationId ? (
          <>
            {/* the thread stays mounted (draft, live stream) while a sub-page is open */}
            <div className={cn("h-full", sub && "hidden")}>
              <Thread key={conversationId} conversationId={conversationId} />
            </div>
            {sub === "skills" && <ConversationSkillsPane conversationId={conversationId} />}
            {sub === "commands" && <CommandsPane conversationId={conversationId} />}
          </>
        ) : (
          <div className="h-full overflow-y-auto">
            <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
              {isNew && (
                <NavLink to="/chat" className="mb-4 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg md:hidden">
                  <ChevronLeft className="size-3.5" /> Back to chats
                </NavLink>
              )}
              <div className="mb-8 text-center">
                <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/10 text-primary ring-1 ring-inset ring-indigo-500/20">
                  <MessagesSquare className="size-7" strokeWidth={1.8} />
                </div>
                <h2 className="text-xl font-semibold tracking-tight">Who do you want to talk to?</h2>
                <p className="mt-1 text-sm text-muted">Chat with a single agent or a whole team. Every reply uses {project ? `“${project.name}”` : "the active project"}’s context.</p>
              </div>
              {can("member") ? (
                <TargetList onPick={create} />
              ) : (
                <EmptyState title="Read-only access" description="Viewers can browse conversations but not start new ones." />
              )}
            </div>
          </div>
        )}
      </section>

    </div>
  );
}
