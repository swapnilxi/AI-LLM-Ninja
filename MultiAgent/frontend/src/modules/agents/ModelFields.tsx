/** Provider / model / sampling fields, shared by the create page and the Model tab. */
import { useId } from "react";
import type { Effort } from "@/shared/lib/types";
import { useProviders } from "@/modules/settings/api";
import { Button, Field, Input, Select } from "@/shared/ui/primitives";
import { EFFORTS, type AgentForm } from "./form";

type ModelPart = Pick<AgentForm, "provider" | "model" | "effort" | "temperature" | "max_tokens" | "max_steps">;

export function ModelFields({ value, onChange, compact }: { value: ModelPart; onChange: (patch: Partial<ModelPart>) => void; compact?: boolean }) {
  const providers = useProviders();
  const listId = useId();
  const providerList = providers.data?.providers ?? [];
  const resolvedDefault = providers.data?.default;
  const effectiveKey = value.provider === "default" ? resolvedDefault?.provider : value.provider;
  const providerMeta = providerList.find((p) => p.key === effectiveKey);
  const selectedMeta = providerList.find((p) => p.key === value.provider);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field
        label="Provider"
        hint={
          value.provider === "default"
            ? resolvedDefault
              ? `Uses the organization default: ${resolvedDefault.provider} · ${resolvedDefault.model}`
              : "Uses the organization default model"
            : selectedMeta && !selectedMeta.configured
              ? "No API key configured yet - add one in Settings → Model providers."
              : undefined
        }
      >
        <Select value={value.provider} onChange={(e) => onChange({ provider: e.target.value, model: "" })}>
          <option value="default">Organization default</option>
          {providerList.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
              {p.configured ? "" : " (not configured)"}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Model" hint={value.provider === "default" ? "Set by the organization default." : "Pick a suggestion or type any model id."}>
        <Input
          list={listId}
          value={value.provider === "default" ? resolvedDefault?.model ?? "" : value.model}
          disabled={value.provider === "default"}
          onChange={(e) => onChange({ model: e.target.value })}
          placeholder={selectedMeta?.models[0] ?? "model-id"}
          className="font-mono text-xs"
        />
        <datalist id={listId}>
          {(selectedMeta?.models ?? []).map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>
      </Field>
      {!compact && (
        <>
          <Field label="Reasoning effort" hint="Controls thinking depth on models that support it (Claude, GPT-5 / o-series).">
            <Select value={value.effort} onChange={(e) => onChange({ effort: e.target.value as Effort })}>
              {EFFORTS.map((e) => (
                <option key={e.value} value={e.value}>
                  {e.label}
                </option>
              ))}
            </Select>
          </Field>
          {providerMeta?.supports_temperature ? (
            <Field label={`Temperature ${value.temperature === null ? "(model default)" : value.temperature.toFixed(1)}`} hint="Lower is more focused, higher is more creative.">
              <div className="flex h-9 items-center gap-3">
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  value={value.temperature ?? 0.7}
                  onChange={(e) => onChange({ temperature: Number(e.target.value) })}
                  className="w-full accent-[var(--primary)]"
                  aria-label="Temperature"
                />
                <Button size="sm" variant="ghost" onClick={() => onChange({ temperature: null })} disabled={value.temperature === null}>
                  Reset
                </Button>
              </div>
            </Field>
          ) : (
            <Field label="Temperature" hint="This provider manages sampling itself (not configurable).">
              <Input disabled value="Managed by model" />
            </Field>
          )}
          <Field label="Max output tokens" hint="Per model response (256 – 128,000).">
            <Input type="number" min={256} max={128000} value={value.max_tokens} onChange={(e) => onChange({ max_tokens: Number(e.target.value) })} />
          </Field>
          <Field label="Max steps" hint="Maximum model ↔ tool iterations per run (1 – 30).">
            <Input type="number" min={1} max={30} value={value.max_steps} onChange={(e) => onChange({ max_steps: Number(e.target.value) })} />
          </Field>
        </>
      )}
    </div>
  );
}
