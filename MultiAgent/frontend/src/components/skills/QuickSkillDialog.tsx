import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, LayoutTemplate, Slash } from "lucide-react";
import { http } from "@/lib/api";
import type { Skill } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAction, useTools } from "@/hooks/useData";
import { Dialog } from "@/components/ui/overlay";
import { Button, Field, Input, Textarea } from "@/components/ui/primitives";
import { MultiSelect } from "@/components/ui/inputs";

/** Create a skill (optionally with a /command) without leaving the current screen. */
export function QuickSkillDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated?: (s: Skill) => void }) {
  const tools = useTools();
  const [form, setForm] = useState({ name: "", description: "", instructions: "", command: "", argument_hint: "", command_template: "", tool_ids: [] as string[] });
  const [advanced, setAdvanced] = useState(false);
  useEffect(() => {
    if (open) setForm({ name: "", description: "", instructions: "", command: "", argument_hint: "", command_template: "", tool_ids: [] });
  }, [open]);
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));
  const create = useAction(() => http.post<Skill>("/skills", { ...form, command: form.command.trim() || null }), {
    success: "Skill created",
    invalidate: [["skills"]],
    onSuccess: (s) => {
      onCreated?.(s);
      onClose();
    },
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New skill"
      description="Teach agents a repeatable way of working. Give it a /command to invoke it from chat."
      size="lg"
      footer={
        <>
          <Link to="/skills?tab=templates" onClick={onClose} className="mr-auto inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
            <LayoutTemplate className="size-4" /> Browse templates
          </Link>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button loading={create.isPending} disabled={!form.name.trim()} onClick={() => create.mutate()}>Create skill</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name">
            <Input autoFocus value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Competitor Analysis" />
          </Field>
          <Field label="Slash command (optional)" hint="Lowercase letters, digits, - or _">
            <div className="relative">
              <Slash className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted" />
              <Input value={form.command} onChange={(e) => set("command", e.target.value.replace(/^\//, "").toLowerCase())} placeholder="compete" className="pl-8 font-mono" />
            </div>
          </Field>
        </div>
        <Field label="Description">
          <Input value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="What this skill helps with" />
        </Field>
        <Field label="Instructions" hint="Markdown. Added to the system prompt whenever this skill is active.">
          <Textarea rows={6} value={form.instructions} onChange={(e) => set("instructions", e.target.value)} placeholder={"1. …\n2. …"} />
        </Field>
        <button type="button" onClick={() => setAdvanced((a) => !a)} className="flex cursor-pointer items-center gap-1 text-sm font-medium text-muted hover:text-fg">
          <ChevronDown className={cn("size-4 transition-transform", advanced && "rotate-180")} /> Command template & tools
        </button>
        {advanced && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Argument hint">
                <Input value={form.argument_hint} onChange={(e) => set("argument_hint", e.target.value)} placeholder="<company name>" />
              </Field>
              <Field label="Command template" hint="{{ args }} = text after the command">
                <Input value={form.command_template} onChange={(e) => set("command_template", e.target.value)} placeholder="Analyse competitors of {{ args }}" />
              </Field>
            </div>
            <Field label="Bundled tools">
              <MultiSelect
                options={(tools.data ?? []).filter((t) => t.enabled).map((t) => ({ value: t.id, label: t.display_name || t.name, description: t.description, badge: t.kind }))}
                value={form.tool_ids}
                onChange={(v) => set("tool_ids", v)}
                maxHeight="max-h-48"
              />
            </Field>
          </div>
        )}
      </div>
    </Dialog>
  );
}
