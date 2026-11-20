import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheck,
  Blocks,
  BookOpen,
  Check,
  Compass,
  Download,
  ExternalLink,
  FolderKanban,
  Palette,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  TriangleExclamationPoint,
  Users,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { http, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { HubKnowledge, HubSkillPack, RegistrySkill, Trust } from "@/lib/types";
import { cn, errMsg, formatNumber } from "@/lib/utils";
import { useAction, useHub } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, Card, EmptyState, PageLoader, Spinner, Switch, Tabs } from "@/components/ui/primitives";
import { SearchInput } from "@/components/ui/inputs";
import { IconTile } from "@/components/ui/icons";
import { Grid } from "@/components/library";
import { McpServerGrid } from "@/components/hub/McpServers";

type Tab = "skills" | "connectors" | "knowledge";

const CATEGORY: Record<string, { icon: LucideIcon; color: string }> = {
  "Skills ecosystem": { icon: Compass, color: "indigo" },
  "Design & frontend": { icon: Palette, color: "violet" },
  Engineering: { icon: Terminal, color: "slate" },
  Security: { icon: ShieldCheck, color: "emerald" },
  "Agent building blocks": { icon: Blocks, color: "sky" },
};

function TrustBadge({ trust }: { trust: Trust }) {
  if (trust === "official") return <Badge tone="success" icon={<BadgeCheck className="size-3" />}>Official</Badge>;
  if (trust === "built-in") return <Badge tone="primary" icon={<Sparkles className="size-3" />}>Built in</Badge>;
  return <Badge tone="warning" icon={<Users className="size-3" />}>Community</Badge>;
}

export default function Discover() {
  const { project, projectId, can } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = (["skills", "connectors", "knowledge"].includes(params.get("tab") ?? "") ? params.get("tab") : "skills") as Tab;
  const hub = useHub(projectId);
  const [attach, setAttach] = useState(true);
  const setTab = (t: Tab) => setParams(t === "skills" ? {} : { tab: t }, { replace: true });

  return (
    <Page>
      <PageHeader
        title="Discover"
        description="Install top skills, tools and connectors in one click. Attach them to a project and every agent running there can use them."
      />

      <Card className="mb-5 flex flex-col gap-3 bg-gradient-to-br from-primary-soft/60 via-transparent to-transparent p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <IconTile icon={FolderKanban} color="indigo" size="sm" />
          <div className="text-sm">
            <div className="font-medium">{project ? `Project: ${project.name}` : "No active project"}</div>
            <div className="text-muted">Switch project from the sidebar. Installs are shared by your organization; attaching is per project.</div>
          </div>
        </div>
        <Switch checked={attach && !!projectId} disabled={!projectId} onChange={setAttach} label="Attach to project on install" />
      </Card>

      <Tabs
        className="mb-5"
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "skills", label: "Skills", count: hub.data?.skills.length },
          { key: "connectors", label: "Connectors (MCP)", count: hub.data?.mcp.length },
          { key: "knowledge", label: "Knowledge", count: hub.data?.knowledge.length },
        ]}
      />

      {hub.isLoading ? (
        <PageLoader />
      ) : hub.isError || !hub.data ? (
        <EmptyState title="Could not load the catalog" description={errMsg(hub.error)} />
      ) : tab === "skills" ? (
        <SkillsTab packs={hub.data.skills} projectId={attach ? projectId : null} projectName={project?.name} canInstall={can("member")} />
      ) : tab === "connectors" ? (
        <div className="space-y-5">
          <p className="max-w-3xl text-sm text-muted">
            Remote MCP servers over HTTPS. Their tools become available to agents. Looking for GitHub, Slack, Notion, Linear, Jira, email or a REST API?{" "}
            <Link to="/connectors" className="text-primary hover:underline">Browse app connectors</Link>.
          </p>
          <McpServerGrid servers={[...hub.data.mcp].sort((a, b) => Number(b.popular) - Number(a.popular))} projectId={attach ? projectId : null} projectName={project?.name} />
          <p className="text-xs text-muted">Servers that only support OAuth sign-in, and servers on a private network (such as a local agentmemory), are not supported yet. Expose a local server on a public HTTPS URL and add it as a custom MCP connector.</p>
        </div>
      ) : (
        <KnowledgeTab docs={hub.data.knowledge} projectId={projectId} projectName={project?.name} canInstall={can("member")} />
      )}
    </Page>
  );
}

/* ------------------------------------------------------------------ skills */
function SkillsTab({ packs, projectId, projectName, canInstall }: { packs: HubSkillPack[]; projectId?: string | null; projectName?: string; canInstall: boolean }) {
  const categories = useMemo(() => Array.from(new Set(packs.map((p) => p.category))), [packs]);
  const featured = packs.find((p) => p.id === "find-skills");
  return (
    <div className="space-y-8">
      <RegistrySearch projectId={projectId} projectName={projectName} canInstall={canInstall} />
      {categories.map((cat) => (
        <section key={cat}>
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-muted">{cat}</h2>
          <Grid>
            {packs
              .filter((p) => p.category === cat)
              .map((p) => (
                <PackCard key={p.id} pack={p} recommended={p.id === featured?.id} projectId={projectId} projectName={projectName} canInstall={canInstall} />
              ))}
          </Grid>
        </section>
      ))}
    </div>
  );
}

function PackCard({ pack: p, recommended, projectId, projectName, canInstall }: { pack: HubSkillPack; recommended?: boolean; projectId?: string | null; projectName?: string; canInstall: boolean }) {
  const qc = useQueryClient();
  const meta = CATEGORY[p.category] ?? CATEGORY["Skills ecosystem"];
  const refresh = () => ["hub", "skills", "projects", "project"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const install = useAction(() => http.post<{ results: { name: string; status: string }[]; attached: boolean }>("/hub/skills/install", { pack_id: p.id, project_id: projectId ?? undefined }), {
    invalidate: [],
    onSuccess: (r) => {
      toast.success(`${p.name} ${r.results.some((x) => x.status === "updated") ? "updated" : "installed"}${r.attached ? ` and added to ${projectName ?? "the project"}` : ""}`);
      refresh();
    },
  });
  const detach = useAction(
    async () => {
      const cur = await http.get<{ settings: { skill_ids?: string[] } }>(`/projects/${projectId}`);
      return http.patch(`/projects/${projectId}`, { settings: { skill_ids: (cur.settings.skill_ids ?? []).filter((id) => !p.skill_ids.includes(id)) } });
    },
    { success: `Removed from ${projectName ?? "the project"}`, onSuccess: refresh },
  );
  const tokens = Math.round(p.instruction_chars / 4);

  return (
    <Card className={cn("flex flex-col p-4 transition-all hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/5", recommended && "border-indigo-500/30 bg-gradient-to-br from-primary-soft/40 to-transparent")}>
      <div className="flex items-start gap-3">
        <IconTile icon={meta.icon} color={meta.color} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold">{p.name}</h3>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <TrustBadge trust={p.trust} />
            {recommended && <Badge tone="primary">Recommended</Badge>}
            {p.installed && <Badge tone="success" icon={<Check className="size-3" />}>Installed</Badge>}
          </div>
        </div>
      </div>
      <p className="mt-3 text-sm font-medium">{p.tagline}</p>
      <p className="mt-1 text-sm text-muted">{p.description}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {p.skills.slice(0, 5).map((s) => (
          <Badge key={s} tone="muted" className="font-mono">{s}</Badge>
        ))}
        {p.skills.length > 5 && <Badge tone="muted">+{p.skills.length - 5} more</Badge>}
      </div>
      {p.caveat && (
        <p className="mt-3 flex gap-1.5 text-xs text-muted">
          <TriangleExclamationPoint className="mt-0.5 size-3.5 shrink-0 text-warning" /> {p.caveat}
        </p>
      )}
      {p.attached && tokens > 0 && <p className="mt-2 text-[11px] text-muted">About {formatNumber(tokens)} tokens added to every agent prompt in this project. Large sets are loaded on demand.</p>}
      <div className="mt-auto flex items-center justify-between gap-2 pt-4">
        <a href={p.repo_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
          Source <ExternalLink className="size-3" />
        </a>
        {!canInstall ? (
          <span className="text-xs text-muted">Members only</span>
        ) : p.installed && p.attached ? (
          <Button size="sm" variant="outline" loading={detach.isPending} onClick={() => detach.mutate()}>Remove from project</Button>
        ) : (
          <Button size="sm" icon={p.installed ? <Plus className="size-3.5" /> : <Download className="size-3.5" />} loading={install.isPending} onClick={() => install.mutate()}>
            {p.installed ? (projectId ? "Add to project" : "Update") : projectId ? "Install to project" : "Install"}
          </Button>
        )}
      </div>
    </Card>
  );
}

function RegistrySearch({ projectId, projectName, canInstall }: { projectId?: string | null; projectName?: string; canInstall: boolean }) {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 350);
    return () => clearTimeout(t);
  }, [q]);
  const results = useQuery({
    queryKey: ["hub", "registry", debounced],
    queryFn: () => http.get<{ results: RegistrySkill[]; error: string | null }>(`/hub/skills/search${qs({ q: debounced, limit: 12 })}`),
    enabled: debounced.length >= 2,
    staleTime: 300_000,
  });
  const [busy, setBusy] = useState<string | null>(null);
  const install = async (r: RegistrySkill) => {
    setBusy(r.ref);
    try {
      const res = await http.post<{ attached: boolean }>("/hub/skills/install", { source: r.source, skill: r.skill, project_id: projectId ?? undefined });
      toast.success(`${r.name} installed${res.attached ? ` and added to ${projectName ?? "the project"}` : ""}`);
      ["hub", "skills", "projects", "project"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-0.5">
        <h2 className="flex items-center gap-2 text-sm font-semibold"><Search className="size-4 shrink-0 text-primary" /> Search all skills</h2>
        <span className="text-xs text-muted">from the public skills.sh registry, most installed first</span>
      </div>
      <SearchInput value={q} onChange={setQ} placeholder="e.g. react, pdf, security review, seo…" />
      {debounced.length >= 2 && (
        <div className="mt-3">
          {results.isFetching && !results.data ? (
            <div className="flex justify-center py-4"><Spinner /></div>
          ) : results.data?.error ? (
            <p className="text-sm text-danger">{results.data.error}</p>
          ) : !results.data?.results.length ? (
            <p className="text-sm text-muted">No skills found for “{debounced}”.</p>
          ) : (
            <ul className="divide-y divide-border">
              {results.data.results.map((r) => (
                <li key={r.ref} className="flex items-center gap-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-mono text-sm font-medium">{r.name}</div>
                    <div className="truncate text-xs text-muted">{r.source} · {formatNumber(r.installs)} installs</div>
                  </div>
                  {r.installed && <Badge tone="success">Installed</Badge>}
                  {canInstall && (
                    <Button size="sm" variant="outline" icon={<Download className="size-3.5" />} loading={busy === r.ref} onClick={() => install(r)}>
                      {projectId ? "Install to project" : "Install"}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 flex gap-1.5 text-xs text-muted">
            <TriangleExclamationPoint className="mt-0.5 size-3.5 shrink-0 text-warning" />
            Registry skills are written by third parties and steer your agents. Instructions are copied as text and never executed, but read a skill before you attach it.
          </p>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------------ knowledge */
function KnowledgeTab({ docs, projectId, projectName, canInstall }: { docs: HubKnowledge[]; projectId?: string | null; projectName?: string; canInstall: boolean }) {
  const qc = useQueryClient();
  const add = useAction((id: string) => http.post("/hub/knowledge/install", { item_id: id, project_id: projectId }), {
    success: `Added to ${projectName ?? "the project"}'s knowledge`,
    onSuccess: () => ["hub", "documents"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })),
  });
  if (!projectId) return <EmptyState title="Pick a project first" description="Knowledge documents are added to a project so its agents can search them." />;
  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-muted">
        Reference lists that are not installable skills. They are added to the project's knowledge so agents can search them with knowledge_search. Manage them under{" "}
        <Link to={`/projects/${projectId}`} className="text-primary hover:underline">project settings</Link>.
      </p>
      <Grid>
        {docs.map((d) => (
          <Card key={d.id} className="flex flex-col p-4">
            <div className="flex items-start gap-3">
              <IconTile icon={BookOpen} color="amber" />
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold">{d.name}</h3>
                <div className="mt-1 flex gap-1.5">
                  <TrustBadge trust={d.trust} />
                  {d.installed && <Badge tone="success" icon={<Check className="size-3" />}>In project</Badge>}
                </div>
              </div>
            </div>
            <p className="mt-3 text-sm font-medium">{d.tagline}</p>
            <p className="mt-1 text-sm text-muted">{d.description}</p>
            <div className="mt-auto flex items-center justify-between gap-2 pt-4">
              <a href={d.repo_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
                Source <ExternalLink className="size-3" />
              </a>
              {canInstall && (
                <Button size="sm" icon={<Plus className="size-3.5" />} disabled={!!d.installed} loading={add.isPending && add.variables === d.id} onClick={() => add.mutate(d.id)}>
                  {d.installed ? "Added" : "Add to project"}
                </Button>
              )}
            </div>
          </Card>
        ))}
      </Grid>
    </div>
  );
}
