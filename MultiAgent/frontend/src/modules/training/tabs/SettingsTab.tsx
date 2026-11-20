import { Link } from "react-router-dom";
import { Brain, FileText, GraduationCap, Inbox, Layers, Pin, ScrollText } from "lucide-react";
import { http } from "@/shared/lib/api";
import { bytes } from "@/shared/lib/utils";
import type { Skill } from "@/modules/skills/types";
import { useAction } from "@/shared/hooks/useAction";
import { Button, Card, CardHeader, Stat, Switch } from "@/shared/ui/primitives";
import type { TabProps } from "../AgentTraining";
import { useTraining } from "../api";
import { KIND_ORDER, KINDS, KindIcon } from "../parts";

export function SettingsTab({ agent, canEdit }: TabProps) {
  const overview = useTraining(agent.id);
  const o = overview.data;
  const toggle = useAction((v: boolean) => http.put(`/agents/${agent.id}/training/settings`, { auto_learn: v }), {
    invalidate: [["training", agent.id], ["training", "grid"], ["agents"]],
  });
  const distill = useAction(() => http.post<Skill>(`/agents/${agent.id}/training/distill`), { success: "Playbook updated", invalidate: [["skills"], ["agents"]] });
  const configurable = canEdit && !!o?.can_configure;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Documents" value={o?.documents ?? "—"} hint={o ? `${bytes(o.document_bytes)} of text` : undefined} icon={<FileText className="size-4" />} />
        <Stat label="Chunks indexed" value={o?.chunks ?? "—"} hint={o ? `${o.pinned_documents} pinned document${o.pinned_documents === 1 ? "" : "s"}` : undefined} icon={<Layers className="size-4" />} />
        <Stat label="Lessons" value={o?.approved ?? "—"} hint={o ? `${o.pending} pending · ${o.rejected} rejected` : undefined} icon={<GraduationCap className="size-4" />} />
        <Stat label="Memories" value={o?.memories ?? "—"} hint="Up to 500 per agent" icon={<Brain className="size-4" />} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Auto-learn" description="Let the agent propose lessons by itself." />
          <div className="space-y-3 p-3 sm:p-4">
            <Switch
              checked={!!o?.auto_learn}
              disabled={!configurable || toggle.isPending}
              onChange={(v) => toggle.mutate(v)}
              label="Auto-learn after every chat"
              description={
                o && !o.can_configure
                  ? "This is a global agent. Duplicate it into your organization to turn this on."
                  : "After each answer the agent reflects on the exchange (one extra short model call) and queues lessons for review. Thumbs-down feedback always queues a lesson, even with this off."
              }
            />
            {!!o?.pending && (
              <Link to={`/training/${agent.id}/review`} className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline">
                <Inbox className="size-3.5" /> {o.pending} lesson{o.pending === 1 ? "" : "s"} waiting for review
              </Link>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Distill playbook" description="Merge everything taught and approved into one skill attached to the agent. Run it again any time to refresh it." />
          <div className="space-y-3 p-3 sm:p-4">
            <Button variant="outline" icon={<ScrollText className="size-4" />} disabled={!configurable || !o?.memories} loading={distill.isPending} onClick={() => distill.mutate()}>
              Distill into a skill
            </Button>
            {distill.data && (
              <p className="text-xs text-muted">
                Skill <Link className="font-medium text-primary hover:underline" to={`/skills/${distill.data.id}`}>{distill.data.name}</Link> updated and attached to this agent.
              </p>
            )}
            {!o?.memories && <p className="text-xs text-muted">Teach the agent or approve some lessons first.</p>}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Lessons by type" description="Approved and taught lessons, as they are stored in memory." />
        <div className="grid grid-cols-2 gap-3 p-3 sm:p-4 lg:grid-cols-4">
          {KIND_ORDER.map((k) => (
            <div key={k} className="flex items-center gap-3 rounded-xl border border-border p-3">
              <KindIcon kind={k} className="size-9" />
              <div>
                <div className="text-lg font-semibold tabular-nums leading-tight">{o?.approved_by_kind?.[k] ?? 0}</div>
                <div className="text-xs text-muted">{KINDS[k].plural}</div>
              </div>
            </div>
          ))}
        </div>
        {!!o?.pinned_documents && (
          <div className="flex items-center gap-2 border-t border-border px-4 py-3 text-xs text-muted sm:px-5">
            <Pin className="size-3.5" /> Pinned documents are added to every prompt, up to about 16,000 characters in total.
          </div>
        )}
      </Card>
    </div>
  );
}
