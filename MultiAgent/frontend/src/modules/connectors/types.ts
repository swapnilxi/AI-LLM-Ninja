export interface ConnectorField {
  key: string;
  label: string;
  type: "text" | "password" | "url" | "number" | "textarea" | "boolean";
  required: boolean;
  secret: boolean;
  placeholder: string;
  help: string;
  default: any;
}

export interface Connector {
  key: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  docs_url: string;
  dynamic: boolean;
  fields: ConnectorField[];
  actions: { name: string; description: string; write: boolean }[];
}

export interface Connection {
  id: string;
  connector_key: string;
  connector_name: string;
  icon: string;
  name: string;
  config: Record<string, any>;
  enabled_tools: string[];
  enabled: boolean;
  status: string;
  created_at: string;
}
