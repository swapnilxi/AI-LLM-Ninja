import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { http } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Org } from "@/lib/types";
import { errMsg } from "@/lib/utils";
import { Dialog } from "@/components/ui/overlay";
import { Button, Field, Input } from "@/components/ui/primitives";

export function CreateOrgDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const { refresh, switchOrg } = useAuth();
  const nav = useNavigate();
  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const org = await http.post<Org>("/orgs", { name });
      await refresh();
      switchOrg(org.id);
      toast.success(`Created ${org.name}`);
      setName("");
      onClose();
      nav("/");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New organization"
      description="Organizations are isolated tenants with their own members, keys, connectors, projects and private library."
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!name.trim()}>
            Create
          </Button>
        </>
      }
    >
      <Field label="Name">
        <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder="Acme Inc." />
      </Field>
    </Dialog>
  );
}
