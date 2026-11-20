import { useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CircleCheck, Download, FileJson, Upload } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { cn, errMsg } from "@/shared/lib/utils";
import { useAgents } from "@/modules/agents/api";
import { useSkills } from "@/modules/skills/api";
import { useTeams } from "@/modules/teams/api";
import { useTools } from "@/modules/tools/api";
import { useWorkflows } from "@/modules/workflows/api";
import { Badge, Button, Card, CardHeader, Checkbox, Tabs } from "@/shared/ui/primitives";
import { MultiSelect } from "@/shared/ui/inputs";

type Kind = "agent_ids" | "team_ids" | "workflow_ids" | "skill_ids" | "tool_ids";

interface ImportResult {
  created: Record<string, number>;
  items: { type: string; id: string; name: string }[];
  warnings: string[];
}

/** Export library items (with dependencies) to a JSON bundle; import bundles into this org. */
export function TransferTab() {
  const { can, org } = useAuth();
  const qc = useQueryClient();
  const agents = useAgents();
  const teams = useTeams();
  const workflows = useWorkflows();
  const skills = useSkills();
  const tools = useTools();
  const [kind, setKind] = useState<Kind>("agent_ids");
  const [sel, setSel] = useState<Record<Kind, string[]>>({ agent_ids: [], team_ids: [], workflow_ids: [], skill_ids: [], tool_ids: [] });
  const [deps, setDeps] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [bundle, setBundle] = useState<any>(null);
  const [fileName, setFileName] = useState("");
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const options = useMemo(() => {
    const tag = (orgId: string | null) => (orgId === null ? "global" : undefined);
    return {
      agent_ids: (agents.data ?? []).map((a) => ({ value: a.id, label: a.name, description: a.description, badge: tag(a.org_id) })),
      team_ids: (teams.data ?? []).map((t) => ({ value: t.id, label: t.name, description: t.description, badge: tag(t.org_id) })),
      workflow_ids: (workflows.data ?? []).map((w) => ({ value: w.id, label: w.name, description: w.description, badge: tag(w.org_id) })),
      skill_ids: (skills.data ?? []).map((s) => ({ value: s.id, label: s.name, description: s.description, badge: s.command ? `/${s.command}` : tag(s.org_id) })),
      tool_ids: (tools.data ?? []).filter((t) => t.kind !== "builtin").map((t) => ({ value: t.id, label: t.display_name || t.name, description: t.description, badge: t.kind })),
    };
  }, [agents.data, teams.data, workflows.data, skills.data, tools.data]);
  const total = Object.values(sel).reduce((n, v) => n + v.length, 0);

  const doExport = async () => {
    setExporting(true);
    try {
      const data = await http.post("/library/export", { ...sel, include_dependencies: deps });
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `agentforge-${(org?.slug ?? "library").replace(/[^a-z0-9-]/gi, "")}-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      const counts = Object.entries(data.items as Record<string, unknown[]>).filter(([, v]) => v.length).map(([k, v]) => `${v.length} ${k}`).join(", ");
      toast.success(`Exported ${counts}`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setExporting(false);
    }
  };

  const readFile = async (f: File) => {
    setResult(null);
    if (f.size > 1.5 * 1024 * 1024) return toast.error("Bundle is too large (max 1.5 MB)");
    try {
      const parsed = JSON.parse(await f.text());
      if (parsed?.format !== "agentforge.bundle") throw new Error("This file is not an AgentForge bundle");
      setBundle(parsed);
      setFileName(f.name);
    } catch (e) {
      setBundle(null);
      toast.error(errMsg(e));
    }
  };

  const doImport = async () => {
    setImporting(true);
    try {
      const res = await http.post<ImportResult>("/library/import", { bundle });
      setResult(res);
      setBundle(null);
      ["agents", "teams", "workflows", "skills", "tools"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      toast.success(`Imported ${res.items.length} item(s)`);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setImporting(false);
    }
  };

  const preview = bundle ? Object.entries(bundle.items as Record<string, any[]>).filter(([, v]) => v?.length) : [];

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader title="Export" description="Download agents, teams, workflows, skills and custom tools as a portable JSON bundle." />
        <div className="space-y-4 p-4">
          <Tabs
            tabs={[
              { key: "agent_ids" as Kind, label: "Agents", count: sel.agent_ids.length || undefined },
              { key: "team_ids" as Kind, label: "Teams", count: sel.team_ids.length || undefined },
              { key: "workflow_ids" as Kind, label: "Workflows", count: sel.workflow_ids.length || undefined },
              { key: "skill_ids" as Kind, label: "Skills", count: sel.skill_ids.length || undefined },
              { key: "tool_ids" as Kind, label: "Tools", count: sel.tool_ids.length || undefined },
            ]}
            value={kind}
            onChange={setKind}
          />
          <MultiSelect options={options[kind]} value={sel[kind]} onChange={(v) => setSel({ ...sel, [kind]: v })} emptyText="Nothing here yet" maxHeight="max-h-72" />
          <Checkbox checked={deps} onChange={setDeps} label="Include dependencies (team members, skills, tools used by workflows…)" />
          <p className="text-xs text-muted">Built-in tools are referenced, not copied. App connections and secrets are never exported.</p>
          <div className="flex justify-end">
            <Button icon={<Download className="size-4" />} disabled={!total || !can("member")} loading={exporting} onClick={doExport}>
              Export {total ? `${total} selected` : ""}
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Import" description="Add items from a bundle into this organization. Names that already exist get an “(imported)” suffix." />
        <div className="space-y-4 p-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              const f = e.dataTransfer.files[0];
              if (f) readFile(f);
            }}
            onClick={() => fileRef.current?.click()}
            className={cn("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors", drag ? "border-primary bg-primary-soft/50" : "border-border hover:bg-surface-2")}
          >
            <FileJson className="mb-2 size-6 text-muted" />
            <div className="text-sm font-medium">{fileName || "Drop a bundle (.json) or click to choose"}</div>
            <div className="mt-1 text-xs text-muted">Exported from any AgentForge organization or installation</div>
            <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={(e) => e.target.files?.[0] && readFile(e.target.files[0])} />
          </div>
          {bundle && (
            <div className="rounded-xl border border-border p-3">
              <div className="mb-2 text-xs text-muted">From “{bundle.source ?? "unknown"}” · {bundle.exported_at ? new Date(bundle.exported_at).toLocaleString() : ""}</div>
              <div className="flex flex-wrap gap-1.5">
                {preview.map(([k, v]) => (
                  <Badge key={k} tone="primary">{v.length} {k}</Badge>
                ))}
              </div>
            </div>
          )}
          <div className="flex justify-end">
            <Button icon={<Upload className="size-4" />} disabled={!bundle || !can("member")} loading={importing} onClick={doImport}>
              Import bundle
            </Button>
          </div>
          {result && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-sm">
              <div className="mb-2 flex items-center gap-2 font-medium text-success">
                <CircleCheck className="size-4" /> Imported {result.items.length} item(s)
              </div>
              <ul className="space-y-0.5 text-xs text-muted">
                {result.items.map((i) => (
                  <li key={i.id}>
                    <span className="capitalize">{i.type}</span> · <span className="text-fg">{i.name}</span>
                  </li>
                ))}
              </ul>
              {result.warnings.length > 0 && <div className="mt-2 text-xs text-warning">{result.warnings.join(" · ")}</div>}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
