import { useMemo } from "react";
import { Trash2, WandSparkles } from "lucide-react";
import type { Agent, Catalog, ProviderInfo, Team, Tool } from "@/lib/types";
import { Button, Checkbox, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { AgentAvatar, IconTile } from "@/components/ui/icons";
import { NODE_META, type FlowNode, type NodeData } from "./nodes";

export function TemplateHelp({ nodeIds }: { nodeIds: string[] }) {
  const rows: [string, string][] = [
    ["{{ input.x }}", "run input field x"],
    ["{{ last }}", "output of the upstream node(s)"],
    ["{{ nodes.<id>.output }}", "output of a specific node"],
    ["{{ vars.x }}", "project variable x"],
    ["{{ project.name }}", "active project name"],
  ];
  return (
    <div className="rounded-lg border border-border bg-surface-2/60 p-3 text-[11px]">
      <div className="mb-1.5 font-medium text-muted">Template variables (sandboxed Jinja)</div>
      <dl className="space-y-1">
        {rows.map(([k, v]) => (
          <div key={k} className="flex flex-wrap gap-x-2">
            <dt className="font-mono text-fg">{k}</dt>
            <dd className="text-muted">{v}</dd>
          </div>
        ))}
      </dl>
      {nodeIds.length > 0 && (
        <div className="mt-2 text-muted">
          Node ids: <span className="font-mono text-fg">{nodeIds.join(", ")}</span>
        </div>
      )}
    </div>
  );
}

export function NodeConfig({
  node,
  onChange,
  onDelete,
  readOnly,
  agents,
  teams,
  tools,
  catalog,
  providers,
  nodeIds,
}: {
  node: FlowNode;
  onChange: (data: NodeData) => void;
  onDelete: () => void;
  readOnly: boolean;
  agents: Agent[];
  teams: Team[];
  tools: Tool[];
  catalog?: Catalog;
  providers: ProviderInfo[];
  nodeIds: string[];
}) {
  const type = node.type ?? "template";
  const d = node.data;
  const meta = NODE_META[type] ?? NODE_META.template;
  const set = (k: string, v: any) => onChange({ ...d, [k]: v });
  const custom = tools.filter((t) => t.kind !== "builtin" && t.enabled);
  const toolValue = d.tool_key ? `builtin:${d.tool_key}` : d.tool_id ? `tool:${d.tool_id}` : "";
  const toolParams = useMemo(() => {
    if (d.tool_key) return catalog?.builtin_tools.find((b) => b.key === d.tool_key)?.parameters;
    if (d.tool_id) return tools.find((t) => t.id === d.tool_id)?.parameters;
    return undefined;
  }, [d.tool_key, d.tool_id, catalog, tools]);
  const provider = providers.find((p) => p.key === d.provider);
  const others = nodeIds.filter((n) => n !== node.id);

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-start gap-3">
        <IconTile icon={meta.icon} color={meta.color} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">{meta.label} node</div>
          <div className="text-xs text-muted">{meta.description}</div>
          <div className="mt-1 font-mono text-[11px] text-muted">id: {node.id}</div>
        </div>
        {!readOnly && (
          <Button variant="ghost" size="icon" onClick={onDelete} aria-label="Delete node" title="Delete node (Backspace)">
            <Trash2 className="size-4 text-muted" />
          </Button>
        )}
      </div>

      <fieldset disabled={readOnly} className="space-y-4">
        <Field label="Label">
          <Input value={d.label ?? ""} onChange={(e) => set("label", e.target.value)} />
        </Field>

        {type === "input" && <p className="text-xs text-muted">Define the fields users fill in when running this workflow via the <b>Inputs</b> button in the top bar. Reference them as <span className="font-mono">{"{{ input.<name> }}"}</span>.</p>}

        {type === "agent" && (
          <>
            <Field label="Agent">
              <div className="flex items-center gap-2">
                <AgentAvatar agent={agents.find((a) => a.id === d.agent_id) ?? { avatar: "bot", color: "slate" }} size="sm" />
                <Select value={d.agent_id ?? ""} onChange={(e) => set("agent_id", e.target.value)}>
                  <option value="" disabled>Select an agent…</option>
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}{a.org_id === null ? " (global)" : ""}</option>
                  ))}
                </Select>
              </div>
            </Field>
            <Field label="Prompt template">
              <Textarea rows={6} mono value={d.prompt ?? ""} onChange={(e) => set("prompt", e.target.value)} />
            </Field>
          </>
        )}

        {type === "team" && (
          <>
            <Field label="Team">
              <Select value={d.team_id ?? ""} onChange={(e) => set("team_id", e.target.value)}>
                <option value="" disabled>Select a team…</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}{t.org_id === null ? " (global)" : ""}</option>
                ))}
              </Select>
            </Field>
            <Field label="Task template">
              <Textarea rows={6} mono value={d.prompt ?? ""} onChange={(e) => set("prompt", e.target.value)} />
            </Field>
          </>
        )}

        {type === "tool" && (
          <>
            <Field label="Tool">
              <Select
                value={toolValue}
                onChange={(e) => {
                  const [kind, val] = e.target.value.split(":");
                  onChange({ ...d, tool_key: kind === "builtin" ? val : "", tool_id: kind === "tool" ? val : "" });
                }}
              >
                <option value="" disabled>Select a tool…</option>
                <optgroup label="Built-in">
                  {(catalog?.builtin_tools ?? []).map((b) => (
                    <option key={b.key} value={`builtin:${b.key}`}>{b.name}</option>
                  ))}
                </optgroup>
                {custom.length > 0 && (
                  <optgroup label="Custom tools">
                    {custom.map((t) => (
                      <option key={t.id} value={`tool:${t.id}`}>{t.display_name || t.name}</option>
                    ))}
                  </optgroup>
                )}
              </Select>
            </Field>
            <Field
              label={
                <span className="flex items-center justify-between">
                  Arguments (JSON template)
                  {toolParams && !readOnly && (
                    <button
                      type="button"
                      className="inline-flex cursor-pointer items-center gap-1 text-primary hover:underline"
                      onClick={() => {
                        const skeleton = Object.fromEntries(Object.keys(toolParams.properties ?? {}).map((k) => [k, "{{ last }}"]));
                        set("args", JSON.stringify(skeleton, null, 2));
                      }}
                    >
                      <WandSparkles className="size-3" /> Fill from schema
                    </button>
                  )}
                </span>
              }
              hint={toolParams ? `Parameters: ${Object.keys(toolParams.properties ?? {}).join(", ") || "none"}${toolParams.required?.length ? ` · required: ${toolParams.required.join(", ")}` : ""}` : undefined}
            >
              <Textarea rows={6} mono value={d.args ?? "{}"} onChange={(e) => set("args", e.target.value)} placeholder='{"query": "{{ input.topic }}"}' />
            </Field>
          </>
        )}

        {type === "llm" && (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              <Field label="Provider">
                <Select value={d.provider ?? "default"} onChange={(e) => onChange({ ...d, provider: e.target.value, model: "" })}>
                  <option value="default">Org default</option>
                  {providers.map((p) => (
                    <option key={p.key} value={p.key}>{p.label}{p.configured ? "" : " (not configured)"}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Model">
                <Input list={`models-${node.id}`} value={d.model ?? ""} onChange={(e) => set("model", e.target.value)} placeholder={d.provider === "default" || !d.provider ? "org default" : provider?.models[0] ?? "model id"} />
                <datalist id={`models-${node.id}`}>
                  {(provider?.models ?? []).map((m) => <option key={m} value={m} />)}
                </datalist>
              </Field>
            </div>
            <Field label="System prompt">
              <Textarea rows={3} value={d.system ?? ""} onChange={(e) => set("system", e.target.value)} />
            </Field>
            <Field label="Prompt template">
              <Textarea rows={6} mono value={d.prompt ?? ""} onChange={(e) => set("prompt", e.target.value)} />
            </Field>
          </>
        )}

        {type === "condition" && (
          <Field label="Expression" hint="Truthy → follows the green 'true' handle, otherwise the red 'false' handle.">
            <Textarea rows={3} mono value={d.expression ?? ""} onChange={(e) => set("expression", e.target.value)} placeholder="'URGENT' in (last | upper)" />
          </Field>
        )}

        {(type === "template" || type === "output") && (
          <Field label="Template">
            <Textarea rows={8} mono value={d.template ?? ""} onChange={(e) => set("template", e.target.value)} />
          </Field>
        )}

        {type !== "input" && type !== "output" && (
          <Checkbox checked={!!d.continue_on_error} onChange={(v) => set("continue_on_error", v)} label="Continue workflow if this node fails" />
        )}
      </fieldset>

      {type !== "input" && <TemplateHelp nodeIds={others} />}
    </div>
  );
}
