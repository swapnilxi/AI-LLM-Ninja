/** Shared state for the agent workspace (`/agents/:id/*`): one form for every sub-page, loaded once in the layout. */
import { createContext, useContext } from "react";
import type { Agent, AgentSettings } from "./types";
import type { AgentForm } from "./form";

export interface AgentWorkspaceCtx {
  id: string;
  agent: Agent;
  form: AgentForm;
  setForm: (fn: (f: AgentForm) => AgentForm) => void;
  set: <K extends keyof AgentForm>(k: K, v: AgentForm[K]) => void;
  setSetting: (k: keyof AgentSettings, v: boolean) => void;
  dirty: boolean;
  readOnly: boolean;
  saving: boolean;
  save: () => Promise<Agent | undefined>;
  discard: () => void;
  /** Navigate outside the workspace; asks first when there are unsaved changes. */
  leave: (to: string) => void;
  /** Save pending changes (if any), then navigate. */
  saveThen: (to: string) => void;
  duplicate: () => void;
  duplicating: boolean;
}

export const AgentWorkspaceContext = createContext<AgentWorkspaceCtx | null>(null);

export function useAgentWorkspace(): AgentWorkspaceCtx {
  const v = useContext(AgentWorkspaceContext);
  if (!v) throw new Error("useAgentWorkspace must be used inside the agent workspace");
  return v;
}
