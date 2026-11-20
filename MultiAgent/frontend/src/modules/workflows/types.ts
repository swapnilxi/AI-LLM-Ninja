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
