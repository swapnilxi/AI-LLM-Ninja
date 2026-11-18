import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Bot,
  CornerDownLeft,
  FolderKanban,
  LayoutDashboard,
  MessagesSquare,
  Plug,
  Plus,
  Search,
  Settings,
  Sparkles,
  Timer,
  Users,
  Workflow as WorkflowIcon,
  Wrench,
  ArrowLeftRight,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useAgents, useSkills, useTeams, useWorkflows } from "@/hooks/useData";
import { AgentAvatar } from "@/components/ui/icons";

interface Cmd {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: ReactNode;
  keywords?: string;
  run: () => void;
}

/** Global ⌘K / Ctrl+K palette: navigate, chat with any agent or team, open items, switch project. */
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate();
  const { projects, setProjectId, project } = useAuth();
  const agents = useAgents();
  const teams = useTeams();
  const workflows = useWorkflows();
  const skills = useSkills();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const go = (path: string) => () => nav(path);
  const commands: Cmd[] = useMemo(() => {
    const ic = "size-4";
    const pages: Cmd[] = [
      { id: "p-dash", group: "Go to", label: "Dashboard", icon: <LayoutDashboard className={ic} />, run: go("/") },
      { id: "p-chat", group: "Go to", label: "Chat", icon: <MessagesSquare className={ic} />, run: go("/chat") },
      { id: "p-agents", group: "Go to", label: "Agents", icon: <Bot className={ic} />, run: go("/agents") },
      { id: "p-teams", group: "Go to", label: "Teams", icon: <Users className={ic} />, run: go("/teams") },
      { id: "p-wf", group: "Go to", label: "Workflows", icon: <WorkflowIcon className={ic} />, run: go("/workflows") },
      { id: "p-skills", group: "Go to", label: "Skills", icon: <Sparkles className={ic} />, run: go("/skills") },
      { id: "p-tpl", group: "Go to", label: "Skill templates", icon: <Sparkles className={ic} />, keywords: "gallery", run: go("/skills?tab=templates") },
      { id: "p-tools", group: "Go to", label: "Tools", icon: <Wrench className={ic} />, run: go("/tools") },
      { id: "p-conn", group: "Go to", label: "Connectors", icon: <Plug className={ic} />, keywords: "apps integrations mcp", run: go("/connectors") },
      { id: "p-auto", group: "Go to", label: "Automations", icon: <Timer className={ic} />, keywords: "schedule cron webhook", run: go("/automations") },
      { id: "p-runs", group: "Go to", label: "Runs", icon: <Activity className={ic} />, keywords: "history logs", run: go("/runs") },
      { id: "p-proj", group: "Go to", label: "Projects", icon: <FolderKanban className={ic} />, run: go("/projects") },
      { id: "p-set", group: "Go to", label: "Settings", icon: <Settings className={ic} />, keywords: "keys members models providers", run: go("/settings") },
      { id: "p-xfer", group: "Go to", label: "Import / Export library", icon: <ArrowLeftRight className={ic} />, keywords: "backup bundle json", run: go("/settings/transfer") },
    ];
    const create: Cmd[] = [
      { id: "n-agent", group: "Create", label: "New agent", icon: <Plus className={ic} />, run: go("/agents/new") },
      { id: "n-skill", group: "Create", label: "New skill", icon: <Plus className={ic} />, run: go("/skills/new") },
      { id: "n-team", group: "Create", label: "New team", icon: <Plus className={ic} />, run: go("/teams/new") },
      { id: "n-wf", group: "Create", label: "New workflow", icon: <Plus className={ic} />, run: go("/workflows/new") },
    ];
    const ags: Cmd[] = (agents.data ?? []).flatMap((a) => [
      { id: `ac-${a.id}`, group: "Agents", label: `Chat with ${a.name}`, hint: a.description, icon: <AgentAvatar agent={a} size="xs" />, keywords: a.tags.join(" "), run: go(`/chat?agent=${a.id}`) },
      { id: `ao-${a.id}`, group: "Agents", label: `Edit ${a.name}`, icon: <Bot className={ic} />, run: go(`/agents/${a.id}`) },
    ]);
    const tms: Cmd[] = (teams.data ?? []).flatMap((t) => [
      { id: `tc-${t.id}`, group: "Teams", label: `Chat with ${t.name}`, hint: t.style.replace("_", " "), icon: <Users className={ic} />, run: go(`/chat?team=${t.id}`) },
      { id: `to-${t.id}`, group: "Teams", label: `Edit ${t.name}`, icon: <Users className={ic} />, run: go(`/teams/${t.id}`) },
    ]);
    const wfs: Cmd[] = (workflows.data ?? []).map((w) => ({ id: `w-${w.id}`, group: "Workflows", label: w.name, hint: w.description, icon: <WorkflowIcon className={ic} />, run: go(`/workflows/${w.id}`) }));
    const sks: Cmd[] = (skills.data ?? []).map((s) => ({
      id: `s-${s.id}`,
      group: "Skills",
      label: s.name,
      hint: s.command ? `/${s.command}` : s.description,
      icon: <Sparkles className={ic} />,
      keywords: s.command ?? "",
      run: go(`/skills/${s.id}`),
    }));
    const prj: Cmd[] = projects
      .filter((p) => p.id !== project?.id)
      .map((p) => ({ id: `pj-${p.id}`, group: "Switch project", label: p.name, icon: <FolderKanban className={ic} />, run: () => setProjectId(p.id) }));
    return [...create, ...pages, ...ags, ...tms, ...wfs, ...sks, ...prj];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agents.data, teams.data, workflows.data, skills.data, projects, project?.id]);

  const results = useMemo(() => {
    const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    const list = terms.length
      ? commands.filter((c) => {
          const hay = `${c.label} ${c.group} ${c.hint ?? ""} ${c.keywords ?? ""}`.toLowerCase();
          return terms.every((t) => hay.includes(t));
        })
      : commands.filter((c) => c.group === "Go to" || c.group === "Create");
    return list.slice(0, 40);
  }, [q, commands]);

  useEffect(() => setActive(0), [q]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;
  const pick = (c?: Cmd) => {
    if (!c) return;
    onClose();
    c.run();
  };
  let lastGroup = "";
  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-start justify-center px-3 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={onClose} />
      <div className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl">
        <div className="flex items-center gap-2 border-b border-border px-4">
          <Search className="size-4 text-muted" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, results.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                pick(results[active]);
              } else if (e.key === "Escape") onClose();
            }}
            placeholder="Search agents, teams, workflows, skills, pages…"
            className="h-12 flex-1 bg-transparent text-sm focus:outline-none"
          />
          <kbd className="hidden rounded border border-border px-1.5 py-0.5 text-[10px] text-muted sm:block">Esc</kbd>
        </div>
        <div ref={listRef} className="max-h-[55vh] overflow-y-auto p-1.5">
          {results.length === 0 && <div className="px-3 py-8 text-center text-sm text-muted">No matches for “{q}”</div>}
          {results.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <div key={c.id}>
                {header && <div className="px-2.5 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-muted">{header}</div>}
                <button
                  data-idx={i}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => pick(c)}
                  className={cn("flex w-full cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm", i === active ? "bg-primary-soft text-fg" : "text-fg hover:bg-surface-2")}
                >
                  <span className="flex size-6 shrink-0 items-center justify-center text-muted">{c.icon}</span>
                  <span className="min-w-0 flex-1 truncate">{c.label}</span>
                  {c.hint && <span className="hidden max-w-[40%] truncate text-xs text-muted sm:block">{c.hint}</span>}
                  {i === active ? <CornerDownLeft className="size-3.5 text-muted" /> : <ArrowRight className="size-3.5 text-transparent" />}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>,
    document.body,
  );
}

/** Registers the ⌘K / Ctrl+K shortcut. */
export function usePaletteShortcut(setOpen: (fn: (o: boolean) => boolean) => void) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [setOpen]);
}
