export type Trust = "official" | "community" | "built-in";

export interface HubSkillPack {
  id: string;
  name: string;
  tagline: string;
  description: string;
  category: string;
  trust: Trust;
  repo_url: string;
  command?: string;
  caveat?: string;
  skills: string[];
  installed: boolean;
  skill_ids: string[];
  instruction_chars: number;
  attached: boolean | null;
}

export interface HubMcpServer {
  id: string;
  name: string;
  tagline: string;
  category: string;
  popular: boolean;
  auth: "none" | "optional" | "bearer";
  url: string;
  docs_url: string;
  token_label?: string;
  token_url?: string;
  caveat?: string;
  connection_id: string | null;
  status: string | null;
  attached: boolean | null;
}

export interface HubKnowledge {
  id: string;
  name: string;
  tagline: string;
  description: string;
  repo_url: string;
  trust: Trust;
  installed: boolean | null;
}

export interface HubCatalog {
  skills: HubSkillPack[];
  mcp: HubMcpServer[];
  knowledge: HubKnowledge[];
}

export interface RegistrySkill {
  source: string;
  skill: string;
  name: string;
  installs: number;
  ref: string;
  installed: boolean;
}
