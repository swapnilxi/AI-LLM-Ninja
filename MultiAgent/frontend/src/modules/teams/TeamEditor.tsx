import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowDown, ArrowUp, Check, Copy, MessagesSquare, Play, Plus, Save, Trash2, X } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Agent } from "@/modules/agents/types";
import type { Team, TeamMember, TeamStyle } from "@/modules/teams/types";
import { cn } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useAgents } from "@/modules/agents/api";
import { useTeam } from "@/modules/teams/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Button, Card, CardHeader, EmptyState, Field, Input, PageLoader, Select, Textarea } from "@/shared/ui/primitives";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { AgentAvatar, IconTile } from "@/shared/ui/icons";
import { GlobalNotice, SaveBar, ScopeBadge } from "@/shared/components/library";
import { withReturn } from "@/shared/hooks/useReturnTo";
import { TEAM_STYLES } from "./styles";

interface Form {
  name: string;
  description: string;
  style: TeamStyle;
  members: TeamMember[];
  manager_agent_id: string;
  config: { max_rounds?: number; termination_keyword?: string; aggregator_agent_id?: string; max_concurrency?: number };
}

const EMPTY: Form = { name: "", description: "", style: "sequential", members: [], manager_agent_id: "", config: {} };

export function AgentPicker({ value, onChange, agents, disabled, placeholder = "Select an agent…", allowEmpty }: {
  value: string;
  onChange: (v: string) => void;
  agents: Agent[];
  disabled?: boolean;
  placeholder?: string;
  allowEmpty?: boolean;
}) {
  const current = agents.find((a) => a.id === value);
  return (
    <div className="flex min-w-0 items-center gap-2">
      <AgentAvatar agent={current ?? { avatar: "bot", color: "slate" }} size="sm" />
      <Select disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)} className="min-w-0 flex-1">
        <option value="" disabled={!allowEmpty}>
          {placeholder}
        </option>
        {agents.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
            {a.org_id === null ? " (global)" : ""}
          </option>
        ))}
      </Select>
    </div>
  );
}

export default function TeamEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const { can, user } = useAuth();
  const team = useTeam(id);
  const agentsQ = useAgents();
  const agents = agentsQ.data ?? [];
  const [form, setForm] = useState<Form>(EMPTY);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    if (team.data)
      setForm({
        name: team.data.name,
        description: team.data.description,
        style: team.data.style,
        members: team.data.members.map((m) => ({ agent_id: m.agent_id, role: m.role ?? "", instructions: m.instructions ?? "" })),
        manager_agent_id: team.data.manager_agent_id ?? "",
        config: { ...team.data.config },
      });
  }, [team.data]);

  const readOnly = !can("member") || (!!team.data && team.data.org_id === null && !user?.is_superadmin);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));
  const setCfg = (k: keyof Form["config"], v: any) => setForm((f) => ({ ...f, config: { ...f.config, [k]: v } }));
  const setMember = (i: number, patch: Partial<TeamMember>) => set("members", form.members.map((m, j) => (j === i ? { ...m, ...patch } : m)));
  const move = (i: number, d: -1 | 1) => {
    const next = [...form.members];
    const j = i + d;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    set("members", next);
  };

  const payload = () => {
    const cfg: Record<string, any> = {};
    if (form.style === "parallel") {
      if (form.config.aggregator_agent_id) cfg.aggregator_agent_id = form.config.aggregator_agent_id;
      if (form.config.max_concurrency) cfg.max_concurrency = Number(form.config.max_concurrency);
    }
    if (form.style === "round_robin") {
      if (form.config.aggregator_agent_id) cfg.aggregator_agent_id = form.config.aggregator_agent_id;
      if (form.config.max_rounds) cfg.max_rounds = Number(form.config.max_rounds);
      if (form.config.termination_keyword) cfg.termination_keyword = form.config.termination_keyword;
    }
    return {
      name: form.name,
      description: form.description,
      style: form.style,
      members: form.members.filter((m) => m.agent_id),
      manager_agent_id: form.manager_agent_id || null,
      config: cfg,
    };
  };

  const save = useAction(() => (isNew ? http.post<Team>("/teams", payload()) : http.put<Team>(`/teams/${id}`, payload())), {
    success: "Team saved",
    invalidate: [["teams"]],
    onSuccess: (t) => isNew && nav(`/teams/${t.id}`, { replace: true }),
  });
  const dup = useAction(() => http.post<Team>(`/teams/${id}/duplicate`), { success: "Duplicated into your org", invalidate: [["teams"]], onSuccess: (t) => nav(`/teams/${t.id}`) });
  const del = useAction(() => http.del(`/teams/${id}`), { success: "Team deleted", invalidate: [["teams"]], onSuccess: () => nav("/teams") });

  const agentMap = useMemo(() => Object.fromEntries(agents.map((a) => [a.id, a])), [agents]);
  const needsManager = form.style === "supervisor";
  const valid = form.name.trim() && form.members.some((m) => m.agent_id) && (!needsManager || form.manager_agent_id);

  if (!isNew && team.isLoading) return <PageLoader />;

  return (
    <Page>
      <PageHeader
        back="/teams"
        title={isNew ? "New team" : form.name || "Team"}
        description={!isNew && team.data && <ScopeBadge orgId={team.data.org_id} />}
        actions={
          !isNew && (
            <>
              <Button variant="outline" icon={<MessagesSquare className="size-4" />} onClick={() => nav(`/chat?team=${id}`)}>Chat</Button>
              {can("member") && <Button icon={<Play className="size-4" />} onClick={() => nav(withReturn(`/runs/new?target_type=team&target_id=${id}`, `/teams/${id}`))}>Run</Button>}
              <Button variant="outline" icon={<Copy className="size-4" />} onClick={() => dup.mutate()} loading={dup.isPending}>Duplicate</Button>
              {!readOnly && <Button variant="outline" icon={<Trash2 className="size-4" />} onClick={() => setConfirm(true)}>Delete</Button>}
            </>
          )
        }
      />
      {readOnly && team.data?.org_id === null && <GlobalNotice onDuplicate={() => dup.mutate()} busy={dup.isPending} />}

      <div className="space-y-5">
        <Card className="grid gap-4 p-4 sm:grid-cols-2">
          <Field label="Name">
            <Input disabled={readOnly} value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Research squad" />
          </Field>
          <Field label="Description">
            <Input disabled={readOnly} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="What this team is good at" />
          </Field>
        </Card>

        <Card>
          <CardHeader title="Orchestration style" description="How members collaborate on a task." />
          <div className="grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-5">
            {TEAM_STYLES.map((s) => {
              const active = form.style === s.key;
              return (
                <button
                  key={s.key}
                  type="button"
                  disabled={readOnly}
                  onClick={() => set("style", s.key)}
                  className={cn(
                    "relative flex cursor-pointer flex-col gap-2 rounded-xl border p-3 text-left transition-all disabled:cursor-default",
                    active ? "border-primary bg-gradient-to-br from-primary-soft to-transparent shadow-sm" : "border-border hover:border-indigo-500/30 hover:bg-surface-2/60",
                  )}
                >
                  {active && (
                    <span className="absolute right-2.5 top-2.5 flex size-5 items-center justify-center rounded-full bg-primary text-primary-fg">
                      <Check className="size-3" />
                    </span>
                  )}
                  <IconTile icon={s.icon} color={s.color} size="sm" />
                  <div>
                    <div className="text-sm font-semibold">{s.label}</div>
                    <div className="text-xs font-medium text-muted">{s.summary}</div>
                  </div>
                  <p className="text-xs leading-relaxed text-muted">{s.detail}</p>
                </button>
              );
            })}
          </div>
        </Card>

        <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
          <Card>
            <CardHeader
              title="Members"
              description={form.style === "sequential" ? "Order matters: members run top to bottom." : form.style === "supervisor" ? "Specialists the manager can delegate to." : "Agents taking part in this team."}
              actions={
                !readOnly && (
                  <Button size="sm" variant="outline" icon={<Plus className="size-3.5" />} onClick={() => set("members", [...form.members, { agent_id: "", role: "", instructions: "" }])}>
                    Add member
                  </Button>
                )
              }
            />
            <div className="space-y-3 p-3">
              {form.members.length === 0 ? (
                <EmptyState
                  title="No members yet"
                  description="Add agents from your library. Global agents work in every org."
                  className="border-0 py-8"
                  action={!readOnly && <Button size="sm" onClick={() => set("members", [{ agent_id: "", role: "", instructions: "" }])}>Add first member</Button>}
                />
              ) : (
                form.members.map((m, i) => (
                  <div key={i} className="rounded-xl border border-border bg-surface p-3">
                    <div className="flex items-center gap-2">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-surface-2 text-xs font-semibold tabular-nums text-muted">{i + 1}</span>
                      <div className="min-w-0 flex-1">
                        <AgentPicker agents={agents} value={m.agent_id} disabled={readOnly} onChange={(v) => setMember(i, { agent_id: v })} />
                      </div>
                      {!readOnly && (
                        <div className="flex shrink-0">
                          <Button variant="ghost" size="icon" className="size-8" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Move up">
                            <ArrowUp className="size-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="size-8" disabled={i === form.members.length - 1} onClick={() => move(i, 1)} aria-label="Move down">
                            <ArrowDown className="size-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="size-8" onClick={() => set("members", form.members.filter((_, j) => j !== i))} aria-label="Remove">
                            <X className="size-4" />
                          </Button>
                        </div>
                      )}
                    </div>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <Field label="Role in team">
                        <Input disabled={readOnly} value={m.role} onChange={(e) => setMember(i, { role: e.target.value })} placeholder="e.g. Gather facts and sources" />
                      </Field>
                      <Field label="Extra instructions (optional)">
                        <Textarea disabled={readOnly} rows={1} className="min-h-9" value={m.instructions} onChange={(e) => setMember(i, { instructions: e.target.value })} placeholder="Focus on…" />
                      </Field>
                    </div>
                    {m.agent_id && agentMap[m.agent_id]?.description && <p className="mt-2 text-xs text-muted">{agentMap[m.agent_id].description}</p>}
                  </div>
                ))
              )}
            </div>
          </Card>

          <div className="space-y-5">
            <Card className="space-y-4 p-4">
              <div>
                <h3 className="text-sm font-semibold">Coordination</h3>
                <p className="mt-0.5 text-xs text-muted">Optional agents that steer or summarize the team.</p>
              </div>
              <Field
                label={form.style === "supervisor" ? "Manager agent (required)" : form.style === "router" ? "Router agent" : "Manager / fallback aggregator"}
                hint={
                  form.style === "supervisor"
                    ? "Plans, delegates to members and writes the final answer."
                    : form.style === "router"
                      ? "Picks the best member. Defaults to the first member."
                      : "Used as aggregator when none is set below."
                }
              >
                <AgentPicker agents={agents} value={form.manager_agent_id} allowEmpty placeholder="None" disabled={readOnly} onChange={(v) => set("manager_agent_id", v)} />
              </Field>
              {(form.style === "parallel" || form.style === "round_robin") && (
                <Field label="Aggregator agent" hint={form.style === "parallel" ? "Merges members' answers into one." : "Writes the final answer if no one ends the chat."}>
                  <AgentPicker agents={agents} value={form.config.aggregator_agent_id ?? ""} allowEmpty placeholder="None" disabled={readOnly} onChange={(v) => setCfg("aggregator_agent_id", v)} />
                </Field>
              )}
              {form.style === "parallel" && (
                <Field label="Max concurrency" hint="How many members run at the same time (default 4).">
                  <Input type="number" min={1} max={20} disabled={readOnly} value={form.config.max_concurrency ?? ""} onChange={(e) => setCfg("max_concurrency", e.target.value ? Number(e.target.value) : undefined)} placeholder="4" />
                </Field>
              )}
              {form.style === "round_robin" && (
                <>
                  <Field label="Max rounds" hint="Each round every member speaks once (1-6).">
                    <Input type="number" min={1} max={6} disabled={readOnly} value={form.config.max_rounds ?? ""} onChange={(e) => setCfg("max_rounds", e.target.value ? Number(e.target.value) : undefined)} placeholder="2" />
                  </Field>
                  <Field label="Termination keyword" hint="A member ends the chat by writing this word.">
                    <Input disabled={readOnly} value={form.config.termination_keyword ?? ""} onChange={(e) => setCfg("termination_keyword", e.target.value)} placeholder="TERMINATE" />
                  </Field>
                </>
              )}
              {form.style === "sequential" && <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">Pipelines don't need a coordinator: the last member's output is the result.</p>}
            </Card>
          </div>
        </div>
      </div>

      {!readOnly && (
        <SaveBar>
          <Button variant="outline" onClick={() => nav("/teams")}>Cancel</Button>
          <Button icon={<Save className="size-4" />} loading={save.isPending} disabled={!valid} onClick={() => save.mutate()}>
            Save team
          </Button>
        </SaveBar>
      )}
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={() => del.mutate()} loading={del.isPending} title="Delete this team?" description="Automations and workflows that use it will fail." />
    </Page>
  );
}
