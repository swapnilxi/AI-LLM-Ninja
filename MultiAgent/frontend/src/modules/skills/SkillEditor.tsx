import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Copy, Link2, Save, Slash, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { errMsg } from "@/shared/lib/utils";
import { useAuth } from "@/shared/lib/auth";
import type { Skill } from "@/modules/skills/types";
import type { Agent } from "@/modules/agents/types";
import type { Conversation } from "@/modules/chat/types";
import { useAgent } from "@/modules/agents/api";
import { useReturnTo } from "@/shared/hooks/useReturnTo";
import { useAction } from "@/shared/hooks/useAction";
import { useSkill } from "@/modules/skills/api";
import { useTools } from "@/modules/tools/api";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Button, Card, CardHeader, Field, Input, PageLoader, Textarea } from "@/shared/ui/primitives";
import { MultiSelect, TagInput } from "@/shared/ui/inputs";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { Markdown } from "@/shared/ui/Markdown";
import { GlobalNotice, SaveBar, ScopeBadge } from "@/shared/components/library";

const EMPTY = { name: "", description: "", instructions: "", tool_ids: [] as string[], tags: [] as string[], command: "", argument_hint: "", command_template: "" };

/**
 * /skills/:id and /skills/new. New skills accept:
 *   ?attach_agent=<agentId>         append the created skill to that agent's skill_ids
 *   ?attach_conversation=<convId>   append it to that chat's skills
 *   ?return_to=<path>               where to go after saving / on cancel (default: the new skill's page)
 */
export default function SkillEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const attachAgent = isNew ? params.get("attach_agent") : null;
  const attachConversation = isNew ? params.get("attach_conversation") : null;
  const hasReturn = !!params.get("return_to");
  const returnTo = useReturnTo("/skills");
  const agentToAttach = useAgent(attachAgent ?? undefined);
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
  /** Attach a freshly created skill to the agent / conversation named in the URL. */
  const attach = async (s: Skill) => {
    if (attachAgent) {
      const a = await http.get<Agent>(`/agents/${attachAgent}`);
      if (!a.skill_ids.includes(s.id)) {
        // full-body PUT, exactly like the agent editor
        await http.put<Agent>(`/agents/${attachAgent}`, { ...a, skill_ids: [...a.skill_ids, s.id] });
      }
      // drop the cached agent so the page we return to loads it fresh (with the new skill) instead of flashing stale data
      qc.removeQueries({ queryKey: ["agents", attachAgent] });
      qc.invalidateQueries({ queryKey: ["agents"] });
    }
    if (attachConversation) {
      const { conversation: c } = await http.get<{ conversation: Conversation }>(`/conversations/${attachConversation}`);
      const ids = c.skill_ids ?? [];
      if (!ids.includes(s.id)) await http.patch(`/conversations/${attachConversation}`, { skill_ids: [...ids, s.id] });
      qc.removeQueries({ queryKey: ["conversation", attachConversation] });
    }
  };
  const save = useAction(
    async () => {
      if (!isNew) return http.put<Skill>(`/skills/${id}`, payload());
      const s = await http.post<Skill>("/skills", payload());
      try {
        await attach(s);
      } catch (e) {
        toast.error(`Skill created, but it could not be attached: ${errMsg(e)}`);
      }
      return s;
    },
    {
      success: attachAgent || attachConversation ? "Skill created and attached" : "Skill saved",
      invalidate: [["skills"]],
      onSuccess: (s) => {
        if (!isNew) return;
        if (hasReturn || attachAgent || attachConversation) nav(returnTo, { replace: true });
        else nav(`/skills/${s.id}`, { replace: true });
      },
    },
  );
  const dup = useAction(() => http.post<Skill>(`/skills/${id}/duplicate`), { success: "Duplicated into your org", invalidate: [["skills"]], onSuccess: (s) => nav(`/skills/${s.id}`) });
  const del = useAction(() => http.del(`/skills/${id}`), { success: "Skill deleted", invalidate: [["skills"]], onSuccess: () => nav("/skills") });

  if (!isNew && skill.isLoading) return <PageLoader />;
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <Page>
      <PageHeader
        back={isNew ? returnTo : "/skills"}
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
      {(attachAgent || attachConversation) && (
        <div className="mb-5 flex items-center gap-3 rounded-xl border border-indigo-500/20 bg-gradient-to-r from-primary-soft to-transparent p-4 text-sm">
          <Link2 className="size-4 shrink-0 text-primary" />
          <span>
            After saving, this skill is attached to{" "}
            {attachAgent ? <span className="font-medium">{agentToAttach.data?.name ?? "the agent"}</span> : <span className="font-medium">this chat</span>}
            {attachAgent && attachConversation && <> and to <span className="font-medium">this chat</span></>}.
          </span>
        </div>
      )}
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
          <Button variant="outline" onClick={() => nav(isNew ? returnTo : "/skills")}>Cancel</Button>
          <Button icon={<Save className="size-4" />} loading={save.isPending} disabled={!form.name.trim()} onClick={() => save.mutate()}>
            Save skill
          </Button>
        </SaveBar>
      )}
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={() => del.mutate()} loading={del.isPending} title="Delete this skill?" description="Agents using it will no longer receive its instructions." />
    </Page>
  );
}
