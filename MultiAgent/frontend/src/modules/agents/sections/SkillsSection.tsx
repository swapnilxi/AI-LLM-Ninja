import { useMemo } from "react";
import { ArrowUpRight, Plus, Sparkles, X } from "lucide-react";
import { useSkills } from "@/modules/skills/api";
import { withReturn } from "@/shared/hooks/useReturnTo";
import { Badge, Button, Card, CardHeader, EmptyState } from "@/shared/ui/primitives";
import { MultiSelect } from "@/shared/ui/inputs";
import { ScopeBadge } from "@/shared/components/library";
import { useAgentWorkspace } from "../context";

export default function SkillsSection() {
  const { id, form, set, readOnly, dirty, leave, saveThen } = useAgentWorkspace();
  const skills = useSkills();

  const options = useMemo(
    () => (skills.data ?? []).map((s) => ({ value: s.id, label: s.name, description: s.description, badge: s.org_id === null ? "global" : undefined })),
    [skills.data],
  );
  const attached = (skills.data ?? []).filter((s) => form.skill_ids.includes(s.id));
  const newSkillUrl = withReturn(`/skills/new?attach_agent=${encodeURIComponent(id)}`, `/agents/${id}/skills`);

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_380px]">
      <Card className="min-w-0">
        <CardHeader
          title="Attached skills"
          description="Instruction packs added to this agent's prompt. Their bundled tools are added automatically."
          actions={
            !readOnly && (
              <Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => saveThen(newSkillUrl)} title={dirty ? "Saves your changes first" : undefined}>
                {dirty ? "Save & new skill" : "New skill"}
              </Button>
            )
          }
        />
        {attached.length === 0 ? (
          <div className="p-4">
            <EmptyState
              icon={<Sparkles className="size-5" />}
              title="No skills attached"
              description="Pick existing skills on the right, or create a new one for this agent."
            />
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {attached.map((s) => (
              <li key={s.id} className="flex items-start gap-3 px-4 py-3 sm:px-5">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/15 to-indigo-500/10 text-primary ring-1 ring-inset ring-indigo-500/15">
                  <Sparkles className="size-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <button type="button" onClick={() => leave(`/skills/${s.id}`)} className="cursor-pointer truncate text-sm font-semibold hover:text-primary hover:underline">
                      {s.name}
                    </button>
                    <ScopeBadge orgId={s.org_id} />
                  </div>
                  {s.description && <p className="mt-0.5 line-clamp-2 text-xs text-muted">{s.description}</p>}
                </div>
                {!readOnly && (
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-8"
                    aria-label={`Detach ${s.name}`}
                    title="Detach"
                    onClick={() => set("skill_ids", form.skill_ids.filter((x) => x !== s.id))}
                  >
                    <X className="size-4" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Library"
          description="Search and attach skills from your organization and the global library."
          actions={
            <button type="button" onClick={() => leave("/skills")} className="inline-flex cursor-pointer items-center gap-0.5 text-xs font-medium text-primary hover:underline">
              Browse <ArrowUpRight className="size-3" />
            </button>
          }
        />
        <fieldset disabled={readOnly} className="min-w-0 p-3">
          <MultiSelect options={options} value={form.skill_ids} onChange={(v) => set("skill_ids", v)} emptyText={skills.isLoading ? "Loading…" : "No skills yet"} maxHeight="max-h-96" />
          <div className="mt-2 px-1 text-xs text-muted">
            <Badge tone="muted">{form.skill_ids.length}</Badge> attached
          </div>
        </fieldset>
      </Card>
    </div>
  );
}
