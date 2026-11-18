import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Trash2, UserPlus, Users } from "lucide-react";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Member, Role } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { useAction } from "@/hooks/useData";
import { ConfirmDialog, Dialog } from "@/components/ui/overlay";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, PageLoader, Select } from "@/components/ui/primitives";
import { CopyButton } from "@/components/ui/inputs";

const ROLES: { key: Role; label: string; text: string }[] = [
  { key: "owner", label: "Owner", text: "Full control, including deleting the org" },
  { key: "admin", label: "Admin", text: "Members, keys, providers, connectors, secrets" },
  { key: "member", label: "Member", text: "Build and run agents, teams, workflows" },
  { key: "viewer", label: "Viewer", text: "Read-only access" },
];

export function MembersTab() {
  const { can, user, org } = useAuth();
  const admin = can("admin");
  const owner = org?.role === "owner";
  const members = useQuery({ queryKey: ["members"], queryFn: () => http.get<Member[]>("/org/members") });
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Member | null>(null);
  const update = useAction((v: { id: string; role: Role }) => http.patch(`/org/members/${v.id}`, { role: v.role }), { success: "Role updated", invalidate: [["members"]] });
  const remove = useAction((id: string) => http.del(`/org/members/${id}`), { success: "Member removed", invalidate: [["members"]], onSuccess: () => setRemoving(null) });

  if (members.isLoading) return <PageLoader />;
  const list = members.data ?? [];
  const canEdit = (m: Member) => admin && m.user_id !== user?.id && (owner || m.role !== "owner");

  return (
    <Card>
      <CardHeader
        title="Members"
        description={`${list.length} ${list.length === 1 ? "person" : "people"} in this organization`}
        actions={admin && <Button size="sm" icon={<UserPlus className="size-3.5" />} onClick={() => setAdding(true)}>Add member</Button>}
      />
      {list.length === 0 ? (
        <EmptyState icon={<Users className="size-5" />} title="No members" className="m-4 border-0" />
      ) : (
        <ul className="divide-y divide-border">
          {list.map((m) => (
            <li key={m.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/20 to-violet-500/10 text-sm font-semibold text-primary">
                  {m.name?.[0]?.toUpperCase() ?? "?"}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <span className="truncate">{m.name}</span>
                    {m.user_id === user?.id && <Badge tone="primary">You</Badge>}
                  </div>
                  <div className="truncate text-xs text-muted">{m.email} · joined {timeAgo(m.created_at)}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 pl-12 sm:pl-0">
                {canEdit(m) ? (
                  <Select className="w-32" value={m.role} onChange={(e) => update.mutate({ id: m.id, role: e.target.value as Role })}>
                    {ROLES.filter((r) => owner || r.key !== "owner").map((r) => (
                      <option key={r.key} value={r.key}>{r.label}</option>
                    ))}
                  </Select>
                ) : (
                  <Badge tone={m.role === "owner" ? "primary" : "muted"} className="capitalize">{m.role}</Badge>
                )}
                {canEdit(m) && (
                  <Button variant="ghost" size="icon" onClick={() => setRemoving(m)} aria-label={`Remove ${m.name}`}>
                    <Trash2 className="size-4 text-muted" />
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <AddMemberDialog open={adding} onClose={() => setAdding(false)} allowOwner={owner} />
      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && remove.mutate(removing.id)}
        loading={remove.isPending}
        title={`Remove ${removing?.name}?`}
        description="They lose access to this organization immediately and their API keys for it are deleted."
        confirmLabel="Remove"
      />
    </Card>
  );
}

function AddMemberDialog({ open, onClose, allowOwner }: { open: boolean; onClose: () => void; allowOwner: boolean }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [temp, setTemp] = useState<{ email: string; password: string } | null>(null);
  const add = useAction(
    () => http.post<Member & { temporary_password?: string }>("/org/members", { email, role, name: name || undefined, password: password || undefined }),
    {
      success: "Member added",
      invalidate: [["members"]],
      onSuccess: (res) => {
        if (res.temporary_password) setTemp({ email: res.email, password: res.temporary_password });
        else close();
      },
    },
  );
  const close = () => {
    setEmail("");
    setName("");
    setPassword("");
    setRole("member");
    setTemp(null);
    onClose();
  };
  return (
    <Dialog
      open={open}
      onClose={close}
      title={temp ? "Share these sign-in details" : "Add member"}
      description={temp ? "This temporary password is shown only once. Ask them to change it after signing in." : "Existing users are added directly. New users get an account with the password you set (or a generated one)."}
      footer={
        temp ? (
          <Button onClick={close}>Done</Button>
        ) : (
          <>
            <Button variant="outline" onClick={close}>Cancel</Button>
            <Button loading={add.isPending} disabled={!email.trim()} onClick={() => add.mutate()}>Add member</Button>
          </>
        )
      }
    >
      {temp ? (
        <div className="space-y-3">
          <Field label="Email"><Input readOnly value={temp.email} /></Field>
          <Field label="Temporary password">
            <div className="flex gap-2">
              <Input readOnly value={temp.password} className="font-mono" />
              <CopyButton text={temp.password} />
            </div>
          </Field>
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="Email">
            <Input type="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" />
          </Field>
          <Field label="Role">
            <div className="grid gap-2 sm:grid-cols-2">
              {ROLES.filter((r) => allowOwner || r.key !== "owner").map((r) => (
                <button
                  key={r.key}
                  type="button"
                  onClick={() => setRole(r.key)}
                  className={`cursor-pointer rounded-lg border p-2.5 text-left transition-colors ${role === r.key ? "border-primary bg-primary-soft" : "border-border hover:bg-surface-2"}`}
                >
                  <div className="text-sm font-medium">{r.label}</div>
                  <div className="text-xs text-muted">{r.text}</div>
                </button>
              ))}
            </div>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name (new users)">
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Password (optional)" hint="Leave empty to generate one">
              <Input type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
          </div>
        </div>
      )}
    </Dialog>
  );
}
