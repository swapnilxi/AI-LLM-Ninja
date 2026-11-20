import { useState } from "react";
import { GraduationCap, Plus } from "lucide-react";
import { http } from "@/shared/lib/api";
import { cn, timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Spinner, Tabs, Textarea } from "@/shared/ui/primitives";
import type { TabProps } from "../AgentTraining";
import { trainingKeys, useLessons } from "../api";
import { KIND_ORDER, KINDS, KindIcon, LessonBody, SOURCE } from "../parts";
import type { LessonKind } from "../types";

const PLACEHOLDERS: Record<LessonKind, { content: string; prompt?: string; contentLabel: string; promptLabel?: string }> = {
  rule: { contentLabel: "Rule", content: "Always open with a one-line summary, then the details." },
  fact: { contentLabel: "Fact", content: "Our fiscal year starts on 1 April. Support hours are 9am-6pm CET on weekdays." },
  example: { contentLabel: "Ideal answer", promptLabel: "Question", prompt: "How do I reset my password?", content: "Go to Settings > Account and click Reset password. You will get an email within a minute." },
  correction: { contentLabel: "What it should do instead", promptLabel: "What it got wrong (optional)", prompt: "Said that refunds take 30 days.", content: "Refunds are processed within 14 days of receiving the return." },
};

export function TeachTab({ agent, canEdit }: TabProps) {
  const [kind, setKind] = useState<LessonKind>("rule");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [content, setContent] = useState("");
  const [filter, setFilter] = useState<"all" | LessonKind>("all");
  const approved = useLessons(agent.id, "approved");
  const ph = PLACEHOLDERS[kind];
  const needsPrompt = kind === "example";
  const valid = !!content.trim() && (!needsPrompt || !!prompt.trim());

  const teach = useAction(
    () => http.post(`/agents/${agent.id}/lessons`, { kind, title: title.trim(), content: content.trim(), prompt: ph.promptLabel ? prompt.trim() || undefined : undefined }),
    {
      success: `${KINDS[kind].label} saved to memory`,
      invalidate: trainingKeys(agent.id),
      onSuccess: () => {
        setTitle("");
        setPrompt("");
        setContent("");
      },
    },
  );

  const items = (approved.data ?? []).filter((l) => filter === "all" || (l.kind ?? "rule") === filter);
  const counts = (approved.data ?? []).reduce<Record<string, number>>((acc, l) => ({ ...acc, [l.kind ?? "rule"]: (acc[l.kind ?? "rule"] ?? 0) + 1 }), {});

  return (
    <div className="space-y-5">
      {canEdit && (
        <Card>
          <CardHeader title="Teach this agent" description="Taught lessons are saved to the agent's memory immediately and included in every future prompt." />
          <div className="space-y-4 p-3 sm:p-4">
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-4" role="radiogroup" aria-label="Lesson type">
              {KIND_ORDER.map((k) => {
                const meta = KINDS[k];
                const active = kind === k;
                return (
                  <button
                    key={k}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => setKind(k)}
                    className={cn(
                      "flex cursor-pointer items-start gap-2.5 rounded-xl border p-3 text-left transition-colors",
                      active ? "border-primary bg-primary-soft/50 ring-1 ring-primary/30" : "border-border hover:bg-surface-2",
                    )}
                  >
                    <KindIcon kind={k} />
                    <span className="min-w-0">
                      <span className="block text-sm font-medium">{meta.label}</span>
                      <span className="mt-0.5 hidden text-xs text-muted sm:block">{meta.hint}</span>
                    </span>
                  </button>
                );
              })}
            </div>

            {ph.promptLabel && (
              <Field label={ph.promptLabel}>
                <Textarea rows={2} maxLength={2000} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={ph.prompt} />
              </Field>
            )}
            <Field label={ph.contentLabel}>
              <Textarea rows={kind === "example" ? 5 : 4} maxLength={2000} value={content} onChange={(e) => setContent(e.target.value)} placeholder={ph.content} />
            </Field>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <Field label="Title (optional)" className="flex-1">
                <Input maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Short label, defaults to the first words" />
              </Field>
              <Button icon={<Plus className="size-4" />} disabled={!valid} loading={teach.isPending} onClick={() => teach.mutate()}>
                Teach {KINDS[kind].label.toLowerCase()}
              </Button>
            </div>
          </div>
        </Card>
      )}

      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2">What it has learned {!!approved.data?.length && <Badge tone="muted">{approved.data.length}</Badge>}</span>}
          description="Approved and taught lessons. Edit or delete their memory text on the Memory tab."
        />
        <div className="px-3 pt-2 sm:px-4">
          <Tabs
            value={filter}
            onChange={setFilter}
            tabs={[{ key: "all" as const, label: "All", count: approved.data?.length }, ...KIND_ORDER.map((k) => ({ key: k, label: KINDS[k].plural, count: counts[k] ?? 0 }))]}
          />
        </div>
        <div className="p-2 sm:p-3">
          {approved.isLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : !items.length ? (
            <EmptyState icon={<GraduationCap className="size-5" />} title="Nothing here yet" description="Teach a rule, fact, example or correction above, or approve proposed lessons on the Review tab." className="border-0" />
          ) : (
            <ul className="divide-y divide-border">
              {items.map((l) => {
                const src = SOURCE[l.source] ?? SOURCE.user;
                return (
                  <li key={l.id} className="flex items-start gap-3 px-2 py-3">
                    <KindIcon kind={l.kind ?? "rule"} />
                    <div className="min-w-0 flex-1 space-y-1.5">
                      {l.title && <div className="truncate text-xs font-semibold text-muted">{l.title}</div>}
                      <LessonBody lesson={l} />
                      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
                        <Badge tone="muted">{KINDS[l.kind ?? "rule"].label}</Badge>
                        <Badge tone={src.tone} icon={<src.icon className="size-3" />}>{src.label}</Badge>
                        {timeAgo(l.created_at)}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}
