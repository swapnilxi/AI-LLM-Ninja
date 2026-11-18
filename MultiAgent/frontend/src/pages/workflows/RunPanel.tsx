import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Play, Square } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { InputField } from "@/lib/types";
import { errMsg } from "@/lib/utils";
import type { RunStreamState } from "@/hooks/useRunStream";
import { Button, Field, Input, Textarea } from "@/components/ui/primitives";
import { CopyButton } from "@/components/ui/inputs";
import { Markdown } from "@/components/ui/Markdown";
import { RunStatusBadge, RunTimeline } from "@/components/run/RunTimeline";

/** Run form + live result/trace for the workflow builder. Live node status is shown on the canvas. */
export function RunPanel({
  fields,
  runId,
  stream,
  starting,
  onRun,
}: {
  fields: InputField[];
  runId: string | null;
  stream: RunStreamState;
  starting: boolean;
  onRun: (input: Record<string, any>) => void;
}) {
  const { project } = useAuth();
  const [values, setValues] = useState<Record<string, any>>({});
  useEffect(() => {
    setValues((v) => Object.fromEntries(fields.map((f) => [f.name, v[f.name] ?? f.default ?? ""])));
  }, [fields]);
  const running = !!runId && !stream.done;

  const submit = () => {
    const input = Object.fromEntries(fields.map((f) => [f.name, f.type === "number" ? Number(values[f.name]) : values[f.name]]));
    onRun(input);
  };
  const cancel = async () => {
    if (!runId) return;
    try {
      await http.post(`/runs/${runId}/cancel`);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return (
    <div className="space-y-4 p-4">
      <p className="text-xs text-muted">
        Runs in project <span className="font-medium text-fg">{project?.name ?? "—"}</span>. Unsaved changes are saved first.
      </p>
      {fields.length === 0 ? (
        <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">No input fields defined. Add some with the Inputs button.</p>
      ) : (
        fields.map((f) => (
          <Field key={f.name} label={f.label || f.name}>
            {f.type === "textarea" ? (
              <Textarea rows={3} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
            ) : (
              <Input type={f.type === "number" ? "number" : "text"} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
            )}
          </Field>
        ))
      )}
      <div className="flex items-center gap-2">
        {running ? (
          <Button variant="outline" icon={<Square className="size-3.5" />} onClick={cancel}>
            Stop
          </Button>
        ) : (
          <Button icon={<Play className="size-4" />} loading={starting} onClick={submit} disabled={!project}>
            {runId ? "Run again" : "Run workflow"}
          </Button>
        )}
        {runId && (
          <>
            <RunStatusBadge status={stream.status ?? "queued"} />
            <Link to={`/runs/${runId}`} className="ml-auto inline-flex items-center gap-1 text-xs text-muted hover:text-fg">
              Open run <ExternalLink className="size-3" />
            </Link>
          </>
        )}
      </div>
      {runId && stream.done && (stream.output || stream.error) && (
        <div className={stream.error ? "rounded-xl border border-red-500/30 bg-red-500/5 p-3 text-sm text-danger" : "relative rounded-xl border border-border bg-gradient-to-br from-primary-soft/50 to-transparent p-3"}>
          {stream.error ? (
            stream.error
          ) : (
            <>
              <CopyButton text={stream.output} className="absolute right-2 top-2 size-7" />
              <Markdown>{stream.output}</Markdown>
            </>
          )}
        </div>
      )}
      {runId && (
        <div>
          <div className="mb-2 text-xs font-medium text-muted">Trace · {stream.events.length} events</div>
          <RunTimeline events={stream.events} live={stream.live} />
        </div>
      )}
    </div>
  );
}
