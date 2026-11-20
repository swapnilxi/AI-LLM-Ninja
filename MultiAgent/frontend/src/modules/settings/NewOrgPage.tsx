import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2 } from "lucide-react";
import { toast } from "sonner";
import { http } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import type { Org } from "@/shared/lib/types";
import { errMsg } from "@/shared/lib/utils";
import { useReturnTo } from "@/shared/hooks/useReturnTo";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Button, Card, Field, Input } from "@/shared/ui/primitives";
import { IconTile } from "@/shared/ui/icons";

/** /settings/organizations/new */
export default function NewOrgPage() {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const { refresh, switchOrg } = useAuth();
  const nav = useNavigate();
  const back = useReturnTo("/settings/general");
  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const org = await http.post<Org>("/orgs", { name });
      await refresh();
      switchOrg(org.id);
      toast.success(`Created ${org.name}`);
      nav("/");
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Page className="max-w-2xl">
      <PageHeader
        back={back}
        icon={<IconTile icon={Building2} color="indigo" />}
        title="New organization"
        description="Organizations are isolated tenants with their own members, keys, connectors, projects and private library."
      />
      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div className="p-4 sm:p-5">
            <Field label="Name">
              <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Inc." />
            </Field>
          </div>
          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">
            <Button type="button" variant="outline" onClick={() => nav(back)}>
              Cancel
            </Button>
            <Button type="submit" loading={busy} disabled={!name.trim()}>
              Create organization
            </Button>
          </div>
        </form>
      </Card>
    </Page>
  );
}
