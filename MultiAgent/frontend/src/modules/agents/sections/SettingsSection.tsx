import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Copy, Download, Trash2 } from "lucide-react";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { timeAgo } from "@/shared/lib/utils";
import { useAction } from "@/shared/hooks/useAction";
import { Button, Card, CardHeader } from "@/shared/ui/primitives";
import { CopyButton } from "@/shared/ui/inputs";
import { ConfirmDialog } from "@/shared/ui/overlay";
import { ScopeBadge } from "@/shared/components/library";
import { useAgentWorkspace } from "../context";

function Row({ title, description, action }: { title: string; description: string; action: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
      <div className="min-w-0">
        <div className="text-sm font-medium">{title}</div>
        <p className="mt-0.5 text-xs text-muted">{description}</p>
      </div>
      <div className="shrink-0">{action}</div>
    </div>
  );
}

export default function SettingsSection() {
  const { id, agent, form, readOnly, duplicate, duplicating } = useAgentWorkspace();
  const { can } = useAuth();
  const nav = useNavigate();
  const [confirm, setConfirm] = useState(false);
  const del = useAction(() => http.del(`/agents/${id}`), { success: "Agent deleted", invalidate: [["agents"]], onSuccess: () => nav("/agents") });

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(form, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(form.name || "agent").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "agent"}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Details" />
        <dl className="grid gap-4 p-4 text-sm sm:grid-cols-3 sm:p-5">
          <div className="min-w-0">
            <dt className="text-xs text-muted">Agent ID</dt>
            <dd className="mt-1 flex items-center gap-2">
              <code className="truncate font-mono text-xs">{id}</code>
              <CopyButton text={id} />
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Library scope</dt>
            <dd className="mt-1"><ScopeBadge orgId={agent.org_id} /></dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Last updated</dt>
            <dd className="mt-1">{timeAgo(agent.updated_at)}</dd>
          </div>
        </dl>
      </Card>

      <Card>
        <CardHeader title="Actions" />
        <div className="divide-y divide-border">
          {can("member") && (
            <Row
              title="Duplicate"
              description="Create an editable copy in your organization, including instructions, model, tools and skills."
              action={<Button variant="outline" icon={<Copy className="size-4" />} loading={duplicating} onClick={duplicate}>Duplicate</Button>}
            />
          )}
          <Row
            title="Export as JSON"
            description="Download this agent's configuration (as currently edited) to back it up or share it."
            action={<Button variant="outline" icon={<Download className="size-4" />} onClick={exportJson}>Export</Button>}
          />
        </div>
      </Card>

      {!readOnly && (
        <Card className="border-red-500/30">
          <CardHeader title={<span className="text-danger">Danger zone</span>} />
          <Row
            title="Delete this agent"
            description="Its documents, memories and lessons are deleted too. Teams and workflows that use it will fail until updated."
            action={<Button variant="danger" icon={<Trash2 className="size-4" />} onClick={() => setConfirm(true)}>Delete agent</Button>}
          />
        </Card>
      )}

      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => del.mutate()}
        loading={del.isPending}
        title={`Delete "${agent.name}"?`}
        description="Its documents, memories and lessons are deleted too. Teams and workflows that use it will fail until updated. This cannot be undone."
      />
    </div>
  );
}
