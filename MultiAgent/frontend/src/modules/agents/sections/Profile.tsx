import { Card, CardHeader, Field, Input, Textarea } from "@/shared/ui/primitives";
import { TagInput } from "@/shared/ui/inputs";
import { AgentAvatar, IconPicker } from "@/shared/ui/icons";
import { useAgentWorkspace } from "../context";

export default function Profile() {
  const { form, set, setForm, readOnly } = useAgentWorkspace();
  return (
    <fieldset disabled={readOnly} className="min-w-0">
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader title="Identity" description="How teammates, supervisors and routers recognise this agent." />
          <div className="space-y-4 p-4 sm:p-5">
            <Field label="Name">
              <Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Research Analyst" maxLength={120} />
            </Field>
            <Field label="Description" hint="Shown to teammates and used by supervisors and routers to pick the right agent.">
              <Textarea rows={4} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="Finds and verifies up-to-date information on the web." maxLength={4000} />
            </Field>
            <Field label="Tags" hint="Used for search and filtering in the agent library.">
              <TagInput value={form.tags} onChange={(v) => set("tags", v)} />
            </Field>
          </div>
        </Card>
        <Card>
          <CardHeader title="Icon" description="Pick a flat icon and accent color." />
          <div className="p-4">
            <div className="mb-4 flex items-center gap-3 rounded-xl border border-border bg-gradient-to-br from-primary-soft/60 to-transparent p-3">
              <AgentAvatar agent={{ avatar: form.avatar, color: form.color }} size="lg" />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold">{form.name || "Untitled agent"}</div>
                <div className="line-clamp-2 text-xs text-muted">{form.description || "No description"}</div>
              </div>
            </div>
            <IconPicker icon={form.avatar} color={form.color} onChange={(v) => setForm((f) => ({ ...f, avatar: v.icon, color: v.color }))} />
          </div>
        </Card>
      </div>
    </fieldset>
  );
}
