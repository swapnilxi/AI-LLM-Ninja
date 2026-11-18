export type Role = "owner" | "admin" | "member" | "viewer";
export type TargetType = "agent" | "team" | "workflow";
export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type TeamStyle = "sequential" | "parallel" | "supervisor" | "router" | "round_robin";
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

export interface Project {
  id: string;
  org_id: string;
  name: string;
  description: string;
  context: string;
  variables: Record<string, any>;
  settings: ProjectSettings;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectSettings {
  web_access?: boolean;
  memory_enabled?: boolean;
  browser_for_all_agents?: boolean;
  browser_render_js?: boolean;
  allowed_domains?: string[];
  blocked_domains?: string[];
  shared_tool_ids?: string[];
  connection_ids?: string[];
  blocked_tools?: string[];
  default_agent_id?: string;
  timezone?: string;
}

export interface AgentSettings {
  browser_enabled?: boolean;
  memory_enabled?: boolean;
  knowledge_enabled?: boolean;
  show_thinking?: boolean;
  auto_learn?: boolean;
}

export interface Agent {
  id: string;
  org_id: string | null;
  name: string;
  description: string;
  avatar: string;
  color: string;
  provider: string;
  model: string;
  system_prompt: string;
  temperature: number | null;
  max_tokens: number;
  max_steps: number;
  effort: Effort;
  tool_ids: string[];
  skill_ids: string[];
  connection_ids: string[];
  settings: AgentSettings;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface Skill {
  id: string;
  org_id: string | null;
  name: string;
  description: string;
  instructions: string;
  tool_ids: string[];
  tags: string[];
  command: string | null;
  argument_hint: string | null;
  command_template: string | null;
  created_at: string;
  updated_at: string;
}

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

export interface JSONSchema {
  type: "object";
  properties: Record<string, { type?: string; description?: string; enum?: string[]; default?: any }>;
  required?: string[];
}

export interface TeamMember {
  agent_id: string;
  role: string;
  instructions: string;
}

export interface Team {
  id: string;
  org_id: string | null;
  name: string;
  description: string;
  style: TeamStyle;
  members: TeamMember[];
  manager_agent_id: string | null;
  config: { max_rounds?: number; termination_keyword?: string; aggregator_agent_id?: string; router_agent_id?: string; max_concurrency?: number };
  created_at: string;
  updated_at: string;
}

export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, any>;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

export interface InputField {
  name: string;
  label?: string;
  type?: "text" | "textarea" | "number";
  default?: any;
}

export interface Workflow {
  id: string;
  org_id: string | null;
  name: string;
  description: string;
  graph: { nodes: WorkflowNode[]; edges: WorkflowEdge[]; viewport?: any };
  input_fields: InputField[];
  created_at: string;
  updated_at: string;
}

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

export interface Doc {
  id: string;
  owner_type: "org" | "project" | "agent";
  owner_id: string;
  title: string;
  source: string;
  source_ref: string;
  mime: string;
  size: number;
  chunk_count: number;
  pinned: boolean;
  created_at: string;
  updated_at: string;
  content?: string;
}

export interface Memory {
  id: string;
  scope: "agent" | "project";
  agent_id: string | null;
  project_id: string | null;
  key: string;
  content: string;
  tags: string[];
  source: "agent" | "user" | "learned";
  run_id: string | null;
  created_at: string;
}

export interface Run {
  id: string;
  project_id: string;
  target_type: TargetType;
  target_id: string;
  target_name: string;
  status: RunStatus;
  input: Record<string, any>;
  output: string;
  error: string;
  trigger: string;
  automation_id: string | null;
  conversation_id: string | null;
  user_id: string | null;
  usage: { input_tokens?: number; output_tokens?: number; llm_calls?: number; tool_calls?: number };
  total_tokens: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunEvent {
  seq?: number;
  id?: number;
  type: string;
  agent: string;
  node_id: string;
  data: Record<string, any>;
  created_at: string;
}

export interface Conversation {
  id: string;
  project_id: string;
  target_type: "agent" | "team";
  target_id: string;
  title: string;
  skill_ids?: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  run_id: string | null;
  meta: Record<string, any>;
  created_at: string;
}

export interface Automation {
  id: string;
  project_id: string;
  name: string;
  description: string;
  target_type: TargetType;
  target_id: string;
  input: Record<string, any>;
  trigger_type: "schedule" | "interval" | "webhook" | "manual";
  cron: string;
  interval_minutes: number;
  timezone: string;
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: string;
  run_count: number;
  created_at: string;
  webhook_url: string | null;
}

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

export interface Catalog {
  styles: { key: TeamStyle; description: string }[];
  node_types: string[];
  builtin_tools: { key: string; name: string; description: string; category: string; parameters: JSONSchema }[];
  connectors: Connector[];
}

export interface SkillCommand {
  command: string;
  skill_id: string;
  name: string;
  description: string;
  argument_hint: string;
  scope: "org" | "global";
}

export interface SkillTemplate {
  key: string;
  name: string;
  category: string;
  command: string;
  argument_hint: string;
  description: string;
  tools: string[];
  command_template: string;
  preview: string;
}

export interface Lesson {
  id: string;
  agent_id: string;
  status: "pending" | "approved" | "rejected";
  source: "user" | "feedback" | "auto";
  title: string;
  content: string;
  rationale: string;
  conversation_id: string | null;
  created_at: string;
}

export interface TrainingOverview {
  auto_learn: boolean;
  can_configure: boolean;
  pending: number;
  approved: number;
  rejected: number;
  memories: number;
}
