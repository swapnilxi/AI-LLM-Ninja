export type TeamStyle = "sequential" | "parallel" | "supervisor" | "router" | "round_robin";

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
