import { useEffect, useState } from "react";
import { LogOut, Save, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { http, session } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuthResponse } from "@/lib/types";
import { errMsg, formatDate } from "@/lib/utils";
import { Button, Card, CardHeader, Field, Input } from "@/components/ui/primitives";
import { ConfirmDialog } from "@/components/ui/overlay";

export function AccountTab() {
  const { user, refresh, logout } = useAuth();
  const [name, setName] = useState("");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState<"profile" | "password" | "logout" | null>(null);
  const [askLogout, setAskLogout] = useState(false);

  useEffect(() => setName(user?.name ?? ""), [user]);

  const saveProfile = async () => {
    setBusy("profile");
    try {
      const res = await http.patch<AuthResponse>("/auth/me", { name });
      session.set(res.access_token);
      await refresh();
      toast.success("Profile updated");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const changePassword = async () => {
    if (next !== confirm) {
      toast.error("New passwords do not match");
      return;
    }
    setBusy("password");
    try {
      // Changing the password revokes other sessions; the response carries a fresh token for this one.
      const res = await http.patch<AuthResponse>("/auth/me", { current_password: current, new_password: next });
      session.set(res.access_token);
      await refresh();
      setCurrent("");
      setNext("");
      setConfirm("");
      toast.success("Password changed - other sessions were signed out");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const logoutAll = async () => {
    setBusy("logout");
    try {
      await http.post("/auth/logout-all");
      logout();
    } catch (e) {
      toast.error(errMsg(e));
      setBusy(null);
    }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader title="Profile" />
        <div className="space-y-4 p-4">
          <Field label="Name">
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Email" hint="Email cannot be changed.">
            <Input value={user?.email ?? ""} readOnly disabled />
          </Field>
          <div className="text-xs text-muted">
            Member since {formatDate(user?.created_at)}
            {user?.last_login_at && <> · last sign-in {formatDate(user.last_login_at)}</>}
            {user?.is_superadmin && <> · platform admin</>}
          </div>
          <div className="flex justify-end">
            <Button icon={<Save className="size-4" />} loading={busy === "profile"} disabled={!name.trim() || name === user?.name} onClick={saveProfile}>
              Save profile
            </Button>
          </div>
        </div>
      </Card>
      <div className="space-y-5">
        <Card>
          <CardHeader title="Change password" description="At least 8 characters with a mix of letters, numbers or symbols." />
          <div className="space-y-4 p-4">
            <Field label="Current password">
              <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="New password">
                <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
              </Field>
              <Field label="Confirm" error={confirm && next !== confirm ? "Doesn't match" : undefined}>
                <Input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
              </Field>
            </div>
            <div className="flex justify-end">
              <Button icon={<ShieldCheck className="size-4" />} loading={busy === "password"} disabled={!current || next.length < 8 || next !== confirm} onClick={changePassword}>
                Update password
              </Button>
            </div>
          </div>
        </Card>
        <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <div className="flex-1">
            <div className="text-sm font-medium">Sign out everywhere</div>
            <div className="text-xs text-muted">Revokes every active session, including this one.</div>
          </div>
          <Button variant="outline" icon={<LogOut className="size-4" />} onClick={() => setAskLogout(true)}>Sign out all</Button>
        </Card>
      </div>
      <ConfirmDialog open={askLogout} onClose={() => setAskLogout(false)} onConfirm={logoutAll} loading={busy === "logout"} title="Sign out of all sessions?" description="You will need to sign in again on every device." confirmLabel="Sign out all" danger={false} />
    </div>
  );
}
