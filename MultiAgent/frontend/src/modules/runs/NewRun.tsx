import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Play, PlayCircle } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { TargetType } from "@/shared/lib/types";
import type { InputField } from "@/modules/workflows/types";
import { useStartRun } from "@/modules/runs/api";
import { useReturnTo } from "@/shared/hooks/useReturnTo";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Button, Card, EmptyState, Field, Input, PageLoader, Textarea } from "@/shared/ui/primitives";
import { TARGET_META, TargetIcon } from "./common";

const TYPES: TargetType[] = ["agent", "team", "workflow"];
const ENDPOINT: Record<TargetType, string> = { agent: "/agents", team: "/teams", workflow: "/workflows" };

/**
 * /runs/new?target_type=agent|team|workflow&target_id=<id>[&return_to=<path>]
 * Agents and teams take one task; workflows render their input fields. Starting navigates to /runs/<id> (live timeline).
 */
export default function NewRun() {
  const [params] = useSearchParams();
  const type = params.get("target_type") as TargetType | null;
  const targetId = params.get("target_id");
  const valid = !!type && TYPES.includes(type) && !!targetId;
  const back = useReturnTo(valid ? `${TARGET_META[type!].path}/${targetId}` : "/runs");
  const target = useQuery({
    queryKey: [`${type}s`, targetId],
    queryFn: () => http.get<{ id: string; name: string; input_fields?: InputField[] }>(`${ENDPOINT[type!]}/${targetId}`),
    enabled: valid,
  });
  if (valid && target.isLoading) return <PageLoader />;
  if (!valid || !target.data)
    return (
      <Page className="max-w-2xl">
        <PageHeader back={back} title="Start a run" />
        <EmptyState
          icon={<PlayCircle className="size-5" />}
          title={valid ? "Nothing to run" : "Missing target"}
          description={
            valid ? "This agent, team or workflow does not exist or belongs to another organization." : "Open this page from an agent, team or workflow (target_type and target_id are required)."
          }
        />
      </Page>
    );
  return <RunForm key={target.data.id} type={type!} targetId={target.data.id} name={target.data.name} fields={target.data.input_fields} back={back} />;
}

function RunForm({ type, targetId, name, fields, back }: { type: TargetType; targetId: string; name: string; fields?: InputField[]; back: string }) {
  const { project } = useAuth();
  const nav = useNavigate();
  const start = useStartRun();
  const inputFields: InputField[] = type === "workflow" ? (fields ?? []) : [{ name: "task", label: "Task", type: "textarea" }];
  const [values, setValues] = useState<Record<string, any>>(() => Object.fromEntries(inputFields.map((f) => [f.name, f.default ?? ""])));

  const run = async () => {
    const input = Object.fromEntries(Object.entries(values).map(([k, v]) => [k, inputFields.find((f) => f.name === k)?.type === "number" ? Number(v) : v]));
    try {
      const r = await start.mutateAsync({ target_type: type, target_id: targetId, input });
      nav(`/runs/${r.id}`);
    } catch {
      /* toast shown by the hook */
    }
  };

  return (
    <Page className="max-w-2xl">
      <PageHeader
        back={back}
        icon={<TargetIcon type={type} size="md" />}
        title={
          <>
            Run <span className="text-brand">{name}</span>
          </>
        }
        description={project ? `${TARGET_META[type].label} · runs in project “${project.name}” with its context, documents, memory and policies.` : "Select a project in the header first."}
      />
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (project) run();
          }}
        >
          <div className="space-y-4 p-4 sm:p-5">
            {inputFields.length === 0 && <p className="text-sm text-muted">This workflow has no input fields. Click Run to start it.</p>}
            {inputFields.map((f, i) => (
              <Field key={f.name} label={f.label || f.name}>
                {f.type === "textarea" ? (
                  <Textarea
                    autoFocus={i === 0}
                    rows={5}
                    value={values[f.name] ?? ""}
                    onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                    placeholder={type === "workflow" ? "" : "What should it do?"}
                  />
                ) : (
                  <Input autoFocus={i === 0} type={f.type === "number" ? "number" : "text"} value={values[f.name] ?? ""} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
                )}
              </Field>
            ))}
          </div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
            <Button type="button" variant="outline" onClick={() => nav(back)}>
              Cancel
            </Button>
            <Button type="submit" icon={<Play className="size-4" />} loading={start.isPending} disabled={!project}>
              Run
            </Button>
          </div>
        </form>
      </Card>
    </Page>
  );
}
