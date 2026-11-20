/** `/agents/new` - create an agent from a starting template, then continue in its workspace. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Plus } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { cn } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { useReturnTo } from "@/shared/hooks/useReturnTo";
import { useProviders } from "@/modules/settings/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Button, Card, CardHeader, EmptyState, Field, Input, Select, Textarea } from "@/shared/ui/primitives";
import { AgentAvatar, IconPicker } from "@/shared/ui/icons";
import { SaveBar } from "@/shared/components/library";
import type { Agent } from "./types";
import { EMPTY_FORM, toPayload, type AgentForm } from "./form";
import { ModelFields } from "./ModelFields";
import { INSTRUCTION_TEMPLATES } from "./templates";

export default function AgentCreate() {
  const nav = useNavigate();
  const { can, user } = useAuth();
  const providers = useProviders();
  const back = useReturnTo("/agents");
  const [form, setForm] = useState<AgentForm>(EMPTY_FORM);
  const [template, setTemplate] = useState("blank");
  const [scope, setScope] = useState<"org" | "global">("org");
  const [iconTouched, setIconTouched] = useState(false);

  const create = useAction(() => http.post<Agent>("/agents", { ...toPayload(form, providers.data), scope }), {
    success: "Agent created",
    invalidate: [["agents"]],
    onSuccess: (a) => nav(`/agents/${a.id}`, { replace: true }),
  });

  if (!can("member")) {
    return (
      <Page>
        <EmptyState title="You can't create agents" description="Ask an organization admin for member access." />
      </Page>
    );
  }

  const pickTemplate = (key: string) => {
    const t = INSTRUCTION_TEMPLATES.find((x) => x.key === key);
    if (!t) return;
    setTemplate(key);
    setForm((f) => ({ ...f, system_prompt: t.prompt, ...(iconTouched ? {} : { avatar: t.avatar, color: t.color }) }));
  };

  return (
    <Page>
      <PageHeader
        back={back}
        icon={<AgentAvatar agent={{ avatar: form.avatar, color: form.color }} size="md" />}
        title="New agent"
        description="Agents are reusable across projects. Project context, documents and memory are added at run time. You can refine everything after creating it."
      />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (form.name.trim()) create.mutate();
        }}
        className="space-y-5"
      >
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <Card>
            <CardHeader title="Basics" />
            <div className="space-y-4 p-4 sm:p-5">
              <Field label="Name">
                <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Research Analyst" maxLength={120} autoFocus required />
              </Field>
              <Field label="Description" hint="Shown to teammates and used by supervisors and routers to pick the right agent.">
                <Textarea rows={3} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Finds and verifies up-to-date information on the web." maxLength={4000} />
              </Field>
              {user?.is_superadmin && (
                <Field label="Library scope" hint="Global agents are shared (read-only) with every organization.">
                  <Select value={scope} onChange={(e) => setScope(e.target.value as "org" | "global")}>
                    <option value="org">This organization</option>
                    <option value="global">Global library</option>
                  </Select>
                </Field>
              )}
            </div>
          </Card>
          <Card>
            <CardHeader title="Icon" description="Pick a flat icon and accent color." />
            <div className="p-4">
              <IconPicker
                icon={form.avatar}
                color={form.color}
                onChange={(v) => {
                  setIconTouched(true);
                  setForm((f) => ({ ...f, avatar: v.icon, color: v.color }));
                }}
              />
            </div>
          </Card>
        </div>

        <Card>
          <CardHeader title="Starting instructions" description="Pick a template for the system prompt. You can edit it on the Instructions page." />
          <div className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4">
            {INSTRUCTION_TEMPLATES.map((t) => {
              const active = template === t.key;
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => pickTemplate(t.key)}
                  aria-pressed={active}
                  className={cn(
                    "relative flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-left transition-all",
                    active ? "border-primary bg-gradient-to-br from-primary-soft to-transparent ring-1 ring-primary/30" : "border-border bg-surface hover:border-indigo-500/30 hover:bg-surface-2/50",
                  )}
                >
                  <t.icon className={cn("mt-0.5 size-4 shrink-0", active ? "text-primary" : "text-muted")} />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{t.label}</span>
                    <span className="block text-xs text-muted">{t.description}</span>
                  </span>
                  {active && <Check className="absolute right-2.5 top-2.5 size-4 text-primary" />}
                </button>
              );
            })}
          </div>
          {form.system_prompt && (
            <div className="px-4 pb-4 sm:px-5 sm:pb-5">
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-surface-2/40 px-3 py-2.5 font-mono text-xs leading-5 text-muted">{form.system_prompt}</pre>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Model" description="Defaults to the organization model. Fine-tune effort, temperature and limits later." />
          <div className="p-4 sm:p-5">
            <ModelFields value={form} onChange={(patch) => setForm((f) => ({ ...f, ...patch }))} compact />
          </div>
        </Card>

        <SaveBar>
          <Button type="button" variant="outline" onClick={() => nav(back)}>
            Cancel
          </Button>
          <Button type="submit" icon={<Plus className="size-4" />} loading={create.isPending} disabled={!form.name.trim()}>
            Create agent
          </Button>
        </SaveBar>
      </form>
    </Page>
  );
}
