/** Chat sub-pages rendered in the thread pane: /chat/:id/skills and /chat/:id/commands. */
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, LayoutTemplate, Plus, Sparkles, SquareSlash } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import type { ChatMessage, Conversation } from "@/modules/chat/types";
import { errMsg } from "@/shared/lib/utils";
import { useSkillCommands, useSkills } from "@/modules/skills/api";
import { withReturn } from "@/shared/hooks/useReturnTo";
import { Badge, Button, Card, EmptyState, PageLoader } from "@/shared/ui/primitives";
import { MultiSelect } from "@/shared/ui/inputs";
import { IconTile } from "@/shared/ui/icons";

function Pane({ back, icon, title, description, children }: { back: string; icon: ReactNode; title: ReactNode; description: ReactNode; children: ReactNode }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-4 py-5 sm:px-6 sm:py-7">
        <Link to={back} className="mb-1.5 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg">
          <ChevronLeft className="size-3.5" /> Back to chat
        </Link>
        <div className="mb-5 flex items-center gap-3">
          {icon}
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-0.5 text-sm text-muted">{description}</p>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

const useConversation = (id: string) => useQuery({ queryKey: ["conversation", id], queryFn: () => http.get<{ conversation: Conversation; messages: ChatMessage[] }>(`/conversations/${id}`) });

/** /chat/:conversationId/skills: pick skills that apply to every message of one conversation. */
export function ConversationSkillsPane({ conversationId }: { conversationId: string }) {
  const conv = useConversation(conversationId);
  if (conv.isLoading) return <PageLoader />;
  const c = conv.data?.conversation;
  if (!c) return <EmptyState className="m-6" title="Conversation not found" />;
  return <SkillsEditor key={c.id} conversation={c} />;
}

function SkillsEditor({ conversation }: { conversation: Conversation }) {
  const skills = useSkills();
  const qc = useQueryClient();
  const nav = useNavigate();
  const back = `/chat/${conversation.id}`;
  const here = `${back}/skills`;
  const [value, setValue] = useState<string[]>(conversation.skill_ids ?? []);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await http.patch(`/conversations/${conversation.id}`, { skill_ids: value });
      await qc.invalidateQueries({ queryKey: ["conversation", conversation.id] });
      toast.success(value.length ? `${value.length} skill(s) active in this chat` : "Chat skills cleared");
      nav(back);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Pane
      back={back}
      icon={<IconTile icon={Sparkles} color="violet" />}
      title="Skills for this chat"
      description="Selected skills are added on top of the agent's own skills for every message here. Use /commands for one-off skills."
    >
      <Card>
        <div className="p-3 sm:p-4">
          <MultiSelect
            options={(skills.data ?? []).map((s) => ({ value: s.id, label: s.name, description: s.description, badge: s.command ? `/${s.command}` : undefined }))}
            value={value}
            onChange={setValue}
            maxHeight="max-h-[50dvh]"
          />
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-4 py-3">
          <Link to={withReturn(`/skills/new?attach_conversation=${conversation.id}`, here)} className="mr-auto inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-fg">
            <Plus className="size-4" /> New skill
          </Link>
          <Button variant="outline" onClick={() => nav(back)}>
            Cancel
          </Button>
          <Button loading={busy} onClick={save}>
            Save
          </Button>
        </div>
      </Card>
      <Link to="/skills?tab=templates" className="mt-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg">
        <LayoutTemplate className="size-4" /> Browse skill templates
      </Link>
    </Pane>
  );
}

/** /chat/:conversationId/commands: slash commands (from skills) and built-ins. Picking one drops it into the composer. */
export function CommandsPane({ conversationId }: { conversationId: string }) {
  const commands = useSkillCommands();
  const nav = useNavigate();
  const back = `/chat/${conversationId}`;
  const pick = (draft: string) => nav(back, { state: { draft } });
  return (
    <Pane back={back} icon={<IconTile icon={SquareSlash} color="indigo" />} title="Commands" description="Type / in the message box. Skill commands apply that skill to one message.">
      <div className="space-y-5">
        <Card>
          <div className="border-b border-border px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-muted">Built-in</div>
          <ul className="space-y-1.5 px-4 py-3 text-sm">
            <li>
              <code className="font-mono">/new</code> <span className="text-muted">— start a new chat</span>
            </li>
            <li>
              <code className="font-mono">/skills</code> <span className="text-muted">— choose skills for this chat</span>
            </li>
            <li>
              <code className="font-mono">/help</code> <span className="text-muted">— this list</span>
            </li>
          </ul>
        </Card>
        <Card>
          <div className="border-b border-border px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-muted">Skill commands</div>
          {commands.isLoading ? (
            <PageLoader />
          ) : !commands.data?.length ? (
            <EmptyState
              icon={<Sparkles className="size-5" />}
              title="No skill commands yet"
              description="Give a skill a /command in the skill editor, or add one from templates."
              className="m-4 border-0 py-6"
            />
          ) : (
            <ul className="divide-y divide-border">
              {commands.data.map((c) => (
                <li key={c.command}>
                  <button onClick={() => pick(`/${c.command} `)} className="flex w-full cursor-pointer items-start gap-3 px-4 py-2.5 text-left hover:bg-surface-2">
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
        </Card>
      </div>
    </Pane>
  );
}
