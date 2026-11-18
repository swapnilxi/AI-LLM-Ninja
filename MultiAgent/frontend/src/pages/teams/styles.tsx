import type { LucideIcon } from "lucide-react";
import { ListOrdered, Network, Repeat, Route, Split } from "lucide-react";
import type { TeamStyle } from "@/lib/types";

export const TEAM_STYLES: { key: TeamStyle; label: string; icon: LucideIcon; color: string; summary: string; detail: string }[] = [
  {
    key: "sequential",
    label: "Pipeline",
    icon: ListOrdered,
    color: "sky",
    summary: "One after another",
    detail: "Each member builds on the previous member's output, like an assembly line (research → write → review).",
  },
  {
    key: "parallel",
    label: "Parallel panel",
    icon: Split,
    color: "emerald",
    summary: "Everyone at once, then merge",
    detail: "All members answer the same task independently and at the same time; an aggregator merges the best parts.",
  },
  {
    key: "supervisor",
    label: "Supervisor",
    icon: Network,
    color: "violet",
    summary: "A manager delegates",
    detail: "A manager agent breaks the task down, hands sub-tasks to specialists and writes the final answer.",
  },
  {
    key: "router",
    label: "Router",
    icon: Route,
    color: "amber",
    summary: "Pick the best expert",
    detail: "A router reads the task and sends it to the single most suitable member.",
  },
  {
    key: "round_robin",
    label: "Group chat",
    icon: Repeat,
    color: "rose",
    summary: "Take turns & debate",
    detail: "Members take turns on a shared conversation until they agree (termination keyword) or rounds run out.",
  },
];

export const styleMeta = (key: string) => TEAM_STYLES.find((s) => s.key === key) ?? TEAM_STYLES[0];
