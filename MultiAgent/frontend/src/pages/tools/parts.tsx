import { useEffect, useState } from "react";
import { Bot, Brain, Calculator, Clock, FileText, FlaskConical, Globe, Library, Plus, Search, Trash2, Webhook, Wrench } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { JSONSchema, Tool } from "@/lib/types";
import { cn, errMsg } from "@/lib/utils";
import { Badge, Button, Card, CardHeader, Checkbox, Input, Select } from "@/components/ui/primitives";
import { JsonEditor } from "@/components/ui/inputs";

export const BUILTIN_ICONS: Record<string, { icon: LucideIcon; color: string }> = {
  web_search: { icon: Search, color: "sky" },
  browse_webpage: { icon: Globe, color: "sky" },
  http_request: { icon: Webhook, color: "teal" },
  calculator: { icon: Calculator, color: "emerald" },
  current_datetime: { icon: Clock, color: "amber" },
  knowledge_search: { icon: Library, color: "violet" },
  read_document: { icon: FileText, color: "violet" },
  memory: { icon: Brain, color: "rose" },
};

export function toolIcon(t: Pick<Tool, "kind" | "builtin_key">): { icon: LucideIcon; color: string } {
  if (t.kind === "builtin") return BUILTIN_ICONS[t.builtin_key ?? ""] ?? { icon: Wrench, color: "slate" };
  if (t.kind === "agent") return { icon: Bot, color: "indigo" };
  return { icon: Webhook, color: "teal" };
}

/* ------------------------------------------------------------------ parameters */
export const PARAM_TYPES = ["string", "number", "integer", "boolean", "array", "object"] as const;

export interface ParamRow {
  name: string;
  type: string;
  description: string;
  required: boolean;
}

export function schemaToRows(schema: JSONSchema | undefined): ParamRow[] {
  const props = schema?.properties ?? {};
  const req = new Set(schema?.required ?? []);
  return Object.entries(props).map(([name, p]) => ({ name, type: p.type ?? "string", description: p.description ?? "", required: req.has(name) }));
}

export function rowsToSchema(rows: ParamRow[], previous?: JSONSchema): JSONSchema {
  const prevProps = previous?.properties ?? {};
  const properties: JSONSchema["properties"] = {};
  for (const r of rows) {
    const name = r.name.trim();
    if (!name) continue;
    properties[name] = { ...(prevProps[name] ?? {}), type: r.type, ...(r.description ? { description: r.description } : { description: undefined }) };
    if (!r.description) delete properties[name].description;
  }
  return { type: "object", properties, required: rows.filter((r) => r.required && r.name.trim()).map((r) => r.name.trim()) };
}

/** Visual parameter builder with a raw JSON-schema toggle. */
export function ParamBuilder({ value, onChange, readOnly }: { value: JSONSchema; onChange: (s: JSONSchema) => void; readOnly?: boolean }) {
  const [json, setJson] = useState(false);
  const [rows, setRows] = useState<ParamRow[]>(() => schemaToRows(value));
  useEffect(() => {
    setRows(schemaToRows(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(value)]);
  const commit = (next: ParamRow[]) => {
    setRows(next);
    onChange(rowsToSchema(next, value));
  };
  const update = (i: number, patch: Partial<ParamRow>) => commit(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <Card>
      <CardHeader
        title="Parameters"
        description="The JSON schema the model fills in when calling this tool."
        actions={
          <Button size="sm" variant="ghost" onClick={() => setJson((j) => !j)}>
            {json ? "Visual" : "JSON"}
          </Button>
        }
      />
      <div className="p-3 sm:p-4">
        {json ? (
          <JsonEditor rows={12} value={value} onChange={(v) => v && typeof v === "object" && onChange({ type: "object", properties: v.properties ?? {}, required: v.required ?? [] })} />
        ) : (
          <div className="space-y-2">
            {rows.length === 0 && <p className="py-2 text-sm text-muted">No parameters - the tool is called without arguments.</p>}
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-[1fr_auto] gap-2 rounded-lg border border-border p-2 sm:grid-cols-[minmax(0,160px)_130px_minmax(0,1fr)_auto_auto] sm:items-center sm:border-0 sm:p-0">
                <Input disabled={readOnly} value={r.name} onChange={(e) => update(i, { name: e.target.value.replace(/[^a-zA-Z0-9_]/g, "") })} placeholder="name" className="font-mono text-xs" />
                <Select disabled={readOnly} value={r.type} onChange={(e) => update(i, { type: e.target.value })} className="w-[120px] sm:w-auto">
                  {PARAM_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </Select>
                <Input disabled={readOnly} value={r.description} onChange={(e) => update(i, { description: e.target.value })} placeholder="Description shown to the model" className="col-span-2 sm:col-span-1" />
                <Checkbox checked={r.required} onChange={(v) => !readOnly && update(i, { required: v })} label="Required" className="whitespace-nowrap" />
                {!readOnly && (
                  <Button variant="ghost" size="icon" aria-label="Remove parameter" onClick={() => commit(rows.filter((_, j) => j !== i))} className="justify-self-end">
                    <Trash2 className="size-4 text-muted" />
                  </Button>
                )}
              </div>
            ))}
            {!readOnly && (
              <Button variant="outline" size="sm" icon={<Plus className="size-3.5" />} onClick={() => commit([...rows, { name: "", type: "string", description: "", required: false }])}>
                Add parameter
              </Button>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

/** Read-only parameter table (built-in tools). */
export function ParamTable({ schema }: { schema: JSONSchema }) {
  const rows = schemaToRows(schema);
  if (!rows.length) return <p className="p-4 text-sm text-muted">No parameters.</p>;
  return (
    <ul className="divide-y divide-border">
      {rows.map((r) => {
        const spec = schema.properties[r.name] ?? {};
        return (
          <li key={r.name} className="flex flex-col gap-1 px-4 py-2.5 sm:flex-row sm:items-start sm:gap-4">
            <div className="flex shrink-0 items-center gap-2 sm:w-48">
              <span className="font-mono text-xs font-medium">{r.name}</span>
              {r.required && <Badge tone="warning">required</Badge>}
            </div>
            <div className="min-w-0 flex-1 text-sm">
              <Badge tone="muted" className="mr-2">{r.type}</Badge>
              <span className="text-muted">{r.description}</span>
              {spec.enum && <div className="mt-1 text-xs text-muted">One of: {spec.enum.join(", ")}</div>}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function sampleArgs(schema: JSONSchema): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [k, p] of Object.entries(schema?.properties ?? {})) {
    if (!(schema.required ?? []).includes(k)) continue;
    out[k] = p.default ?? (p.enum ? p.enum[0] : { string: "", number: 0, integer: 0, boolean: false, array: [], object: {} }[p.type ?? "string"] ?? "");
  }
  return out;
}

/** Execute a saved tool in the active project. */
export function TestPanel({ tool }: { tool: Tool }) {
  const { projectId, project, can } = useAuth();
  const [args, setArgs] = useState<Record<string, any>>(() => sampleArgs(tool.parameters));
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; output: string } | null>(null);
  useEffect(() => setArgs(sampleArgs(tool.parameters)), [tool.id, tool.parameters]);

  const run = async () => {
    setBusy(true);
    setResult(null);
    try {
      setResult(await http.post<{ ok: boolean; output: string }>(`/tools/${tool.id}/test`, { project_id: projectId, arguments: args }));
    } catch (e) {
      setResult({ ok: false, output: errMsg(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader
        title="Test"
        description={project ? `Runs in project “${project.name}” with its policies and secrets.` : "Select a project to test."}
        actions={
          <Button size="sm" icon={<FlaskConical className="size-3.5" />} loading={busy} disabled={!projectId || !can("member")} onClick={run}>
            Run test
          </Button>
        }
      />
      <div className="space-y-3 p-3 sm:p-4">
        <JsonEditor rows={6} value={args} onChange={(v) => setArgs(v && typeof v === "object" ? v : {})} />
        {result && (
          <div>
            <div className="mb-1.5">{result.ok ? <Badge tone="success">Success</Badge> : <Badge tone="danger">Error</Badge>}</div>
            <pre
              className={cn(
                "max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border bg-surface-2 p-3 font-mono text-[11px] leading-relaxed",
                result.ok ? "border-border" : "border-red-500/30 text-danger",
              )}
            >
              {result.output}
            </pre>
          </div>
        )}
      </div>
    </Card>
  );
}
