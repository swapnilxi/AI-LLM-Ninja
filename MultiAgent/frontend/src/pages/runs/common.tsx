import { Bot, Users, Workflow as WorkflowIcon } from "lucide-react";
import type { TargetType } from "@/lib/types";
import { IconTile } from "@/components/ui/icons";

export const TARGET_META: Record<TargetType, { label: string; icon: typeof Bot; color: string; path: string }> = {
  agent: { label: "Agent", icon: Bot, color: "indigo", path: "/agents" },
  team: { label: "Team", icon: Users, color: "violet", path: "/teams" },
  workflow: { label: "Workflow", icon: WorkflowIcon, color: "teal", path: "/workflows" },
};

export function TargetIcon({ type, size = "sm" }: { type: TargetType; size?: "xs" | "sm" | "md" }) {
  const m = TARGET_META[type] ?? TARGET_META.agent;
  return <IconTile icon={m.icon} color={m.color} size={size} />;
}

export const TRIGGERS = ["manual", "chat", "api", "schedule", "webhook"];
export const STATUSES = ["queued", "running", "succeeded", "failed", "cancelled"];
