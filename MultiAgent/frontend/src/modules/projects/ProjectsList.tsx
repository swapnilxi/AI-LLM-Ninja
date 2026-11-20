import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Archive, Check, FolderKanban, Globe, GlobeLock, Plus } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Project } from "@/modules/projects/types";
import { timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, Card, Checkbox, EmptyState, Field, Input, PageLoader, Textarea } from "@/shared/ui/primitives";
import { SearchInput } from "@/shared/ui/inputs";
import { useReturnTo } from "@/shared/hooks/useReturnTo";
import { IconTile } from "@/shared/ui/icons";
import { Grid, ResourceCard } from "@/shared/components/library";

export default function ProjectsList() {
  const { org, projectId, setProjectId, can } = useAuth();
  const [showArchived, setShowArchived] = useState(false);
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const projects = useQuery({
    queryKey: ["projects", org?.id, "with-archived"],
    queryFn: () => http.get<Project[]>("/projects?include_archived=true"),
    enabled: !!org,
  });
  const items = (projects.data ?? []).filter((p) => (showArchived || !p.archived) && (!q || `${p.name} ${p.description}`.toLowerCase().includes(q.toLowerCase())));

  return (
    <Page>
      <PageHeader
        title="Projects"
        description="Projects give agents their working context: a brief, variables, documents, shared memory, tools, connectors and policies. Agents themselves stay reusable across projects."
        actions={can("member") && <Button icon={<Plus className="size-4" />} onClick={() => nav("/projects/new")}>New project</Button>}
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Checkbox checked={showArchived} onChange={setShowArchived} label={<span className="text-muted">Show archived</span>} />
        <SearchInput value={q} onChange={setQ} placeholder="Search projects…" className="sm:w-64" />
      </div>
      {projects.isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <EmptyState icon={<FolderKanban className="size-5" />} title="No projects found" action={can("member") && <Button onClick={() => nav("/projects/new")}>New project</Button>} />
      ) : (
        <Grid>
          {items.map((p) => {
            const active = p.id === projectId;
            const web = p.settings?.web_access !== false;
            return (
              <ResourceCard
                key={p.id}
                to={`/projects/${p.id}`}
                icon={<IconTile icon={FolderKanban} color={active ? "indigo" : "slate"} />}
                title={p.name}
                subtitle={
                  <span className="inline-flex items-center gap-1.5">
                    {active && <Badge tone="primary" icon={<Check className="size-2.5" />}>Active</Badge>}
                    {p.archived && <Badge tone="muted" icon={<Archive className="size-2.5" />}>Archived</Badge>}
                    <span>Updated {timeAgo(p.updated_at)}</span>
                  </span>
                }
                description={p.description || "No description"}
                badges={
                  <>
                    <Badge tone="muted" icon={web ? <Globe className="size-2.5" /> : <GlobeLock className="size-2.5" />}>{web ? "Web on" : "Web off"}</Badge>
                    {Object.keys(p.variables ?? {}).length > 0 && <Badge tone="muted">{Object.keys(p.variables).length} variables</Badge>}
                    {(p.settings?.connection_ids?.length ?? 0) > 0 && <Badge tone="muted">{p.settings.connection_ids!.length} connectors</Badge>}
                    {p.context && <Badge tone="muted">Has brief</Badge>}
                  </>
                }
                actions={
                  !active &&
                  !p.archived && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.preventDefault();
                        setProjectId(p.id);
                      }}
                    >
                      Set active
                    </Button>
                  )
                }
              />
            );
          })}
        </Grid>
      )}
    </Page>
  );
}

/** /projects/new */
export function NewProjectPage() {
  const nav = useNavigate();
  const { setProjectId } = useAuth();
  const back = useReturnTo("/projects");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = useAction(() => http.post<Project>("/projects", { name, description }), {
    success: "Project created",
    invalidate: [["projects"]],
    onSuccess: (p) => {
      setProjectId(p.id);
      nav(`/projects/${p.id}`, { replace: true });
    },
  });
  return (
    <Page className="max-w-2xl">
      <PageHeader back={back} icon={<IconTile icon={FolderKanban} color="indigo" />} title="New project" description="You can add a brief, documents, tools and policies next." />
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <div className="space-y-4 p-4 sm:p-5">
            <Field label="Name">
              <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Q3 market research" />
            </Field>
            <Field label="Description">
              <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What is this project about?" />
            </Field>
          </div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
            <Button type="button" variant="outline" onClick={() => nav(back)}>Cancel</Button>
            <Button type="submit" loading={create.isPending} disabled={!name.trim()}>Create project</Button>
          </div>
        </form>
      </Card>
    </Page>
  );
}
