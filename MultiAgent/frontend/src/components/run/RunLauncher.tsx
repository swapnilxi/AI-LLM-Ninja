import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Play, Square } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { InputField, TargetType } from "@/lib/types";
import { errMsg } from "@/lib/utils";
import { useStartRun } from "@/hooks/useData";
import { useRunStream } from "@/hooks/useRunStream";
import { Dialog } from "@/components/ui/overlay";
import { Button, Field, Input, Textarea } from "@/components/ui/primitives";
import { Markdown } from "@/components/ui/Markdown";
import { RunStatusBadge, RunTimeline } from "./RunTimeline";

/**
 * Run any agent / team / workflow in the active project and watch it live.
 * Agents & teams take a single task; workflows render their input fields.
 */
export function RunLauncher({ open, onClose, targetType, targetId, targetName, fields }: {
  open: boolean;
  onClose: () => void;
  targetType: TargetType;
  targetId: string;
  targetName: string;
  fields?: InputField[];
}) {
  const { project } = useAuth();
  const start = useStartRun();
  const [runId, setRunId] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, any>>({});
  const stream = useRunStream(runId);

  const inputFields: InputField[] = targetType === "workflow" ? (fields?.length ? fields : []) : [{ name: "task", label: "Task", type: "textarea" }];

  useEffect(() => {
    if (open) {
      setRunId(null);
      setValues(Object.fromEntries(inputFields.map((f) => [f.name, f.default ?? ""])));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, targetId]);

  const run = async () => {
    const input = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, inputFields.find((f) => f.name === k)?.type === "number" ? Number(v) : v]));
    const r = await start.mutateAsync({ target_type: targetType, target_id: targetId, input });
    setRunId(r.id);
  };

  const cancel = async () => {
    if (!runId) return;
    try {
      await http.post(`/runs/${runId}/cancel`);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  const running = !!runId && !stream.done;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title={<span>Run <span className="text-brand">{targetName}</span></span>}
      description={project ? `Runs in project “${project.name}” with its context, documents, memory and policies.` : undefined}
      footer={
        <>
          {runId && (
            <Link to={`/runs/${runId}`} className="mr-auto inline-flex items-center gap-1 text-sm text-muted hover:text-fg">
              Open run <ExternalLink className="size-3.5" />
            </Link>
          )}
          {running ? (
            <Button variant="outline" icon={<Square className="size-3.5" />} onClick={cancel}>
              Stop
            </Button>
          ) : (
            <Button icon={<Play className="size-4" />} loading={start.isPending} onClick={run} disabled={!project}>
              {runId ? "Run again" : "Run"}
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {inputFields.length === 0 && !runId && <p className="text-sm text-muted">This workflow has no input fields. Click Run to start it.</p>}
        {(!runId || stream.done) &&
          inputFields.map((f) => (
            <Field key={f.name} label={f.label || f.name}>
              {f.type === "textarea" ? (
                <Textarea autoFocus rows={4} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} placeholder={targetType === "workflow" ? "" : "What should it do?"} />
              ) : (
                <Input type={f.type === "number" ? "number" : "text"} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
              )}
            </Field>
          ))}
        {runId && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted">Status</span> <RunStatusBadge status={stream.status ?? "queued"} />
            </div>
            {stream.done && (stream.output || stream.error) && (
              <div className={stream.error ? "rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm text-danger" : "rounded-xl border border-border bg-gradient-to-br from-primary-soft/50 to-transparent p-4"}>
                {stream.error ? stream.error : <Markdown>{stream.output}</Markdown>}
              </div>
            )}
            <details open={!stream.done} className="rounded-xl border border-border p-3">
              <summary className="cursor-pointer text-xs font-medium text-muted">Live trace ({stream.events.length} events)</summary>
              <RunTimeline events={stream.events} live={stream.live} className="mt-3" />
            </details>
          </div>
        )}
      </div>
    </Dialog>
  );
}
