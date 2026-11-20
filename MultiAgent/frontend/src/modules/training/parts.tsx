/** Shared bits for the training pages. */
import type { LucideIcon } from "lucide-react";
import { BookOpen, Eraser, GraduationCap, ListChecks, MessagesSquare, Sparkles, ThumbsDown } from "lucide-react";
import type { Agent } from "@/modules/agents/types";
import type { User } from "@/shared/lib/types";
import { cn } from "@/shared/lib/utils";
import type { Lesson, LessonKind } from "./types";

export const KINDS: Record<LessonKind, { label: string; plural: string; icon: LucideIcon; hint: string; tile: string }> = {
  rule: { label: "Rule", plural: "Rules", icon: ListChecks, hint: "An instruction or preference to always follow.", tile: "from-indigo-500/15 to-violet-500/10 text-indigo-600 dark:text-indigo-300" },
  fact: { label: "Fact", plural: "Facts", icon: BookOpen, hint: "Something true about your business or domain.", tile: "from-sky-500/15 to-cyan-500/10 text-sky-600 dark:text-sky-300" },
  example: { label: "Q&A example", plural: "Examples", icon: MessagesSquare, hint: "A question and the ideal answer to model.", tile: "from-emerald-500/15 to-teal-500/10 text-emerald-600 dark:text-emerald-300" },
  correction: { label: "Correction", plural: "Corrections", icon: Eraser, hint: "Fix a mistake the agent made.", tile: "from-amber-500/15 to-orange-500/10 text-amber-600 dark:text-amber-300" },
};
export const KIND_ORDER: LessonKind[] = ["rule", "fact", "example", "correction"];

export const SOURCE: Record<Lesson["source"], { label: string; tone: "primary" | "warning" | "muted"; icon: LucideIcon }> = {
  auto: { label: "Learned from chat", tone: "primary", icon: Sparkles },
  feedback: { label: "From thumbs-down", tone: "warning", icon: ThumbsDown },
  user: { label: "Taught by you", tone: "muted", icon: GraduationCap },
};

/** Global agents are read-only unless you are a platform admin; viewers can never edit. */
export function canTrain(agent: Pick<Agent, "org_id"> | undefined, user: User | null, isMember: boolean): boolean {
  return !!agent && isMember && (agent.org_id !== null || !!user?.is_superadmin);
}

export function KindIcon({ kind, className }: { kind: LessonKind; className?: string }) {
  const k = KINDS[kind] ?? KINDS.rule;
  return (
    <span className={cn("inline-flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br", k.tile, className)}>
      <k.icon className="size-3.5" strokeWidth={2} />
    </span>
  );
}

/** Render a lesson body according to its kind. */
export function LessonBody({ lesson }: { lesson: Pick<Lesson, "kind" | "content" | "prompt"> }) {
  if (lesson.kind === "example" && lesson.prompt)
    return (
      <div className="space-y-1.5 text-sm">
        <div><span className="mr-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">Q</span>{lesson.prompt}</div>
        <div className="whitespace-pre-wrap"><span className="mr-1.5 text-[11px] font-semibold uppercase tracking-wide text-success">A</span>{lesson.content}</div>
      </div>
    );
  if (lesson.kind === "correction" && lesson.prompt)
    return (
      <div className="space-y-1.5 text-sm">
        <div className="text-muted line-through decoration-danger/60">{lesson.prompt}</div>
        <div className="whitespace-pre-wrap">{lesson.content}</div>
      </div>
    );
  return <div className="whitespace-pre-wrap text-sm">{lesson.content}</div>;
}
