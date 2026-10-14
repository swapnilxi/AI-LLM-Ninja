"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Agent, AgentRole, AgentsResponse, api, ApiError, Profile } from "@/lib/api";
import { Icon } from "./Icons";
import { Badge, Card, PageHeader, Spinner, useToast } from "./ui";

const ROLE_ORDER: AgentRole[] = ["planner", "researcher", "critic", "synthesizer"];
const ROLE_LABEL: Record<AgentRole, string> = { planner: "Planner", researcher: "Researcher", critic: "Critic", synthesizer: "Synthesizer" };
const ROLE_TONE: Record<AgentRole, "info" | "ok" | "warn" | "muted"> = { planner: "info", researcher: "ok", critic: "warn", synthesizer: "muted" };
const ALL = "all";

const ago = (t: number | null) => {
  if (!t) return "never";
  const s = Math.max(0, Date.now() / 1000 - t);
  return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`;
};

export default function Agents({ profiles, activeId, onChanged }: { profiles: Profile[]; activeId: string; onChanged?: () => void }) {
  const toast = useToast();
  const [data, setData] = useState<AgentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [business, setBusiness] = useState(ALL);
  const [role, setRole] = useState<AgentRole | typeof ALL>(ALL);
  const [editing, setEditing] = useState<Agent | "new" | null>(null);

  const refresh = useCallback(async () => {
    try { setData(await api<AgentsResponse>("/agents")); }
    catch (e) { toast("bad", (e as Error).message); }
    finally { setLoading(false); }
  }, [toast]);
  useEffect(() => { refresh(); }, [refresh, profiles.length]);

  const fail = (e: unknown) => toast("bad", e instanceof ApiError ? e.message : (e as Error).message);
  const businesses = data?.businesses ?? [];
  const agents = data?.agents ?? [];
  const visible = useMemo(
    () => agents.filter((a) => (business === ALL || a.profile_id === business) && (role === ALL || a.role === role)),
    [agents, business, role],
  );
  // group by business so "All businesses" still reads as teams
  const groups = useMemo(() => {
    const g = new Map<string, Agent[]>();
    for (const a of visible) g.set(a.profile_id, [...(g.get(a.profile_id) ?? []), a]);
    return businesses.filter((b) => g.has(b.id) || business === b.id).map((b) => ({ b, list: (g.get(b.id) ?? []).sort((x, y) => ROLE_ORDER.indexOf(x.role) - ROLE_ORDER.indexOf(y.role) || x.position - y.position) }));
  }, [visible, businesses, business]);

  async function toggle(a: Agent) {
    try { await api(`/agents/${a.id}`, "PATCH", { enabled: !a.enabled }); await refresh(); } catch (e) { fail(e); }
  }
  async function remove(a: Agent) {
    if (!confirm(`Delete agent "${a.name}" from ${a.profile_name}?`)) return;
    try { await api(`/agents/${a.id}`, "DELETE"); toast("ok", "Agent deleted"); await refresh(); } catch (e) { fail(e); }
  }
  async function restore(id: string) {
    try {
      const r = await api<{ added: Agent[] }>(`/profiles/${encodeURIComponent(id)}/agents/defaults`, "POST");
      toast("ok", r.added.length ? `Added ${r.added.length} starter agent${r.added.length > 1 ? "s" : ""}` : "Every starter role is already there");
      await refresh();
    } catch (e) { fail(e); }
  }

  const enabledCount = visible.filter((a) => a.enabled).length;
  const runs = visible.reduce((n, a) => n + a.run_count, 0);
  const errors = visible.reduce((n, a) => n + a.error_count, 0);
  const selected = businesses.find((b) => b.id === business);

  return (
    <div className="page">
      <PageHeader
        title="Agents"
        subtitle="Each business has its own team. In Chat, switch on Agents and the team plans, researches, checks and writes the answer — only from that business's documents."
        actions={<button onClick={() => setEditing("new")} disabled={!businesses.length}><Icon name="plus" size={15} />New agent</button>}
      />

      <div className="tiles compact">
        <div className="tile"><div className="tile-icon"><Icon name="users" size={18} /></div><div><div className="tile-value">{visible.length}</div><div className="tile-label">Agents</div></div></div>
        <div className="tile"><div className="tile-icon"><Icon name="check" size={18} /></div><div><div className="tile-value">{enabledCount}</div><div className="tile-label">Enabled</div></div></div>
        <div className="tile"><div className="tile-icon"><Icon name="zap" size={18} /></div><div><div className="tile-value">{runs}</div><div className="tile-label">Runs</div></div></div>
        <div className="tile"><div className="tile-icon"><Icon name="alert" size={18} /></div><div><div className="tile-value">{errors}</div><div className="tile-label">Failures</div></div></div>
      </div>

      <Card className="table-card">
        <div className="toolbar">
          <label className="chip-select" title="Filter by business">
            <Icon name="database" size={14} />
            <select aria-label="Business" value={business} onChange={(e) => setBusiness(e.target.value)}>
              <option value={ALL}>All businesses</option>
              {businesses.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.agents})</option>)}
            </select>
          </label>
          <div className="chips">
            <button className={`chip ${role === ALL ? "on" : ""}`} onClick={() => setRole(ALL)}>all roles</button>
            {ROLE_ORDER.map((r) => <button key={r} className={`chip ${role === r ? "on" : ""}`} onClick={() => setRole(r)}>{ROLE_LABEL[r]}</button>)}
          </div>
          {selected && <button className="secondary sm" onClick={() => restore(selected.id)} title="Add any missing starter roles (planner, researcher, critic, synthesizer)"><Icon name="refresh" size={14} />Restore starter team</button>}
        </div>

        {loading ? (
          <div className="empty-table"><Spinner size={22} /></div>
        ) : groups.length === 0 ? (
          <div className="empty-table"><Icon name="users" size={28} /><b>{agents.length ? "No agents match" : "No agents yet"}</b>
            <span className="muted small">{agents.length ? "Try another business or role." : "Create the first agent for a business."}</span></div>
        ) : groups.map(({ b, list }) => (
          <section key={b.id} className="agent-group">
            <h4 className="agent-group-title">{b.name}{b.id === activeId && <Badge tone="info">active in chat</Badge>}<span className="muted small">{list.filter((a) => a.enabled).length}/{list.length} enabled</span></h4>
            {list.length === 0 && <div className="muted small agent-empty">No agents for this business. <button className="link" onClick={() => restore(b.id)}>Add the starter team</button></div>}
            <div className="agent-list">
              {list.map((a) => (
                <div key={a.id} className={`agent-item ${a.enabled ? "" : "off"}`}>
                  <div className="agent-main">
                    <div className="row wrap agent-head">
                      <span className="agent-name">{a.name}</span>
                      <Badge tone={ROLE_TONE[a.role]}>{ROLE_LABEL[a.role]}</Badge>
                      {a.model && <Badge tone="muted">{a.model}</Badge>}
                    </div>
                    {a.description && <div className="muted small">{a.description}</div>}
                    {a.instructions && <div className="agent-instr">{a.instructions}</div>}
                    <div className="row wrap faq-meta muted small">
                      {a.focus && <span>focus: <code>{a.focus}</code></span>}
                      <span>{a.run_count} run{a.run_count === 1 ? "" : "s"}</span>
                      <span>last run {ago(a.last_run_at)}</span>
                      {a.error_count > 0 && <span className="error small" title={a.last_error}>{a.error_count} failure{a.error_count === 1 ? "" : "s"}</span>}
                    </div>
                  </div>
                  <div className="faq-actions">
                    <label className="switch" title={a.enabled ? "Enabled — click to disable" : "Disabled — click to enable"}>
                      <input type="checkbox" checked={a.enabled} onChange={() => toggle(a)} /><span />
                    </label>
                    <button className="icon-btn" title="Edit" onClick={() => setEditing(a)}><Icon name="edit" size={15} /></button>
                    <button className="icon-btn danger" title="Delete" onClick={() => remove(a)}><Icon name="trash" size={15} /></button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </Card>

      <Card title="How the team runs" icon="info">
        <ol className="agent-flow muted small">
          {ROLE_ORDER.map((r) => <li key={r}><b>{ROLE_LABEL[r]}</b> — {data?.roles[r]}</li>)}
        </ol>
        <p className="muted small">Only the first enabled planner, critic and synthesizer run; up to {data?.max_researchers ?? 4} researchers run. Helper agents that fail are skipped; the answer is still written.</p>
      </Card>

      {editing && data && (
        <AgentDialog agent={editing === "new" ? null : editing} businesses={businesses}
          defaultBusiness={business !== ALL ? business : activeId || businesses[0]?.id}
          onClose={() => setEditing(null)} onSaved={async () => { setEditing(null); await refresh(); onChanged?.(); }} />
      )}
    </div>
  );
}

function AgentDialog({ agent, businesses, defaultBusiness, onClose, onSaved }: {
  agent: Agent | null; businesses: AgentsResponse["businesses"]; defaultBusiness: string; onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [profileId, setProfileId] = useState(agent?.profile_id ?? defaultBusiness);
  const [name, setName] = useState(agent?.name ?? "");
  const [role, setRole] = useState<AgentRole>(agent?.role ?? "researcher");
  const [description, setDescription] = useState(agent?.description ?? "");
  const [instructions, setInstructions] = useState(agent?.instructions ?? "");
  const [focus, setFocus] = useState(agent?.focus ?? "");
  const [model, setModel] = useState(agent?.model ?? "");
  const [enabled, setEnabled] = useState(agent?.enabled ?? true);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const body = { name, role, description, instructions, focus, model, enabled };
      if (agent) await api(`/agents/${agent.id}`, "PATCH", body);
      else await api("/agents", "POST", { ...body, profile_id: profileId });
      toast("ok", agent ? "Agent updated" : "Agent created");
      onSaved();
    } catch (e) { toast("bad", e instanceof ApiError ? e.message : (e as Error).message); }
    finally { setSaving(false); }
  }

  return (
    <>
      <div className="scrim light" onClick={onClose} />
      <div className="modal card" role="dialog" aria-label={agent ? "Edit agent" : "New agent"}>
        <div className="card-head"><h3>{agent ? "Edit agent" : "New agent"}</h3><button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button></div>
        <div className="form">
          <label>Business
            <select value={profileId} disabled={!!agent} onChange={(e) => setProfileId(e.target.value)}>
              {businesses.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </label>
          <label>Name<input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="Policy researcher" autoFocus /></label>
          <label>Role
            <select value={role} onChange={(e) => setRole(e.target.value as AgentRole)}>
              {ROLE_ORDER.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </select>
          </label>
          <label>Description <span className="muted small">(optional)</span><input value={description} maxLength={300} onChange={(e) => setDescription(e.target.value)} placeholder="What this agent is for" /></label>
          <label>Instructions <span className="muted small">(optional)</span>
            <textarea rows={5} value={instructions} maxLength={8000} onChange={(e) => setInstructions(e.target.value)} placeholder="e.g. Focus on refund and warranty policies. Quote exact time limits." />
          </label>
          {role === "researcher" && (
            <label>Search focus <span className="muted small">(optional — added to every query this agent runs)</span>
              <input value={focus} maxLength={200} onChange={(e) => setFocus(e.target.value)} placeholder="refund policy warranty" />
            </label>
          )}
          <label>Model override <span className="muted small">(optional — same provider as Settings)</span>
            <input value={model} maxLength={100} onChange={(e) => setModel(e.target.value)} placeholder="leave empty for the default model" />
          </label>
          <label className="check"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />Enabled</label>
        </div>
        <div className="row modal-actions">
          <button onClick={save} disabled={saving || !name.trim() || !profileId}>{saving ? <Spinner size={14} /> : agent ? "Save" : "Create"}</button>
          <button className="secondary" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </>
  );
}
