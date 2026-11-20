import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, CircleHelp, MessageSquarePlus, Slash, Sparkles, Square, X } from "lucide-react";
import type { SkillCommand } from "@/modules/skills/types";
import { cn } from "@/shared/lib/utils";
import { Badge, Button } from "@/shared/ui/primitives";

export type BuiltinCommand = "new" | "skills" | "help";

const BUILTINS: { command: BuiltinCommand; description: string; icon: typeof Slash }[] = [
  { command: "new", description: "Start a new chat", icon: MessageSquarePlus },
  { command: "skills", description: "Choose skills for this chat", icon: Sparkles },
  { command: "help", description: "Show available commands", icon: CircleHelp },
];

type Item = { kind: "builtin"; command: BuiltinCommand; description: string; icon: typeof Slash } | { kind: "skill"; cmd: SkillCommand };

/** Chat composer with a `/` command menu for skills and built-in actions. */
export function Composer({
  disabled,
  onSend,
  busy,
  onStop,
  initial,
  commands,
  onBuiltin,
}: {
  disabled?: boolean;
  busy?: boolean;
  onSend: (text: string) => void;
  onStop?: () => void;
  initial?: string;
  commands: SkillCommand[];
  onBuiltin: (cmd: BuiltinCommand) => void;
}) {
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (initial) {
      setText(initial);
      ref.current?.focus();
    }
  }, [initial]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const query = /^\/([\w-]*)$/.exec(text)?.[1]?.toLowerCase() ?? null;
  const items: Item[] = useMemo(() => {
    if (query === null) return [];
    const b: Item[] = BUILTINS.filter((x) => x.command.startsWith(query)).map((x) => ({ kind: "builtin", ...x }));
    const s: Item[] = commands
      .filter((c) => c.command.startsWith(query) || c.name.toLowerCase().includes(query))
      .map((cmd) => ({ kind: "skill", cmd }));
    return [...s, ...b].slice(0, 12);
  }, [query, commands]);
  const menuOpen = items.length > 0 && !dismissed;
  useEffect(() => {
    setActive(0);
    setDismissed(false);
  }, [query]);

  const applied = useMemo(() => {
    const m = /^\/([\w-]+)\s/.exec(text);
    return m ? commands.find((c) => c.command === m[1].toLowerCase()) ?? null : null;
  }, [text, commands]);

  const choose = (it: Item) => {
    if (it.kind === "builtin") {
      setText("");
      onBuiltin(it.command);
    } else {
      setText(`/${it.cmd.command} `);
    }
    requestAnimationFrame(() => ref.current?.focus());
  };

  const send = () => {
    const t = text.trim();
    if (!t || disabled || busy) return;
    const builtin = BUILTINS.find((b) => t === `/${b.command}`);
    if (builtin) {
      setText("");
      onBuiltin(builtin.command);
      return;
    }
    onSend(t);
    setText("");
  };

  return (
    <div className="border-t border-border bg-surface/80 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur sm:px-6">
      <div className="relative mx-auto max-w-3xl">
        {menuOpen && (
          <div className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl border border-border bg-surface shadow-xl" role="listbox">
            <div className="flex items-center justify-between border-b border-border px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted">
              Commands
              <span className="hidden normal-case tracking-normal sm:inline">↑↓ to move · Enter to pick · Esc to close</span>
            </div>
            <div className="max-h-72 overflow-y-auto p-1">
              {items.map((it, i) => {
                const isSkill = it.kind === "skill";
                const Icon = isSkill ? Sparkles : it.icon;
                return (
                  <button
                    key={isSkill ? it.cmd.command : it.command}
                    role="option"
                    aria-selected={i === active}
                    onMouseEnter={() => setActive(i)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      choose(it);
                    }}
                    className={cn("flex w-full cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2 text-left", i === active ? "bg-primary-soft" : "hover:bg-surface-2")}
                  >
                    <div className={cn("flex size-7 shrink-0 items-center justify-center rounded-lg", isSkill ? "bg-gradient-to-br from-violet-500/20 to-indigo-500/10 text-primary" : "bg-surface-2 text-muted")}>
                      <Icon className="size-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-mono font-medium">/{isSkill ? it.cmd.command : it.command}</span>
                        {isSkill && it.cmd.argument_hint && <span className="truncate font-mono text-xs text-muted">{it.cmd.argument_hint}</span>}
                      </div>
                      <div className="truncate text-xs text-muted">{isSkill ? `${it.cmd.name} — ${it.cmd.description}` : it.description}</div>
                    </div>
                    {isSkill && it.cmd.scope === "global" && <Badge tone="muted">global</Badge>}
                  </button>
                );
              })}
            </div>
          </div>
        )}
        {applied && (
          <div className="mb-2 flex items-center gap-2 text-xs">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/20 bg-primary-soft px-2.5 py-1 font-medium text-primary">
              <Sparkles className="size-3" /> Skill: {applied.name}
            </span>
            {applied.argument_hint && <span className="truncate font-mono text-muted">{applied.argument_hint}</span>}
            <button onClick={() => setText(text.replace(/^\/[\w-]+\s*/, ""))} className="ml-auto cursor-pointer text-muted hover:text-fg" aria-label="Remove command">
              <X className="size-3.5" />
            </button>
          </div>
        )}
        <div className="flex items-end gap-2 rounded-2xl border border-border bg-surface p-2 shadow-sm focus-within:ring-2 focus-within:ring-[var(--ring)]">
          <button
            type="button"
            onClick={() => {
              setText((t) => (t.startsWith("/") ? t : "/"));
              ref.current?.focus();
            }}
            disabled={disabled}
            title="Commands"
            aria-label="Insert command"
            className="mb-0.5 flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-xl text-muted hover:bg-surface-2 hover:text-fg disabled:opacity-50"
          >
            <Slash className="size-4" />
          </button>
          <textarea
            ref={ref}
            rows={1}
            value={text}
            disabled={disabled}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (menuOpen) {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setActive((a) => (a + 1) % items.length);
                  return;
                }
                if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setActive((a) => (a - 1 + items.length) % items.length);
                  return;
                }
                if ((e.key === "Enter" && !e.shiftKey) || e.key === "Tab") {
                  e.preventDefault();
                  choose(items[active]);
                  return;
                }
                if (e.key === "Escape") {
                  setDismissed(true);
                  return;
                }
              }
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={disabled ? "You have read-only access" : "Message… type / for skills & commands"}
            className="max-h-[200px] min-h-[40px] flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-relaxed placeholder:text-muted/70 focus:outline-none"
          />
          {busy && onStop ? (
            <Button variant="outline" size="icon" onClick={onStop} aria-label="Stop" className="rounded-xl">
              <Square className="size-3.5 fill-current" />
            </Button>
          ) : (
            <Button size="icon" onClick={send} disabled={!text.trim() || disabled || busy} aria-label="Send" className="rounded-xl">
              <ArrowUp className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
