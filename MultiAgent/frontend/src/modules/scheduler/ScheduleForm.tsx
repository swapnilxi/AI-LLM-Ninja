/** Create / edit a schedule with a form. Used by /scheduler/new/form and /scheduler/:id/edit. */
import { useMemo, useState } from "react";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { TargetType } from "@/shared/lib/types";
import { cn, errMsg } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useAgents } from "@/modules/agents/api";
import { useTeams } from "@/modules/teams/api";
import { useWorkflows } from "@/modules/workflows/api";
import { Badge, Button, Card, CardHeader, Checkbox, Field, Input, Select, Switch, Textarea } from "@/shared/ui/primitives";
import { JsonEditor } from "@/shared/ui/inputs";
import type { Automation, ScheduleDraft, TriggerType } from "./types";
import { CRON_PRESETS, TIMEZONES, TRIGGERS, formatInTz, isoToZonedLocal, localTz, zonedLocalToIso } from "./lib";

interface Form {
  name: string;
  description: string;
  target_type: TargetType;
  target_id: string;
  task: string;
  wfInputs: Record<string, any>;
  advanced: boolean;
  rawInput: Record<string, any>;
  trigger_type: TriggerType;
  cron: string;
  timezone: string;
  interval_minutes: number;
  runAtLocal: string;
  enabled: boolean;
}

function tomorrowAt9(tz: string): string {
  const d = new Date(Date.now() + 86_400_000);
  return `${isoToZonedLocal(d.toISOString(), tz).slice(0, 10)}T09:00`;
}

function initialForm(a: Automation | null | undefined, draft: ScheduleDraft | null | undefined): Form {
  const tz = a?.timezone || draft?.timezone || localTz();
  const base: Form = {
    name: "",
    description: "",
    target_type: "agent",
    target_id: "",
    task: "",
    wfInputs: {},
    advanced: false,
    rawInput: {},
    trigger_type: "once",
    cron: "0 9 * * 1-5",
    timezone: tz,
    interval_minutes: 60,
    runAtLocal: tomorrowAt9(tz),
    enabled: true,
  };
  if (draft) {
    return {
      ...base,
      name: draft.name,
      task: draft.task,
      target_id: draft.target_id,
      trigger_type: draft.trigger_type === "manual" ? "once" : draft.trigger_type,
      cron: draft.cron || base.cron,
      interval_minutes: draft.interval_minutes || base.interval_minutes,
      runAtLocal: draft.run_at ? isoToZonedLocal(draft.run_at, tz) : base.runAtLocal,
    };
  }
  if (!a) return base;
  const input = a.input ?? {};
  const simpleTask = a.target_type !== "workflow" && Object.keys(input).every((k) => k === "task") && (input.task === undefined || typeof input.task === "string");
  return {
    ...base,
    name: a.name,
    description: a.description,
    target_type: a.target_type,
    target_id: a.target_id,
    task: typeof input.task === "string" ? input.task : "",
    wfInputs: a.target_type === "workflow" ? { ...input } : {},
    advanced: a.target_type !== "workflow" && !simpleTask,
    rawInput: input,
    trigger_type: a.trigger_type,
    cron: a.cron || base.cron,
    interval_minutes: a.interval_minutes || 60,
    runAtLocal: a.run_at ? isoToZonedLocal(a.run_at, tz) : base.runAtLocal,
    enabled: a.enabled,
  };
}

export function ScheduleForm({ schedule, draft, onSaved, onCancel, source = "form" }: { schedule?: Automation | null; draft?: ScheduleDraft | null; onSaved: (a: Automation) => void; onCancel?: () => void; source?: "form" | "chat" }) {
  const { projectId, project } = useAuth();
  const agents = useAgents();
  const teams = useTeams();
  const workflows = useWorkflows();
  const [form, setForm] = useState<Form>(() => initialForm(schedule, draft));
  const [aiText, setAiText] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [preview, setPreview] = useState<ScheduleDraft | null>(null);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));

  /** Plain English -> fills the form. Nothing is saved until Create. */
  const draftWithAi = async () => {
    setDrafting(true);
    try {
      const d = await http.post<ScheduleDraft>("/schedules/draft", { project_id: projectId, text: aiText, timezone: form.timezone, agent_id: form.target_type === "agent" && form.target_id ? form.target_id : undefined });
      setPreview(d);
      setForm((f) => ({
        ...f,
        name: f.name.trim() ? f.name : d.name,
        task: d.task,
        advanced: false,
        ...(d.trigger_type === "manual"
          ? {}
          : { trigger_type: d.trigger_type, cron: d.cron || f.cron, interval_minutes: d.interval_minutes || f.interval_minutes, timezone: d.timezone, runAtLocal: d.run_at ? isoToZonedLocal(d.run_at, d.timezone) : f.runAtLocal }),
        ...(f.target_id ? {} : { target_type: "agent" as TargetType, target_id: d.target_id }),
      }));
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setDrafting(false);
    }
  };

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
  const runAtIso = form.trigger_type === "once" ? zonedLocalToIso(form.runAtLocal, form.timezone || "UTC") : null;
  const runAtPast = !!runAtIso && new Date(runAtIso).getTime() <= Date.now() && !(schedule?.last_run_at && schedule.run_at === runAtIso);

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
    ...(runAtIso ? { run_at: runAtIso } : {}),
    enabled: form.enabled,
  });

  const save = useAction(() => (schedule ? http.patch<Automation>(`/schedules/${schedule.id}`, body()) : http.post<Automation>("/schedules", { project_id: projectId, source, ...body() })), {
    success: schedule ? "Schedule updated" : "Schedule created",
    invalidate: [["schedules"]],
    onSuccess: (a) => onSaved(a),
  });

  const valid =
    form.name.trim() &&
    form.target_id &&
    (form.trigger_type !== "interval" || form.interval_minutes >= 5) &&
    (form.trigger_type !== "schedule" || form.cron.trim().split(/\s+/).length >= 5) &&
    (form.trigger_type !== "once" || (runAtIso && !runAtPast));

  return (
    <div className="space-y-4">
      {!schedule && (
        <Card className="border-indigo-500/20 bg-gradient-to-br from-primary-soft/50 to-transparent p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Sparkles className="size-4 text-primary" /> Fill the form from plain English
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={aiText}
              onChange={(e) => setAiText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && aiText.trim().length >= 3 && !drafting && draftWithAi()}
              placeholder="Tomorrow at 3pm remind me to send the invoice"
              aria-label="Describe the schedule in plain English"
            />
            <Button variant="outline" loading={drafting} disabled={aiText.trim().length < 3} onClick={draftWithAi} icon={<Sparkles className="size-4" />}>
              Fill form
            </Button>
          </div>
          {preview && (
            <div className="mt-3 space-y-1 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{preview.summary}</span>
                <Badge tone={preview.engine === "ai" ? "primary" : "muted"}>{preview.engine === "ai" ? "AI" : "Rules"}</Badge>
              </div>
              {preview.notes.map((n) => (
                <div key={n} className={cn("text-xs", preview.trigger_type === "manual" ? "text-warning" : "text-muted")}>{n}</div>
              ))}
            </div>
          )}
        </Card>
      )}

      <Card>
        <CardHeader title="What runs" description={project ? `Runs in project “${project.name}” with its context and policies.` : undefined} />
        <div className="space-y-4 p-4 sm:p-5">
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
              <Select value={form.target_type} onChange={(e) => setForm((f) => ({ ...f, target_type: e.target.value as TargetType, target_id: "", wfInputs: {} }))}>
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
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted">{form.target_type === "workflow" ? "Workflow inputs" : "Task (sent on every run)"}</span>
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
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="When" description={TRIGGERS.find((t) => t.key === form.trigger_type)?.hint} />
        <div className="space-y-4 p-4 sm:p-5">
          <div className="grid grid-cols-2 gap-1 rounded-xl border border-border bg-surface-2/60 p-1 sm:grid-cols-5">
            {TRIGGERS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => set("trigger_type", t.key)}
                className={cn("flex cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium transition-colors", form.trigger_type === t.key ? "bg-surface text-fg shadow-sm" : "text-muted hover:text-fg")}
              >
                <t.icon className="size-4" /> {t.label}
              </button>
            ))}
          </div>

          {(form.trigger_type === "once" || form.trigger_type === "schedule") && (
            <div className="grid gap-3 sm:grid-cols-2">
              {form.trigger_type === "once" ? (
                <Field label="Date and time" error={runAtPast ? "Pick a time in the future" : undefined} hint={runAtIso && !runAtPast ? `Your local time: ${formatInTz(runAtIso, localTz())}` : undefined}>
                  <Input type="datetime-local" value={form.runAtLocal} onChange={(e) => set("runAtLocal", e.target.value)} />
                </Field>
              ) : (
                <Field label="Cron expression" hint="minute hour day-of-month month day-of-week">
                  <Input value={form.cron} onChange={(e) => set("cron", e.target.value)} className="font-mono" placeholder="0 9 * * 1-5" />
                </Field>
              )}
              <Field label="Timezone">
                <Input list="af-timezones" value={form.timezone} onChange={(e) => set("timezone", e.target.value)} placeholder="UTC" />
                <datalist id="af-timezones">
                  {TIMEZONES.map((z) => <option key={z} value={z} />)}
                </datalist>
              </Field>
            </div>
          )}
          {form.trigger_type === "schedule" && (
            <div className="flex flex-wrap gap-1.5">
              {CRON_PRESETS.map((p) => (
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
          )}
          {form.trigger_type === "interval" && (
            <Field label="Every (minutes)" error={form.interval_minutes < 5 ? "Minimum is 5 minutes" : undefined}>
              <Input type="number" min={5} value={form.interval_minutes} onChange={(e) => set("interval_minutes", Number(e.target.value))} className="sm:w-40" />
            </Field>
          )}
          {form.trigger_type === "webhook" && (
            <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">
              {schedule?.webhook_url ? "The webhook URL is on the schedule's overview page." : "A secret webhook URL is generated when you save; you will find it on the schedule's page."} Webhook JSON bodies are merged on top of the input above.
            </p>
          )}
          <Switch checked={form.enabled} onChange={(v) => set("enabled", v)} label="Enabled" description="Paused schedules never trigger (Run now still works)." />
        </div>
      </Card>

      <div className="flex justify-end gap-2">
        {onCancel && <Button variant="outline" onClick={onCancel}>Cancel</Button>}
        <Button loading={save.isPending} disabled={!valid} onClick={() => save.mutate()}>
          {schedule ? "Save changes" : "Create schedule"}
        </Button>
      </div>
    </div>
  );
}
