import { lazy } from "react";
import { ArrowLeftRight, Building2, KeyRound, Settings as SettingsIcon, UserPlus } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const Settings = lazy(() => import("./Settings"));
const NewOrgPage = lazy(() => import("./NewOrgPage"));
const NewApiKeyPage = lazy(() => import("./ApiKeysTab").then((m) => ({ default: m.NewApiKeyPage })));
const NewMemberPage = lazy(() => import("./MembersTab").then((m) => ({ default: m.NewMemberPage })));
const SecretPage = lazy(() => import("./SecretsTab").then((m) => ({ default: m.SecretPage })));
const ProviderPage = lazy(() => import("./ModelsTab").then((m) => ({ default: m.ProviderPage })));

export default defineModule({
  id: "settings",
  nav: [{ to: "/settings", label: "Settings", icon: SettingsIcon, section: "Workspace", order: 20, keywords: "keys members models providers" }],
  commands: [
    { id: "p-xfer", label: "Import / Export library", icon: ArrowLeftRight, to: "/settings/transfer", keywords: "backup bundle json" },
    { id: "n-org", group: "Create", label: "New organization", icon: Building2, to: "/settings/organizations/new", keywords: "tenant workspace" },
    { id: "n-member", group: "Create", label: "Add member", icon: UserPlus, to: "/settings/members/new", keywords: "invite user teammate" },
    { id: "n-apikey", group: "Create", label: "New API key", icon: KeyRound, to: "/settings/api-keys/new", keywords: "token rest" },
  ],
  routes: [
    { path: "settings", element: <Settings /> },
    { path: "settings/organizations/new", element: <NewOrgPage /> },
    { path: "settings/api-keys/new", element: <NewApiKeyPage /> },
    { path: "settings/members/new", element: <NewMemberPage /> },
    { path: "settings/secrets/new", element: <SecretPage /> },
    { path: "settings/secrets/:name", element: <SecretPage /> },
    { path: "settings/models/:provider", element: <ProviderPage /> },
    { path: "settings/:tab", element: <Settings /> },
  ],
});
