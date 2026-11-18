import { useEffect, useMemo, useState } from "react";
import { CalendarClock, Hand, RefreshCw, Timer, Webhook } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Automation, TargetType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAction, useAgents, useTeams, useWorkflows } from "@/hooks/useData";
import { Dialog } from "@/components/ui/overlay";
import { Button, Checkbox, Field, Input, Select, Switch, Textarea } from "@/components/ui/primitives";
import { CopyButton, JsonEditor } from "@/components/ui/inputs";

type Trigger = Automation["trigger_type"];

export const TRIGGERS: { key: Trigger; label: string; icon: LucideIcon; hint: string }[] = [
  { key: "manual", label: "Manual", icon: Hand, hint: "Only runs when you click Run now (or via the API)." },
  { key: "schedule", label: "Schedule", icon: CalendarClock, hint: "Runs on a cron schedule in your timezone." },
  { key: "interval", label: "Interval", icon: Timer, hint: "Runs every N minutes (minimum 5)." },
  { key: "webhook", label: "Webhook", icon: Webhook, hint: "Runs when an external system POSTs JSON to a secret URL." },
];

const PRESETS = [
  { label: "Hourly", cron: "0 * * * *" },
  { label: "Daily 09:00", cron: "0 9 * * *" },
  { label: "Weekdays 09:00", cron: "0 9 * * 1-5" },
  { label: "Mondays 09:00", cron: "0 9 * * 1" },
];

const TIMEZONES: string[] = (() => {
  try {
    return ((Intl as any).supportedValuesOf?.("timeZone") as string[]) ?? [];
  } catch {
    return [];
  }
})();

interface Form {
  name: string;
  description: string;
  target_type: TargetType;
  target_id: string;
  task: string;
  wfInputs: Record<string, any>;
  advanced: boolean;
  rawInput: Record<string, any>;
  trigger_type: Trigger;
  cron: string;
  timezone: string;
  interval_minutes: number;
  enabled: boolean;
}

const localTz = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

function fromAutomation(a: Automation | null): Form {
  if (!a)
    return {
      name: "",
      description: "",
      target_type: "agent",
      target_id: "",
      task: "",
      wfInputs: {},
      advanced: false,
      rawInput: {},
      trigger_type: "manual",
      cron: "0 9 * * 1-5",
      timezone: localTz(),
      interval_minutes: 60,
      enabled: true,
    };
  const input = a.input ?? {};
  const simpleTask = a.target_type !== "workflow" && Object.keys(input).every((k) => k === "task") && (input.task === undefined || typeof input.task === "string");
  return {
    name: a.name,
    description: a.description,
    target_type: a.target_type,
    target_id: a.target_id,
    task: typeof input.task === "string" ? input.task : "",
    wfInputs: a.target_type === "workflow" ? { ...input } : {},
    advanced: a.target_type !== "workflow" && !simpleTask,
    rawInput: input,
    trigger_type: a.trigger_type,
    cron: a.cron || "0 9 * * 1-5",
    timezone: a.timezone || "UTC",
    interval_minutes: a.interval_minutes || 60,
    enabled: a.enabled,
  };
}

export function AutomationDialog({ open, onClose, automation, onCreated }: { open: boolean; onClose: () => void; automation: Automation | null; onCreated: (a: Automation) => void }) {
  const { projectId, project } = useAuth();
  const agents = useAgents();
  const teams = useTeams();
  const workflows = useWorkflows();
  const [form, setForm] = useState<Form>(() => fromAutomation(automation));
  const [current, setCurrent] = useState<Automation | null>(automation);
  useEffect(() => {
    if (open) {
      setForm(fromAutomation(automation));
      setCurrent(automation);
    }
  }, [open, automation]);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));

  const targets = useMemo(() => {
    if (form.target_type === "agent") return (agents.data ?? []).map((a) => ({ id: a.id, name: a.name, global: a.org_id === null }));
    if (form.target_type === "team") return (teams.data ?? []).map((t) => ({ id: t.id, name: t.name, global: t.org_id === null }));
    return (workflows.data ?? []).map((w) => ({ id: w.id, name: w.name, global: w.org_id === null }));
  }, [form.target_type, agents.data, teams.data, workflows.data]);
  const workflow = form.target_type === "workflow" ? workflows.data?.find((w) => w.id === form.target_id) : undefined;

  const input = (): Record<string, any> => {
    if (form.advanced) return form.rawInput;
    if (form.target_type === "workflow") return form.wfInputs;
    return form.task ? { task: form.task } : {};
  };

  const body = () => ({
    name: form.name,
    description: form.description,
    target_type: form.target_type,
    target_id: form.target_id,
    input: input(),
    trigger_type: form.trigger_type,
    cron: form.trigger_type === "schedule" ? form.cron : "",
    timezone: form.timezone || "UTC",
    interval_minutes: form.trigger_type === "interval" ? Number(form.interval_minutes) : 0,
    enabled: form.enabled,
  });

  const save = useAction(() => (current ? http.patch<Automation>(`/automations/${current.id}`, body()) : http.post<Automation>("/automations", { project_id: projectId, ...body() })), {
    success: current ? "Automation updated" : "Automation created",
    invalidate: [["automations"]],
    onSuccess: (a) => {
      if (!current && a.trigger_type === "webhook") {
        setCurrent(a);
        onCreated(a);
      } else onClose();
    },
  });
  const rotate = useAction(() => http.post<Automation>(`/automations/${current!.id}/rotate-token`), {
    success: "Webhook token rotated - update your integrations",
    invalidate: [["automations"]],
    onSuccess: (a) => setCurrent(a),
  });

  const valid = form.name.trim() && form.target_id && (form.trigger_type !== "interval" || form.interval_minutes >= 5) && (form.trigger_type !== "schedule" || form.cron.trim().split(/\s+/).length >= 5);
  const webhookUrl = current?.trigger_type === "webhook" ? current.webhook_url : null;
  const curl = webhookUrl ? `curl -X POST '${webhookUrl}' \\\n  -H 'Content-Type: application/json' \\\n  -d '{"task": "Summarise the latest tickets"}'` : "";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title={current ? "Edit automation" : "New automation"}
      description={project ? `Runs in project “${project.name}” with its context and policies.` : undefined}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>{webhookUrl && !automation ? "Done" : "Cancel"}</Button>
          <Button loading={save.isPending} disabled={!valid} onClick={() => save.mutate()}>
            {current ? "Save changes" : "Create automation"}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name">
            <Input autoFocus value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Daily market brief" />
          </Field>
          <Field label="Description (optional)">
            <Input value={form.description} onChange={(e) => set("description", e.target.value)} />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-[160px_1fr]">
          <Field label="Runs a">
            <Select
              value={form.target_type}
              onChange={(e) => setForm((f) => ({ ...f, target_type: e.target.value as TargetType, target_id: "", wfInputs: {} }))}
            >
              <option value="agent">Agent</option>
              <option value="team">Team</option>
              <option value="workflow">Workflow</option>
            </Select>
          </Field>
          <Field label="Target">
            <Select
              value={form.target_id}
              onChange={(e) => {
                const wid = e.target.value;
                const wf = form.target_type === "workflow" ? workflows.data?.find((w) => w.id === wid) : undefined;
                setForm((f) => ({ ...f, target_id: wid, wfInputs: wf ? Object.fromEntries(wf.input_fields.map((x) => [x.name, x.default ?? ""])) : f.wfInputs }));
              }}
            >
              <option value="" disabled>Select…</option>
              {targets.map((t) => (
                <option key={t.id} value={t.id}>{t.name}{t.global ? " (global)" : ""}</option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted">Input</span>
            <Checkbox checked={form.advanced} onChange={(v) => setForm((f) => ({ ...f, advanced: v, rawInput: v ? input() : f.rawInput }))} label={<span className="text-xs">Advanced JSON</span>} />
          </div>
          {form.advanced ? (
            <JsonEditor value={form.rawInput} onChange={(v) => set("rawInput", v)} rows={6} />
          ) : form.target_type === "workflow" ? (
            workflow ? (
              workflow.input_fields.length ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {workflow.input_fields.map((f) => (
                    <Field key={f.name} label={f.label || f.name} className={f.type === "textarea" ? "sm:col-span-2" : undefined}>
                      {f.type === "textarea" ? (
                        <Textarea rows={3} value={form.wfInputs[f.name] ?? ""} onChange={(e) => set("wfInputs", { ...form.wfInputs, [f.name]: e.target.value })} />
                      ) : (
                        <Input type={f.type === "number" ? "number" : "text"} value={form.wfInputs[f.name] ?? ""} onChange={(e) => set("wfInputs", { ...form.wfInputs, [f.name]: f.type === "number" ? Number(e.target.value) : e.target.value })} />
                      )}
                    </Field>
                  ))}
                </div>
              ) : (
                <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">This workflow has no input fields.</p>
              )
            ) : (
              <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">Select a workflow to fill its inputs.</p>
            )
          ) : (
            <Textarea rows={3} value={form.task} onChange={(e) => set("task", e.target.value)} placeholder="e.g. Search the latest news about our competitors and summarise the top 5 stories." />
          )}
          {form.trigger_type === "webhook" && <p className="text-xs text-muted">Webhook JSON bodies are merged on top of this input.</p>}
        </div>

        <div className="space-y-3">
          <span className="text-xs font-medium text-muted">Trigger</span>
          <div className="grid grid-cols-2 gap-1 rounded-xl border border-border bg-surface-2/60 p-1 sm:grid-cols-4">
            {TRIGGERS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => set("trigger_type", t.key)}
                className={cn(
                  "flex cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium transition-colors",
                  form.trigger_type === t.key ? "bg-surface text-fg shadow-sm" : "text-muted hover:text-fg",
                )}
              >
                <t.icon className="size-4" /> {t.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted">{TRIGGERS.find((t) => t.key === form.trigger_type)?.hint}</p>

          {form.trigger_type === "schedule" && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-1.5">
                {PRESETS.map((p) => (
                  <button
                    key={p.cron}
                    type="button"
                    onClick={() => set("cron", p.cron)}
                    className={cn("cursor-pointer rounded-lg border px-2.5 py-1 text-xs font-medium", form.cron === p.cron ? "border-primary bg-primary-soft text-primary" : "border-border text-muted hover:bg-surface-2")}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Cron expression" hint="minute hour day-of-month month day-of-week">
                  <Input value={form.cron} onChange={(e) => set("cron", e.target.value)} className="font-mono" placeholder="0 9 * * 1-5" />
                </Field>
                <Field label="Timezone">
                  <Input list="af-timezones" value={form.timezone} onChange={(e) => set("timezone", e.target.value)} placeholder="UTC" />
                  <datalist id="af-timezones">
                    {TIMEZONES.map((z) => <option key={z} value={z} />)}
                  </datalist>
                </Field>
              </div>
            </div>
          )}

          {form.trigger_type === "interval" && (
            <Field label="Every (minutes)" error={form.interval_minutes < 5 ? "Minimum is 5 minutes" : undefined}>
              <Input type="number" min={5} value={form.interval_minutes} onChange={(e) => set("interval_minutes", Number(e.target.value))} className="sm:w-40" />
            </Field>
          )}

          {form.trigger_type === "webhook" && (
            webhookUrl ? (
              <div className="space-y-3 rounded-xl border border-border bg-surface-2/40 p-3">
                <Field label="Webhook URL" hint="Keep it secret - anyone with this URL can trigger the automation. Requests are rate limited.">
                  <div className="flex gap-2">
                    <Input readOnly value={webhookUrl} className="font-mono text-xs" onFocus={(e) => e.target.select()} />
                    <CopyButton text={webhookUrl} />
                  </div>
                </Field>
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs font-medium text-muted">
                    Example
                    <CopyButton text={curl} className="size-7" />
                  </div>
                  <pre className="overflow-x-auto rounded-lg border border-border bg-surface p-2.5 font-mono text-[11px] leading-relaxed">{curl}</pre>
                  <p className="mt-1 text-[11px] text-muted">Add <span className="font-mono">?wait=true</span> to wait up to 60s and receive the output in the response.</p>
                </div>
                <Button variant="outline" size="sm" icon={<RefreshCw className="size-3.5" />} loading={rotate.isPending} onClick={() => rotate.mutate()}>
                  Rotate token
                </Button>
              </div>
            ) : (
              <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">A secret webhook URL is generated when you save.</p>
            )
          )}
        </div>

        <Switch checked={form.enabled} onChange={(v) => set("enabled", v)} label="Enabled" description="Disabled automations never trigger (Run now still works)." />
      </div>
    </Dialog>
  );
}
