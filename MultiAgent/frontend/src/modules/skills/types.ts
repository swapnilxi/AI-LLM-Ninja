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
