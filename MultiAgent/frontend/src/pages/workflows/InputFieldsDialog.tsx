import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { InputField } from "@/lib/types";
import { Dialog } from "@/components/ui/overlay";
import { Button, EmptyState, Input, Select } from "@/components/ui/primitives";

/** Edit the input fields a workflow asks for when it runs. */
export function InputFieldsDialog({ open, onClose, value, onChange, readOnly }: { open: boolean; onClose: () => void; value: InputField[]; onChange: (v: InputField[]) => void; readOnly?: boolean }) {
  const [rows, setRows] = useState<InputField[]>(value);
  useEffect(() => {
    if (open) setRows(value.map((f) => ({ ...f })));
  }, [open, value]);
  const set = (i: number, patch: Partial<InputField>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const clean = rows.map((r) => ({ ...r, name: r.name.trim().replace(/[^a-zA-Z0-9_]/g, "_") })).filter((r) => r.name);
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Workflow inputs"
      description="Fields requested when the workflow runs (also used by automations and webhooks). Reference as {{ input.<name> }}."
      size="lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          {!readOnly && (
            <Button
              onClick={() => {
                onChange(clean);
                onClose();
              }}
            >
              Apply
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-3">
        {rows.length === 0 && <EmptyState title="No inputs" description="Add a field such as “topic” or “ticket”." className="py-8" />}
        {rows.map((r, i) => (
          <div key={i} className="grid grid-cols-2 gap-2 rounded-xl border border-border p-3 sm:grid-cols-[1fr_1fr_120px_1fr_auto]">
            <Input disabled={readOnly} value={r.name} onChange={(e) => set(i, { name: e.target.value })} placeholder="name" className="font-mono text-xs" />
            <Input disabled={readOnly} value={r.label ?? ""} onChange={(e) => set(i, { label: e.target.value })} placeholder="Label" />
            <Select disabled={readOnly} value={r.type ?? "text"} onChange={(e) => set(i, { type: e.target.value as InputField["type"] })}>
              <option value="text">Text</option>
              <option value="textarea">Long text</option>
              <option value="number">Number</option>
            </Select>
            <Input disabled={readOnly} value={r.default ?? ""} onChange={(e) => set(i, { default: e.target.value })} placeholder="Default" />
            {!readOnly && (
              <Button variant="ghost" size="icon" onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label="Remove field" className="justify-self-end">
                <Trash2 className="size-4 text-muted" />
              </Button>
            )}
          </div>
        ))}
        {!readOnly && (
          <Button variant="outline" size="sm" icon={<Plus className="size-3.5" />} onClick={() => setRows([...rows, { name: "", label: "", type: "text", default: "" }])}>
            Add field
          </Button>
        )}
      </div>
    </Dialog>
  );
}
