import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Plug } from "lucide-react";
import { useConnections } from "@/modules/connectors/api";
import { useTools } from "@/modules/tools/api";
import { Badge, Card, CardHeader, Switch } from "@/shared/ui/primitives";
import { MultiSelect } from "@/shared/ui/inputs";
import { useAgentWorkspace } from "../context";
import { CAPABILITIES, capabilityOn } from "../parts";

export default function ToolsSection() {
  const { form, set, setSetting, readOnly, leave } = useAgentWorkspace();
  const tools = useTools();
  const connections = useConnections();

  const toolOptions = useMemo(
    () =>
      (tools.data ?? [])
        .filter((t) => t.enabled || form.tool_ids.includes(t.id))
        .map((t) => ({ value: t.id, label: t.display_name || t.name, description: t.description, badge: t.kind === "builtin" ? t.category : t.kind })),
    [tools.data, form.tool_ids],
  );
  const connectionOptions = useMemo(
    () => (connections.data ?? []).map((c) => ({ value: c.id, label: `${c.connector_name} · ${c.name}`, description: c.enabled ? `Status: ${c.status}` : "Disabled", badge: c.connector_key })),
    [connections.data],
  );

  return (
    <fieldset disabled={readOnly} className="min-w-0">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <CardHeader title="Capabilities" description="Built-in abilities. Project policies can still restrict them (for example, web access off)." />
          <div className="grid gap-x-8 px-4 sm:grid-cols-2 sm:px-5">
            {CAPABILITIES.map((c) => (
              <div key={c.key} className="border-b border-border py-3 last:border-b-0 sm:[&:nth-last-child(2)]:border-b-0">
                <Switch
                  checked={capabilityOn(form.settings, c.key)}
                  onChange={(v) => setSetting(c.key, v)}
                  disabled={readOnly}
                  label={
                    <span className="inline-flex items-center gap-2">
                      <c.icon className="size-4 text-primary" /> {c.label}
                    </span>
                  }
                  description={c.description}
                />
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Tools"
            description="Built-in and custom tools this agent can call."
            actions={
              <>
                <Badge tone="muted">{form.tool_ids.length} selected</Badge>
                <Link to="/tools" onClick={(e) => { e.preventDefault(); leave("/tools"); }} className="inline-flex items-center gap-0.5 text-xs font-medium text-primary hover:underline">
                  Manage <ArrowUpRight className="size-3" />
                </Link>
              </>
            }
          />
          <div className="p-3">
            <MultiSelect options={toolOptions} value={form.tool_ids} onChange={(v) => set("tool_ids", v)} emptyText={tools.isLoading ? "Loading…" : "No tools available"} />
          </div>
        </Card>

        <Card>
          <CardHeader
            title="App connectors"
            description="Connections installed in Connectors. Their actions become tools (projects can also share connectors with every agent)."
            actions={connectionOptions.length > 0 ? <Badge tone="muted">{form.connection_ids.length} selected</Badge> : undefined}
          />
          <div className="p-3">
            {connectionOptions.length === 0 ? (
              <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-3 py-8 text-center text-sm text-muted">
                <Plug className="size-5 text-primary" />
                No connections yet.
                <button type="button" className="cursor-pointer font-medium text-primary hover:underline" onClick={() => leave("/connectors")}>
                  Connect an app
                </button>
              </div>
            ) : (
              <MultiSelect options={connectionOptions} value={form.connection_ids} onChange={(v) => set("connection_ids", v)} />
            )}
          </div>
        </Card>
      </div>
    </fieldset>
  );
}
