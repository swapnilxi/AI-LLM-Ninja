import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { InputField } from "@/modules/workflows/types";
import { Button, EmptyState, Field, Input, Select } from "@/shared/ui/primitives";

/**
 * Edits the input fields a workflow asks for when it runs. Rendered by the builder's nested route
 * /workflows/:id/inputs inside its side panel, so the unsaved graph stays in memory.
 */
export function InputFieldsPanel({ value, onApply, onClose, readOnly }: { value: InputField[]; onApply: (v: InputField[]) => void; onClose: () => void; readOnly?: boolean }) {
  const [rows, setRows] = useState<InputField[]>(() => value.map((f) => ({ ...f })));
  const set = (i: number, patch: Partial<InputField>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const clean = rows.map((r) => ({ ...r, name: r.name.trim().replace(/[^a-zA-Z0-9_]/g, "_") })).filter((r) => r.name);
  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        <div>
          <div className="text-sm font-semibold">Workflow inputs</div>
          <p className="mt-0.5 text-xs text-muted">
            Fields requested when the workflow runs (also used by automations and webhooks). Reference as <code className="font-mono">{"{{ input.<name> }}"}</code>.
          </p>
        </div>
        {rows.length === 0 && <EmptyState title="No inputs" description="Add a field such as “topic” or “ticket”." className="py-8" />}
        {rows.map((r, i) => (
          <div key={i} className="space-y-2 rounded-xl border border-border p-3">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Name">
                <Input disabled={readOnly} value={r.name} onChange={(e) => set(i, { name: e.target.value })} placeholder="name" className="font-mono text-xs" />
              </Field>
              <Field label="Label">
                <Input disabled={readOnly} value={r.label ?? ""} onChange={(e) => set(i, { label: e.target.value })} placeholder="Label" />
              </Field>
              <Field label="Type">
                <Select disabled={readOnly} value={r.type ?? "text"} onChange={(e) => set(i, { type: e.target.value as InputField["type"] })}>
                  <option value="text">Text</option>
                  <option value="textarea">Long text</option>
                  <option value="number">Number</option>
                </Select>
              </Field>
              <Field label="Default">
                <Input disabled={readOnly} value={r.default ?? ""} onChange={(e) => set(i, { default: e.target.value })} placeholder="Default" />
              </Field>
            </div>
            {!readOnly && (
              <div className="flex justify-end">
                <Button variant="ghost" size="sm" icon={<Trash2 className="size-3.5" />} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                  Remove
                </Button>
              </div>
            )}
          </div>
        ))}
        {!readOnly && (
          <Button variant="outline" size="sm" icon={<Plus className="size-3.5" />} onClick={() => setRows([...rows, { name: "", label: "", type: "text", default: "" }])}>
            Add field
          </Button>
        )}
      </div>
      <div className="flex shrink-0 justify-end gap-2 border-t border-border px-4 py-3">
        <Button variant="outline" size="sm" onClick={onClose}>
          {readOnly ? "Close" : "Cancel"}
        </Button>
        {!readOnly && (
          <Button size="sm" onClick={() => onApply(clean)}>
            Apply
          </Button>
        )}
      </div>
    </div>
  );
}
