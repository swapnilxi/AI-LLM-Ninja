import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Download, FileDown, LayoutTemplate, Plus, Slash, Sparkles, Terminal, Wrench } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Skill, SkillTemplate } from "@/modules/skills/types";
import { timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useSkills, useSkillTemplates } from "@/modules/skills/api";
import { useTools } from "@/modules/tools/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, Checkbox, EmptyState, Input, PageLoader, Tabs, Textarea } from "@/shared/ui/primitives";
import { SearchInput } from "@/shared/ui/inputs";
import { IconTile } from "@/shared/ui/icons";
import { Grid, ResourceCard, ScopeBadge } from "@/shared/components/library";

export default function SkillsList() {
  const skills = useSkills();
  const tools = useTools();
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [params, setParams] = useSearchParams();
  const scope = (params.get("tab") as "all" | "org" | "global" | "templates") || "all";
  const setScope = (t: string) => setParams(t === "all" ? {} : { tab: t }, { replace: true });
  const toolName = useMemo(() => Object.fromEntries((tools.data ?? []).map((t) => [t.id, t.display_name || t.name])), [tools.data]);

  const items = (skills.data ?? []).filter(
    (s) => (scope === "all" || (scope === "global" ? s.org_id === null : s.org_id !== null)) && (!q || `${s.name} ${s.description}`.toLowerCase().includes(q.toLowerCase())),
  );

  return (
    <Page>
      <PageHeader
        title="Skills"
        description="Reusable instruction packs (like SKILL.md) that bundle know-how and tools. Attach them to any agent."
        actions={
          can("member") && (
            <>
              <Button variant="outline" icon={<Terminal className="size-4" />} onClick={() => nav("/skills/install")}>
                Install
              </Button>
              <Button variant="outline" icon={<FileDown className="size-4" />} onClick={() => nav("/skills/import")}>
                Import SKILL.md
              </Button>
              <Button icon={<Plus className="size-4" />} onClick={() => nav("/skills/new")}>
                New skill
              </Button>
            </>
          )
        }
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={[
            { key: "all", label: "All", count: skills.data?.length },
            { key: "org", label: "My org" },
            { key: "global", label: "Global library" },
            { key: "templates", label: <><LayoutTemplate className="size-3.5" /> Templates</> },
          ]}
          value={scope}
          onChange={setScope}
        />
        <SearchInput value={q} onChange={setQ} placeholder="Search skills…" className="sm:w-64" />
      </div>
      {scope === "templates" ? (
        <TemplateGallery q={q} />
      ) : skills.isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <EmptyState icon={<Sparkles className="size-5" />} title="No skills found" description="Create a skill to teach agents a repeatable way of working." action={can("member") && <Button onClick={() => nav("/skills/new")}>New skill</Button>} />
      ) : (
        <Grid>
          {items.map((s: Skill) => (
            <ResourceCard
              key={s.id}
              to={`/skills/${s.id}`}
              icon={<IconTile icon={Sparkles} color="violet" />}
              title={s.name}
              subtitle={
                <span className="flex items-center gap-1.5">
                  <ScopeBadge orgId={s.org_id} />
                  {s.command && <Badge tone="primary" className="font-mono">/{s.command}</Badge>}
                </span>
              }
              description={s.description}
              badges={s.tool_ids.slice(0, 4).map((id) => <Badge key={id} tone="muted">{toolName[id] ?? "tool"}</Badge>)}
              footer={`Updated ${timeAgo(s.updated_at)}`}
            />
          ))}
        </Grid>
      )}
    </Page>
  );
}

/** /skills/import: paste a SKILL.md file. */
export function ImportSkillPage() {
  const [md, setMd] = useState("---\nname: My skill\ndescription: What it does\n---\n\n# Instructions\n\n1. …");
  const nav = useNavigate();
  const imp = useAction(() => http.post<Skill>("/skills/import", { markdown: md }), {
    success: "Skill imported",
    invalidate: [["skills"]],
    onSuccess: (s) => nav(`/skills/${s.id}`, { replace: true }),
  });
  return (
    <Page className="max-w-3xl">
      <PageHeader
        back="/skills"
        icon={<IconTile icon={FileDown} color="violet" />}
        title="Import SKILL.md"
        description="Paste a skill file with YAML front matter (name, description) followed by markdown instructions."
      />
      <Card>
        <div className="p-4 sm:p-5">
          <Textarea mono rows={18} autoFocus value={md} onChange={(e) => setMd(e.target.value)} aria-label="SKILL.md content" />
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
          <Button variant="outline" onClick={() => nav("/skills")}>Cancel</Button>
          <Button loading={imp.isPending} disabled={!md.trim()} onClick={() => imp.mutate()}>Import</Button>
        </div>
      </Card>
    </Page>
  );
}

type Candidate = { path: string; name: string };

/** /skills/install: paste `npx skills add owner/repo --skill name`; the server resolves it to SKILL.md files on GitHub (npx is never executed). */
export function InstallSkillPage() {
  const [cmd, setCmd] = useState("");
  const [found, setFound] = useState<{ source: string; items: Candidate[] } | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const nav = useNavigate();
  const find = useAction(() => http.post<{ source: string; items: Candidate[] }>("/skills/install/preview", { command: cmd }), {
    onSuccess: (r) => {
      setFound(r);
      setPicked(r.items.length <= 5 ? r.items.map((i) => i.path) : []);
    },
  });
  const install = useAction(() => http.post<{ results: { id: string; name: string; status: string }[] }>("/skills/install", { command: cmd, paths: picked }), {
    invalidate: [["skills"]],
    onSuccess: (r) => {
      const n = r.results.length;
      toast.success(n === 1 ? `${r.results[0].name} ${r.results[0].status}` : `${n} skills installed`);
      nav(n === 1 ? `/skills/${r.results[0].id}` : "/skills?tab=org", { replace: true });
    },
  });
  const toggle = (path: string) => setPicked((p) => (p.includes(path) ? p.filter((x) => x !== path) : [...p, path]));
  return (
    <Page className="max-w-3xl">
      <PageHeader
        back="/skills"
        icon={<IconTile icon={Terminal} color="violet" />}
        title="Install skill"
        description="Paste an install command. The skill's SKILL.md is downloaded from GitHub and added to your organization."
      />
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (found) {
              if (picked.length) install.mutate();
            } else if (cmd.trim()) find.mutate();
          }}
        >
          <div className="space-y-3 p-4 sm:p-5">
            <Input
              className="font-mono"
              autoFocus
              value={cmd}
              onChange={(e) => {
                setCmd(e.target.value);
                setFound(null);
              }}
              placeholder="npx skills add anthropics/skills --skill pdf"
              aria-label="Install command"
            />
            <p className="text-xs text-muted">
              Accepts <code>npx skills add owner/repo</code>, <code>--skill name</code>, <code>owner/repo@name</code>, a GitHub URL, or just a name (looked up in anthropics/skills).
              AgentForge never runs npx: only the instructions are installed, bundled scripts are ignored.
            </p>
            {found && (
              <div className="rounded-lg border border-border">
                <div className="border-b border-border px-3 py-2 text-xs text-muted">{found.items.length} skill{found.items.length === 1 ? "" : "s"} in {found.source}</div>
                <ul className="max-h-80 divide-y divide-border overflow-y-auto">
                  {found.items.map((i) => (
                    <li key={i.path} className="px-3 py-2">
                      <Checkbox checked={picked.includes(i.path)} onChange={() => toggle(i.path)} label={<span><span className="font-medium">{i.name}</span> <span className="font-mono text-xs text-muted">{i.path}</span></span>} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
            <Button type="button" variant="outline" onClick={() => nav("/skills")}>Cancel</Button>
            {found ? (
              <Button type="submit" icon={<Download className="size-4" />} disabled={!picked.length} loading={install.isPending}>
                Install {picked.length || ""} skill{picked.length === 1 ? "" : "s"}
              </Button>
            ) : (
              <Button type="submit" disabled={!cmd.trim()} loading={find.isPending}>Find skills</Button>
            )}
          </div>
        </form>
      </Card>
    </Page>
  );
}

function TemplateGallery({ q }: { q: string }) {
  const templates = useSkillTemplates();
  const { can } = useAuth();
  const nav = useNavigate();
  const add = useAction((key: string) => http.post<Skill>(`/skills/templates/${key}`), {
    success: "Skill added to your organization",
    invalidate: [["skills"]],
    onSuccess: (s) => nav(`/skills/${s.id}`),
  });
  if (templates.isLoading) return <PageLoader />;
  const items = (templates.data ?? []).filter((t) => !q || `${t.name} ${t.description} ${t.category}`.toLowerCase().includes(q.toLowerCase()));
  const groups = items.reduce<Record<string, SkillTemplate[]>>((acc, t) => ((acc[t.category] ??= []).push(t), acc), {});
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">Ready-made skills with slash commands. Add one to your org, then tweak it or attach it to agents and chats.</p>
      {Object.entries(groups).map(([cat, ts]) => (
        <section key={cat}>
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">{cat}</h2>
          <Grid>
            {ts.map((t) => (
              <Card key={t.key} className="flex flex-col p-4">
                <div className="flex items-start gap-3">
                  <IconTile icon={Sparkles} color="violet" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold">{t.name}</div>
                    <div className="mt-0.5 flex items-center gap-1 font-mono text-xs text-primary">
                      <Slash className="size-3" />
                      {t.command} <span className="truncate text-muted">{t.argument_hint}</span>
                    </div>
                  </div>
                </div>
                <p className="mt-3 line-clamp-2 text-sm text-muted">{t.description}</p>
                {t.tools.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {t.tools.map((x) => <Badge key={x} tone="muted" icon={<Wrench className="size-2.5" />}>{x}</Badge>)}
                  </div>
                )}
                <div className="mt-auto flex justify-end pt-4">
                  <Button size="sm" icon={<Plus className="size-3.5" />} disabled={!can("member")} loading={add.isPending && add.variables === t.key} onClick={() => add.mutate(t.key)}>
                    Add skill
                  </Button>
                </div>
              </Card>
            ))}
          </Grid>
        </section>
      ))}
    </div>
  );
}
