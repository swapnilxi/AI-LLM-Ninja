import type { Role } from "@/shared/lib/types";

export interface ProviderInfo {
  key: string;
  label: string;
  models: string[];
  needs_key: boolean;
  supports_temperature: boolean;
  docs: string;
  default_base_url: string;
  configured: boolean;
  org_key: string;
  base_url: string;
  server_key: boolean;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  name: string;
  role: Role;
  created_at: string;
}
