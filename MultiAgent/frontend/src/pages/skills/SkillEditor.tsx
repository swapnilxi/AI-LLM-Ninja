import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Copy, Save, Slash, Trash2 } from "lucide-react";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Skill } from "@/lib/types";
import { useAction, useSkill, useTools } from "@/hooks/useData";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Button, Card, CardHeader, Field, Input, PageLoader, Textarea } from "@/components/ui/primitives";
import { MultiSelect, TagInput } from "@/components/ui/inputs";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Markdown } from "@/components/ui/Markdown";
import { GlobalNotice, SaveBar, ScopeBadge } from "@/components/library";

const EMPTY = { name: "", description: "", instructions: "", tool_ids: [] as string[], tags: [] as string[], command: "", argument_hint: "", command_template: "" };

export default function SkillEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const { can, user } = useAuth();
  const skill = useSkill(id);
  const tools = useTools();
  const [form, setForm] = useState(EMPTY);
  const [preview, setPreview] = useState(false);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    if (skill.data)
      setForm({
        name: skill.data.name,
        description: skill.data.description,
        instructions: skill.data.instructions,
        tool_ids: skill.data.tool_ids,
        tags: skill.data.tags,
        command: skill.data.command ?? "",
        argument_hint: skill.data.argument_hint ?? "",
        command_template: skill.data.command_template ?? "",
      });
  }, [skill.data]);

  const readOnly = !can("member") || (!!skill.data && skill.data.org_id === null && !user?.is_superadmin);
  const payload = () => ({ ...form, command: form.command.trim() || null });
  const save = useAction(() => (isNew ? http.post<Skill>("/skills", payload()) : http.put<Skill>(`/skills/${id}`, payload())), {
    success: "Skill saved",
    invalidate: [["skills"]],
    onSuccess: (s) => isNew && nav(`/skills/${s.id}`, { replace: true }),
  });
  const dup = useAction(() => http.post<Skill>(`/skills/${id}/duplicate`), { success: "Duplicated into your org", invalidate: [["skills"]], onSuccess: (s) => nav(`/skills/${s.id}`) });
  const del = useAction(() => http.del(`/skills/${id}`), { success: "Skill deleted", invalidate: [["skills"]], onSuccess: () => nav("/skills") });

  if (!isNew && skill.isLoading) return <PageLoader />;
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <Page>
      <PageHeader
        back="/skills"
        title={isNew ? "New skill" : form.name || "Skill"}
        description={!isNew && skill.data && <ScopeBadge orgId={skill.data.org_id} />}
        actions={
          !isNew && (
            <>
              <Button variant="outline" icon={<Copy className="size-4" />} onClick={() => dup.mutate()} loading={dup.isPending}>Duplicate</Button>
              {!readOnly && <Button variant="outline" icon={<Trash2 className="size-4" />} onClick={() => setConfirm(true)}>Delete</Button>}
            </>
          )
        }
      />
      {readOnly && skill.data?.org_id === null && <GlobalNotice onDuplicate={() => dup.mutate()} busy={dup.isPending} />}
      <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader
            title="Instructions"
            description="Markdown. Injected into the system prompt of every agent that uses this skill."
            actions={<Button size="sm" variant="ghost" onClick={() => setPreview((p) => !p)}>{preview ? "Edit" : "Preview"}</Button>}
          />
          <div className="p-4">
            {preview ? (
              <div className="min-h-[320px] rounded-lg border border-border p-4"><Markdown>{form.instructions || "_Nothing yet_"}</Markdown></div>
            ) : (
              <Textarea rows={18} disabled={readOnly} value={form.instructions} onChange={(e) => set("instructions", e.target.value)} placeholder={"When asked to …\n1. …\n2. …"} className="font-mono text-[13px]" />
            )}
          </div>
        </Card>
        <div className="space-y-5">
          <Card className="space-y-4 p-4">
            <Field label="Name">
              <Input disabled={readOnly} value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Web Research" />
            </Field>
            <Field label="Description">
              <Textarea disabled={readOnly} rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} />
            </Field>
            <Field label="Tags">
              <TagInput value={form.tags} onChange={(v) => set("tags", v)} />
            </Field>
          </Card>
          <Card>
            <CardHeader title="Slash command" description="Invoke this skill on demand: in chat, the API, automations or webhooks." />
            <div className="space-y-4 p-4">
              <Field label="Command" hint="Lowercase letters, digits, - or _. Leave empty for no command.">
                <div className="relative">
                  <Slash className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted" />
                  <Input disabled={readOnly} value={form.command} onChange={(e) => set("command", e.target.value.replace(/^\//, "").toLowerCase())} placeholder="research" className="pl-8 font-mono" />
                </div>
              </Field>
              <Field label="Argument hint">
                <Input disabled={readOnly} value={form.argument_hint} onChange={(e) => set("argument_hint", e.target.value)} placeholder="<topic>" />
              </Field>
              <Field label="Prompt template (optional)" hint="{{ args }} is the text typed after the command; {{ vars.x }} and {{ project.name }} also work.">
                <Textarea disabled={readOnly} rows={3} value={form.command_template} onChange={(e) => set("command_template", e.target.value)} placeholder="Write a sourced brief on: {{ args }}" className="font-mono text-xs" />
              </Field>
              {form.command && (
                <div className="rounded-lg border border-border bg-surface-2/60 p-3 text-xs">
                  <div className="mb-1 font-medium text-muted">Try it in chat</div>
                  <code className="font-mono text-fg">/{form.command} {form.argument_hint || "…"}</code>
                </div>
              )}
            </div>
          </Card>
          <Card>
            <CardHeader title="Bundled tools" description="Agents with this skill automatically get these tools." />
            <div className="p-3">
              <MultiSelect
                options={(tools.data ?? []).filter((t) => t.enabled).map((t) => ({ value: t.id, label: t.display_name || t.name, description: t.description, badge: t.kind }))}
                value={form.tool_ids}
                onChange={(v) => !readOnly && set("tool_ids", v)}
              />
            </div>
          </Card>
        </div>
      </div>
      {!readOnly && (
        <SaveBar>
          <Button variant="outline" onClick={() => nav("/skills")}>Cancel</Button>
          <Button icon={<Save className="size-4" />} loading={save.isPending} disabled={!form.name.trim()} onClick={() => save.mutate()}>
            Save skill
          </Button>
        </SaveBar>
      )}
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={() => del.mutate()} loading={del.isPending} title="Delete this skill?" description="Agents using it will no longer receive its instructions." />
    </Page>
  );
}
