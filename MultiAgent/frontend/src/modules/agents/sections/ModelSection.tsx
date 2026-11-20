import { Card, CardHeader } from "@/shared/ui/primitives";
import { ModelFields } from "../ModelFields";
import { useAgentWorkspace } from "../context";

export default function ModelSection() {
  const { form, setForm, readOnly } = useAgentWorkspace();
  return (
    <fieldset disabled={readOnly} className="min-w-0">
      <Card>
        <CardHeader title="Model" description="Which model runs this agent and how much room it gets to think and act." />
        <div className="p-4 sm:p-5">
          <ModelFields value={form} onChange={(patch) => setForm((f) => ({ ...f, ...patch }))} />
        </div>
      </Card>
    </fieldset>
  );
}
