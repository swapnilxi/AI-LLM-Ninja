import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plug, Plus, Wrench } from "lucide-react";
import { useAuth } from "@/lib/auth";
import type { Tool } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useTools } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Badge, Button, EmptyState, PageLoader } from "@/components/ui/primitives";
import { SearchInput } from "@/components/ui/inputs";
import { IconTile } from "@/components/ui/icons";
import { Grid, ResourceCard, ScopeBadge } from "@/components/library";
import { toolIcon } from "./parts";

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <div className="mb-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="text-xs text-muted">{description}</p>
      </div>
      {children}
    </section>
  );
}

export default function ToolsList() {
  const tools = useTools();
  const { can } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const match = (t: Tool) => !q || `${t.name} ${t.display_name} ${t.description} ${t.category}`.toLowerCase().includes(q.toLowerCase());
  const builtin = (tools.data ?? []).filter((t) => t.kind === "builtin" && match(t));
  const custom = (tools.data ?? []).filter((t) => t.kind !== "builtin" && match(t));

  const card = (t: Tool) => {
    const ic = toolIcon(t);
    return (
      <ResourceCard
        key={t.id}
        to={`/tools/${t.id}`}
        icon={<IconTile icon={ic.icon} color={ic.color} />}
        title={t.display_name || t.name}
        subtitle={<span className="font-mono text-[11px]">{t.name}</span>}
        description={t.description}
        badges={
          <>
            {t.kind === "builtin" ? <Badge tone="primary">{t.category}</Badge> : <ScopeBadge orgId={t.org_id} />}
            {t.kind !== "builtin" && <Badge tone="muted">{t.kind === "http" ? "HTTP API" : "Agent as tool"}</Badge>}
            {!t.enabled && <Badge tone="warning">Disabled</Badge>}
            <Badge tone="muted">{Object.keys(t.parameters?.properties ?? {}).length} params</Badge>
          </>
        }
        footer={t.kind === "builtin" ? "Built-in" : `Updated ${timeAgo(t.updated_at)}`}
      />
    );
  };

  return (
    <Page>
      <PageHeader
        title="Tools"
        description="Functions agents can call. Built-in tools ship with the platform; add custom HTTP API tools or wrap an agent as a tool."
        actions={can("member") && <Button icon={<Plus className="size-4" />} onClick={() => nav("/tools/new")}>New tool</Button>}
      />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link
          to="/connectors"
          className="flex items-center gap-2 rounded-lg border border-border bg-gradient-to-r from-primary-soft/70 to-transparent px-3 py-2 text-sm hover:border-indigo-500/30"
        >
          <Plug className="size-4 text-primary" />
          <span className="text-muted">
            App tools (GitHub, Slack, Notion, MCP…) come from <span className="font-medium text-fg">Connectors</span>
          </span>
        </Link>
        <SearchInput value={q} onChange={setQ} placeholder="Search tools…" className="sm:w-64" />
      </div>
      {tools.isLoading ? (
        <PageLoader />
      ) : (
        <>
          <Section title="Built-in" description="Available to every organization. Toggle web, memory and knowledge per agent; projects can restrict web access.">
            {builtin.length ? <Grid>{builtin.map(card)}</Grid> : <p className="text-sm text-muted">No matching built-in tools.</p>}
          </Section>
          <Section title="Custom" description="Your organization's HTTP API tools and agent-as-tool wrappers.">
            {custom.length ? (
              <Grid>{custom.map(card)}</Grid>
            ) : (
              <EmptyState
                icon={<Wrench className="size-5" />}
                title={q ? "No matching custom tools" : "No custom tools yet"}
                description="Turn any REST endpoint into a tool with templated URL, headers and body - or let one agent call another."
                action={can("member") && !q && <Button onClick={() => nav("/tools/new")}>New tool</Button>}
              />
            )}
          </Section>
        </>
      )}
    </Page>
  );
}
