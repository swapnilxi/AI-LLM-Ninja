import { useMemo, useRef, useState } from "react";
import { ChevronDown, Eye, FileText, Layers, PenLine, Plus } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { cn } from "@/shared/lib/utils";
import { useSkills } from "@/modules/skills/api";
import { Badge, Button, Card, CardHeader, Tabs } from "@/shared/ui/primitives";
import { CopyButton } from "@/shared/ui/inputs";
import { ConfirmDialog, Menu, MenuItem } from "@/shared/ui/overlay";
import { useAgentWorkspace } from "../context";
import { INSTRUCTION_TEMPLATES, PROMPT_SECTIONS, type InstructionTemplate } from "../templates";

const MAX = 50000;

export default function Instructions() {
  const { form, set, readOnly } = useAgentWorkspace();
  const [view, setView] = useState<"write" | "preview">("write");
  const [pendingTemplate, setPendingTemplate] = useState<InstructionTemplate | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);
  const text = form.system_prompt;

  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const tokens = Math.ceil(text.length / 4);

  const insert = (snippet: string) => {
    const el = ref.current;
    const start = el?.selectionStart ?? text.length;
    const end = el?.selectionEnd ?? text.length;
    const before = text.slice(0, start);
    const after = text.slice(end);
    const pre = before.length === 0 ? "" : before.endsWith("\n\n") ? "" : before.endsWith("\n") ? "\n" : "\n\n";
    const post = after.length === 0 || after.startsWith("\n") ? "" : "\n\n";
    const next = before + pre + snippet + post + after;
    set("system_prompt", next.slice(0, MAX));
    const caret = (before + pre + snippet).length;
    requestAnimationFrame(() => {
      if (!ref.current) return;
      ref.current.focus();
      ref.current.setSelectionRange(caret, caret);
    });
  };

  const applyTemplate = (t: InstructionTemplate) => (text.trim() ? setPendingTemplate(t) : set("system_prompt", t.prompt));

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
      <Card className="min-w-0">
        <CardHeader
          title="System prompt"
          description="Who the agent is and how it should work. Context, skills, documents and memory are layered on top at run time."
          actions={
            <Tabs
              tabs={[
                { key: "write", label: <span className="inline-flex items-center gap-1.5"><PenLine className="size-3.5" />Write</span> },
                { key: "preview", label: <span className="inline-flex items-center gap-1.5"><Eye className="size-3.5" />Full prompt</span> },
              ]}
              value={view}
              onChange={setView}
              className="border-b-0"
            />
          }
        />
        {view === "write" ? (
          <>
            {!readOnly && (
              <div className="flex flex-wrap items-center gap-1.5 border-b border-border px-3 py-2 sm:px-4">
                <span className="mr-1 text-xs font-medium text-muted">Insert</span>
                {PROMPT_SECTIONS.map((s) => (
                  <button
                    key={s.key}
                    type="button"
                    onClick={() => insert(s.snippet)}
                    className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-border bg-surface px-2 py-1 text-xs font-medium text-fg transition-colors hover:border-primary/40 hover:bg-primary-soft hover:text-primary"
                  >
                    <Plus className="size-3" />
                    {s.label}
                  </button>
                ))}
                <Menu
                  className="ml-auto"
                  trigger={
                    <Button size="sm" variant="ghost" icon={<FileText className="size-3.5" />}>
                      Templates <ChevronDown className="size-3.5" />
                    </Button>
                  }
                >
                  {(close) =>
                    INSTRUCTION_TEMPLATES.filter((t) => t.prompt).map((t) => (
                      <MenuItem
                        key={t.key}
                        icon={<t.icon className="size-4 text-muted" />}
                        onClick={() => {
                          close();
                          applyTemplate(t);
                        }}
                      >
                        {t.label}
                      </MenuItem>
                    ))
                  }
                </Menu>
              </div>
            )}
            <div className="p-3 sm:p-4">
              <textarea
                ref={ref}
                value={text}
                readOnly={readOnly}
                maxLength={MAX}
                onChange={(e) => set("system_prompt", e.target.value)}
                spellCheck
                placeholder={"## Role\nYou are a meticulous research analyst.\n\n## Rules\n- Always cite sources\n- Prefer primary data"}
                className="block min-h-[420px] w-full resize-y rounded-lg border border-border bg-surface-2/40 px-4 py-3 font-mono text-[13px] leading-6 text-fg placeholder:text-muted/60 focus:border-primary focus:outline-none focus:ring-2 focus:ring-[var(--ring)] sm:min-h-[520px]"
              />
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
                <span>
                  {words.toLocaleString()} words · ~{tokens.toLocaleString()} tokens
                </span>
                <span className={cn("tabular-nums", text.length > MAX * 0.9 && "text-warning")}>
                  {text.length.toLocaleString()} / {MAX.toLocaleString()}
                </span>
              </div>
            </div>
          </>
        ) : (
          <LayeredPreview />
        )}
      </Card>

      <div className="space-y-5">
        <Card>
          <CardHeader title="Writing tips" />
          <ul className="space-y-2.5 p-4 text-sm text-muted">
            <li><span className="font-medium text-fg">Start with a role.</span> One sentence on who the agent is.</li>
            <li><span className="font-medium text-fg">State the goal.</span> What does a great answer achieve?</li>
            <li><span className="font-medium text-fg">Give rules, not essays.</span> Short bullets the model can follow.</li>
            <li><span className="font-medium text-fg">Show the output format.</span> An example beats a description.</li>
            <li><span className="font-medium text-fg">Keep shared context out.</span> Organization guidelines and the project brief are added automatically.</li>
          </ul>
        </Card>
        <LayerLegend />
      </div>

      <ConfirmDialog
        open={!!pendingTemplate}
        onClose={() => setPendingTemplate(null)}
        onConfirm={() => {
          if (pendingTemplate) set("system_prompt", pendingTemplate.prompt);
          setPendingTemplate(null);
        }}
        title="Replace the current prompt?"
        description={`The "${pendingTemplate?.label}" template will replace what you have written. You can still discard before saving.`}
        confirmLabel="Replace"
      />
    </div>
  );
}

function LayerLegend() {
  const { form } = useAgentWorkspace();
  const { org, project } = useAuth();
  const layers = [
    { label: "Your instructions", on: true, hint: "This page" },
    { label: "Operating context", on: true, hint: "Org, project, date" },
    { label: "Organization guidelines", on: !!org?.context?.trim(), hint: "Settings" },
    { label: "Project brief", on: !!(project?.description?.trim() || project?.context?.trim()), hint: "Project settings" },
    { label: "Skills", on: form.skill_ids.length > 0, hint: `${form.skill_ids.length} attached` },
    { label: "Pinned documents & memory", on: true, hint: "At run time" },
    { label: "Tool use & safety rules", on: true, hint: "Automatic" },
  ];
  return (
    <Card>
      <CardHeader title={<span className="inline-flex items-center gap-2"><Layers className="size-4 text-primary" />How the prompt is built</span>} description="Layers are appended in this order for every run." />
      <ol className="space-y-1 p-3">
        {layers.map((l, i) => (
          <li key={l.label} className={cn("flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm", i === 0 && "bg-primary-soft/60")}>
            <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold", l.on ? "bg-primary text-white dark:text-[#0b0d12]" : "bg-surface-2 text-muted")}>{i + 1}</span>
            <span className={cn("min-w-0 flex-1 truncate", !l.on && "text-muted")}>{l.label}</span>
            <span className="shrink-0 text-[11px] text-muted">{l.on ? l.hint : "empty"}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

/** Client-side approximation of the server's build_system_prompt (documents, memory and tool rules are summarised). */
function LayeredPreview() {
  const { form } = useAgentWorkspace();
  const { org, project } = useAuth();
  const skills = useSkills();
  const preview = useMemo(() => {
    let base = form.system_prompt.trim() || `You are ${form.name}. ${form.description}`.trim();
    if (!base.toLowerCase().startsWith("you are")) base = `You are ${form.name || "the agent"}.\n${base}`;
    const parts = [base, "", "# Operating context", `- Organization: ${org?.name ?? "…"}`, `- Project: ${project?.name ?? "…"}`, `- Today's date (UTC): ${new Date().toISOString().slice(0, 10)}`];
    if (org?.context?.trim()) parts.push("", "## Organization guidelines", org.context.trim());
    if (project && (project.description?.trim() || project.context?.trim())) {
      parts.push("", "## Project brief");
      if (project.description?.trim()) parts.push(project.description.trim());
      if (project.context?.trim()) parts.push(project.context.trim());
    }
    const attached = (skills.data ?? []).filter((s) => form.skill_ids.includes(s.id));
    if (attached.length) {
      parts.push("", "## Skills");
      attached.forEach((s) => parts.push(`### Skill: ${s.name}`, "[skill instructions]"));
    }
    parts.push("", "## Reference documents (pinned) and long-term memory", "[added at run time when present]", "", "## Tool use & safety", "[rules for the tools this agent can call]");
    return parts.join("\n");
  }, [form.system_prompt, form.name, form.description, form.skill_ids, org, project, skills.data]);

  return (
    <div className="p-3 sm:p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-muted">
          <Badge tone="muted">Preview</Badge>
          For the current project. Bracketed parts are filled in at run time.
        </div>
        <CopyButton text={preview} label="Copy" />
      </div>
      <pre className="max-h-[560px] min-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-surface-2/40 px-4 py-3 font-mono text-[12.5px] leading-6 text-fg">{preview}</pre>
    </div>
  );
}
