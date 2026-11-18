import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { LayoutTemplate, Plus, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/lib/api";
import type { Conversation, SkillCommand } from "@/lib/types";
import { errMsg } from "@/lib/utils";
import { useSkills } from "@/hooks/useData";
import { Dialog } from "@/components/ui/overlay";
import { Badge, Button, EmptyState } from "@/components/ui/primitives";
import { MultiSelect } from "@/components/ui/inputs";
import { QuickSkillDialog } from "@/components/skills/QuickSkillDialog";

/** Pick skills that apply to every message of one conversation. */
export function ConversationSkillsDialog({ open, onClose, conversation }: { open: boolean; onClose: () => void; conversation: Conversation }) {
  const skills = useSkills();
  const qc = useQueryClient();
  const [value, setValue] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  useEffect(() => {
    if (open) setValue(conversation.skill_ids ?? []);
  }, [open, conversation.skill_ids]);

  const save = async () => {
    setBusy(true);
    try {
      await http.patch(`/conversations/${conversation.id}`, { skill_ids: value });
      await qc.invalidateQueries({ queryKey: ["conversation", conversation.id] });
      toast.success(value.length ? `${value.length} skill(s) active in this chat` : "Chat skills cleared");
      onClose();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Dialog
        open={open && !creating}
        onClose={onClose}
        title="Skills for this chat"
        description="Selected skills are added on top of the agent's own skills for every message here. Use /commands for one-off skills."
        size="lg"
        footer={
          <>
            <Button variant="ghost" className="mr-auto" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
              New skill
            </Button>
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button loading={busy} onClick={save}>Save</Button>
          </>
        }
      >
        <MultiSelect
          options={(skills.data ?? []).map((s) => ({ value: s.id, label: s.name, description: s.description, badge: s.command ? `/${s.command}` : undefined }))}
          value={value}
          onChange={setValue}
          maxHeight="max-h-80"
        />
        <Link to="/skills?tab=templates" onClick={onClose} className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
          <LayoutTemplate className="size-4" /> Browse skill templates
        </Link>
      </Dialog>
      <QuickSkillDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(s) => {
          setValue((v) => [...v, s.id]);
          qc.invalidateQueries({ queryKey: ["skills"] });
        }}
      />
    </>
  );
}

/** Lists slash commands (from skills) and built-ins. */
export function CommandsHelpDialog({ open, onClose, commands, onPick }: { open: boolean; onClose: () => void; commands: SkillCommand[]; onPick: (cmd: string) => void }) {
  return (
    <Dialog open={open} onClose={onClose} title="Commands" description="Type / in the message box. Skill commands apply that skill to one message." size="lg">
      <div className="space-y-4">
        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Built-in</div>
          <ul className="space-y-1 text-sm">
            <li><code className="font-mono">/new</code> <span className="text-muted">— start a new chat</span></li>
            <li><code className="font-mono">/skills</code> <span className="text-muted">— choose skills for this chat</span></li>
            <li><code className="font-mono">/help</code> <span className="text-muted">— this list</span></li>
          </ul>
        </div>
        <div>
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Skill commands</div>
          {commands.length === 0 ? (
            <EmptyState icon={<Sparkles className="size-5" />} title="No skill commands yet" description="Give a skill a /command in the skill editor, or add one from templates." className="py-6" />
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {commands.map((c) => (
                <li key={c.command}>
                  <button
                    onClick={() => {
                      onPick(`/${c.command} `);
                      onClose();
                    }}
                    className="flex w-full cursor-pointer items-start gap-3 px-3 py-2.5 text-left hover:bg-surface-2"
                  >
                    <code className="shrink-0 font-mono text-sm font-medium text-primary">/{c.command}</code>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm">
                        {c.name} {c.argument_hint && <span className="font-mono text-xs text-muted">{c.argument_hint}</span>}
                      </div>
                      <div className="line-clamp-1 text-xs text-muted">{c.description}</div>
                    </div>
                    {c.scope === "global" && <Badge tone="muted">global</Badge>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Dialog>
  );
}
