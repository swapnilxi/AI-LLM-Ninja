/** Agent form model shared by the create page and the agent workspace. */
import type { Effort } from "@/shared/lib/types";
import type { ProviderInfo } from "@/modules/settings/types";
import type { Agent, AgentSettings } from "./types";

export type AgentForm = {
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
};

export const EMPTY_FORM: AgentForm = {
  name: "",
  description: "",
  avatar: "bot",
  color: "indigo",
  provider: "default",
  model: "",
  system_prompt: "",
  temperature: null,
  max_tokens: 8000,
  max_steps: 8,
  effort: "medium",
  tool_ids: [],
  skill_ids: [],
  connection_ids: [],
  settings: { knowledge_enabled: true },
  tags: [],
};

export const EFFORTS: { value: Effort; label: string }[] = [
  { value: "low", label: "Low · fastest, cheapest" },
  { value: "medium", label: "Medium · balanced (default)" },
  { value: "high", label: "High · deeper reasoning" },
  { value: "xhigh", label: "Extra high · hard agentic tasks" },
  { value: "max", label: "Max · when correctness matters most" },
];

export function toForm(a: Agent): AgentForm {
  return {
    name: a.name,
    description: a.description,
    avatar: a.avatar || "bot",
    color: a.color || "indigo",
    provider: a.provider || "default",
    model: a.model,
    system_prompt: a.system_prompt,
    temperature: a.temperature,
    max_tokens: a.max_tokens,
    max_steps: a.max_steps,
    effort: a.effort,
    tool_ids: a.tool_ids ?? [],
    skill_ids: a.skill_ids ?? [],
    connection_ids: a.connection_ids ?? [],
    settings: a.settings ?? {},
    tags: a.tags ?? [],
  };
}

export const sameForm = (a: AgentForm | null, b: AgentForm | null) => JSON.stringify(a) === JSON.stringify(b);

/** Normalise the form into the API payload (drops fields the chosen provider ignores). */
export function toPayload(form: AgentForm, providers: { providers: ProviderInfo[]; default?: { provider: string; model: string } } | undefined) {
  const list = providers?.providers ?? [];
  const key = form.provider === "default" ? providers?.default?.provider : form.provider;
  const meta = list.find((p) => p.key === key);
  return {
    ...form,
    model: form.provider === "default" ? "" : form.model,
    temperature: meta?.supports_temperature ? form.temperature : null,
  };
}
