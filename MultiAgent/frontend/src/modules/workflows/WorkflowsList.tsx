import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GitBranch, Play, Plus, Workflow as WorkflowIcon } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { timeAgo } from "@/shared/lib/utils";
import { useWorkflows } from "@/modules/workflows/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Badge, Button, EmptyState, PageLoader, Tabs } from "@/shared/ui/primitives";
import { SearchInput } from "@/shared/ui/inputs";
import { IconTile } from "@/shared/ui/icons";
import { Grid, ResourceCard, ScopeBadge } from "@/shared/components/library";
import { withReturn } from "@/shared/hooks/useReturnTo";

export default function WorkflowsList() {
  const wfs = useWorkflows();
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"all" | "org" | "global">("all");

  const items = (wfs.data ?? []).filter(
    (w) => (scope === "all" || (scope === "global" ? w.org_id === null : w.org_id !== null)) && (!q || `${w.name} ${w.description}`.toLowerCase().includes(q.toLowerCase())),
  );

  return (
    <Page>
      <PageHeader
        title="Workflows"
        description="Visual pipelines: chain agents, teams, tools, LLM calls and conditions into a DAG. Independent branches run in parallel."
        actions={can("member") && <Button icon={<Plus className="size-4" />} onClick={() => nav("/workflows/new")}>New workflow</Button>}
      />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          tabs={[
            { key: "all", label: "All", count: wfs.data?.length },
            { key: "org", label: "My org" },
            { key: "global", label: "Global library" },
          ]}
          value={scope}
          onChange={setScope}
        />
        <SearchInput value={q} onChange={setQ} placeholder="Search workflows…" className="sm:w-64" />
      </div>
      {wfs.isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<WorkflowIcon className="size-5" />}
          title="No workflows found"
          description="Build a pipeline visually: drag nodes, connect them and run."
          action={can("member") && <Button onClick={() => nav("/workflows/new")}>New workflow</Button>}
        />
      ) : (
        <Grid>
          {items.map((w) => {
            const nodes = w.graph?.nodes ?? [];
            const types = Array.from(new Set(nodes.map((n) => n.type))).filter((t) => t !== "input" && t !== "output");
            const branches = nodes.filter((n) => n.type === "condition").length;
            return (
              <ResourceCard
                key={w.id}
                to={`/workflows/${w.id}`}
                icon={<IconTile icon={WorkflowIcon} color="teal" />}
                title={w.name}
                subtitle={<ScopeBadge orgId={w.org_id} />}
                description={w.description}
                badges={
                  <>
                    <Badge tone="muted">{nodes.length} nodes</Badge>
                    {branches > 0 && <Badge tone="muted" icon={<GitBranch className="size-2.5" />}>{branches} branch{branches > 1 ? "es" : ""}</Badge>}
                    {types.slice(0, 3).map((t) => <Badge key={t} tone="muted" className="capitalize">{t}</Badge>)}
                  </>
                }
                footer={`Updated ${timeAgo(w.updated_at)}`}
                actions={
                  can("member") && (
                    <Button
                      size="icon"
                      className="size-8"
                      title="Run workflow"
                      onClick={(e) => {
                        e.preventDefault();
                        nav(withReturn(`/runs/new?target_type=workflow&target_id=${w.id}`, "/workflows"));
                      }}
                    >
                      <Play className="size-3.5" />
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
