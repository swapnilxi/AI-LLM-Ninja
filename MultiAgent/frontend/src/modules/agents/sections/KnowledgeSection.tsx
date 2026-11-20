import { ArrowRight, Brain, FileUp, GraduationCap, Library, MessageSquareText } from "lucide-react";
import { Card, Switch } from "@/shared/ui/primitives";
import { useAgentWorkspace } from "../context";
import { capabilityOn, trainingUrl } from "../parts";

const LINKS = [
  { sub: "ingest", label: "Ingest documents", description: "Upload files, URLs or text that only this agent can search. Pin key documents into every prompt.", icon: FileUp },
  { sub: "teach", label: "Teach", description: "Give corrections and lessons in plain language; the agent remembers them in every run.", icon: MessageSquareText },
  { sub: "memory", label: "Memory", description: "Review, edit or remove what the agent has learned and saved over time.", icon: Brain },
] as const;

export default function KnowledgeSection() {
  const { id, form, setSetting, readOnly, leave } = useAgentWorkspace();
  return (
    <div className="space-y-5">
      <Card className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary-soft/80 via-transparent to-transparent" />
        <div className="relative flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:p-6">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/10 text-primary ring-1 ring-inset ring-indigo-500/20">
            <GraduationCap className="size-6" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold">Knowledge and training live in the Training window</h2>
            <p className="mt-1 text-sm text-muted">Documents, taught lessons and memory for {form.name || "this agent"} are managed in one place, with their own pages.</p>
          </div>
          <button
            type="button"
            onClick={() => leave(trainingUrl(id))}
            className="inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:brightness-110 dark:text-[#0b0d12]"
          >
            Open training <ArrowRight className="size-4" />
          </button>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        {LINKS.map((l) => (
          <button
            key={l.sub}
            type="button"
            onClick={() => leave(trainingUrl(id, l.sub))}
            className="group flex cursor-pointer flex-col rounded-xl border border-border bg-surface p-4 text-left transition-all hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/5"
          >
            <div className="flex items-center justify-between">
              <l.icon className="size-5 text-primary" />
              <ArrowRight className="size-4 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
            </div>
            <div className="mt-3 text-sm font-semibold">{l.label}</div>
            <p className="mt-1 text-xs text-muted">{l.description}</p>
          </button>
        ))}
      </div>

      <Card className="px-4 py-2 sm:px-5">
        <Switch
          checked={capabilityOn(form.settings, "knowledge_enabled")}
          onChange={(v) => setSetting("knowledge_enabled", v)}
          disabled={readOnly}
          label={<span className="inline-flex items-center gap-2"><Library className="size-4 text-primary" /> Document knowledge</span>}
          description="Lets the agent search agent, project and organization documents during runs."
        />
      </Card>
    </div>
  );
}
