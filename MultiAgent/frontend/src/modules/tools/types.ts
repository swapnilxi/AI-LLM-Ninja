import type { JSONSchema } from "@/shared/lib/types";

export interface Tool {
  id: string;
  org_id: string | null;
  name: string;
  display_name: string;
  description: string;
  kind: "builtin" | "http" | "agent";
  builtin_key: string | null;
  category: string;
  parameters: JSONSchema;
  config: Record<string, any>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}
