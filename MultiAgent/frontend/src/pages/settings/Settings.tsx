import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Tabs } from "@/components/ui/primitives";
import { GeneralTab } from "./GeneralTab";
import { ModelsTab } from "./ModelsTab";
import { MembersTab } from "./MembersTab";
import { SecretsTab } from "./SecretsTab";
import { ApiKeysTab } from "./ApiKeysTab";
import { AuditTab } from "./AuditTab";
import { AccountTab } from "./AccountTab";
import { TransferTab } from "./TransferTab";

type Tab = "general" | "models" | "members" | "secrets" | "api-keys" | "audit" | "transfer" | "account";

export default function Settings() {
  const { tab: param } = useParams();
  const nav = useNavigate();
  const { can, org } = useAuth();
  const admin = can("admin");
  const tabs: { key: Tab; label: string }[] = [
    { key: "general", label: "General" },
    { key: "models", label: "Models" },
    { key: "members", label: "Members" },
    ...(admin
      ? ([
          { key: "secrets", label: "Secrets" },
          { key: "api-keys", label: "API keys" },
          { key: "audit", label: "Audit log" },
        ] as { key: Tab; label: string }[])
      : []),
    ...(can("member") ? ([{ key: "transfer", label: "Import / Export" }] as { key: Tab; label: string }[]) : []),
    { key: "account", label: "Account" },
  ];
  const tab: Tab = tabs.some((t) => t.key === param) ? (param as Tab) : "general";

  return (
    <Page>
      <PageHeader title="Settings" description={org ? `Organization “${org.name}” · you are ${org.role}` : undefined} />
      <Tabs className="mb-5" tabs={tabs} value={tab} onChange={(t) => nav(`/settings/${t}`)} />
      {tab === "general" && <GeneralTab />}
      {tab === "models" && <ModelsTab />}
      {tab === "members" && <MembersTab />}
      {tab === "secrets" && admin && <SecretsTab />}
      {tab === "api-keys" && admin && <ApiKeysTab />}
      {tab === "audit" && admin && <AuditTab />}
      {tab === "transfer" && <TransferTab />}
      {tab === "account" && <AccountTab />}
    </Page>
  );
}
