import type { Connector } from "@/modules/connectors/types";
import type { TeamStyle } from "@/modules/teams/types";

export type Role = "owner" | "admin" | "member" | "viewer";

export type TargetType = "agent" | "team" | "workflow";

export type Effort = "low" | "medium" | "high" | "xhigh" | "max";

export interface User {
  id: string;
  email: string;
  name: string;
  is_superadmin: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface Org {
  id: string;
  name: string;
  slug: string;
  context: string;
  settings: Record<string, any>;
  created_at: string;
  role: Role;
}

export interface AuthResponse {
  access_token: string;
  user: User;
  orgs: Org[];
}

export interface JSONSchema {
  type: "object";
  properties: Record<string, { type?: string; description?: string; enum?: string[]; default?: any }>;
  required?: string[];
}

export interface Catalog {
  styles: { key: TeamStyle; description: string }[];
  node_types: string[];
  builtin_tools: { key: string; name: string; description: string; category: string; parameters: JSONSchema }[];
  connectors: Connector[];
}
