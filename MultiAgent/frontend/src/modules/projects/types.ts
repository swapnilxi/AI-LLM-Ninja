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
  skill_ids?: string[]; // project-level skills: every agent in the project gets them
  tasks_enabled?: boolean; // to-do tools for agents (default on)
  skill_discovery_enabled?: boolean; // find_skills / use_skill (default on)
  scheduling_enabled?: boolean; // schedule_task: agents can create automations (default off)
}
