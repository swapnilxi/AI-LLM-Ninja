import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Check, Copy, Plus, Search, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge, Button, Input, Textarea } from "./primitives";

export interface Option {
  value: string;
  label: string;
  description?: string;
  badge?: string;
  icon?: ReactNode;
}

/** Searchable checklist with selected chips. Works well on touch screens. */
export function MultiSelect({ options, value, onChange, placeholder = "Search…", emptyText = "Nothing to select", maxHeight = "max-h-64" }: {
  options: Option[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  emptyText?: string;
  maxHeight?: string;
}) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const s = q.toLowerCase();
    return options.filter((o) => !s || o.label.toLowerCase().includes(s) || o.description?.toLowerCase().includes(s));
  }, [options, q]);
  const selected = new Set(value);
  const toggle = (v: string) => onChange(selected.has(v) ? value.filter((x) => x !== v) : [...value, v]);
  const byValue = Object.fromEntries(options.map((o) => [o.value, o]));
  return (
    <div className="rounded-lg border border-border bg-surface">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-border p-2">
          {value.map((v) => (
            <span key={v} className="inline-flex items-center gap-1 rounded-md bg-primary-soft px-2 py-0.5 text-xs font-medium text-primary">
              {byValue[v]?.label ?? v}
              <button onClick={() => toggle(v)} className="cursor-pointer opacity-70 hover:opacity-100" aria-label="Remove">
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {options.length > 6 && (
        <div className="relative border-b border-border">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} className="h-9 w-full bg-transparent pl-8 pr-3 text-sm focus:outline-none" />
        </div>
      )}
      <div className={cn("overflow-y-auto p-1", maxHeight)}>
        {filtered.length === 0 && <div className="px-3 py-4 text-center text-xs text-muted">{emptyText}</div>}
        {filtered.map((o) => (
          <button
            key={o.value}
            type="button"
            onClick={() => toggle(o.value)}
            className={cn("flex w-full cursor-pointer items-start gap-2.5 rounded-md px-2.5 py-2 text-left hover:bg-surface-2", selected.has(o.value) && "bg-primary-soft/60")}
          >
            <span className={cn("mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border", selected.has(o.value) ? "border-primary bg-primary text-primary-fg" : "border-border")}>
              {selected.has(o.value) && <Check className="size-3" />}
            </span>
            {o.icon}
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2 text-sm font-medium">
                <span className="truncate">{o.label}</span>
                {o.badge && <Badge tone="muted">{o.badge}</Badge>}
              </span>
              {o.description && <span className="line-clamp-2 text-xs text-muted">{o.description}</span>}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** Editable list of key/value pairs. */
export function KeyValueEditor({ value, onChange, keyPlaceholder = "key", valuePlaceholder = "value" }: { value: Record<string, any>; onChange: (v: Record<string, any>) => void; keyPlaceholder?: string; valuePlaceholder?: string }) {
  const [rows, setRows] = useState<[string, string][]>(() => Object.entries(value ?? {}).map(([k, v]) => [k, String(v)]));
  useEffect(() => {
    setRows(Object.entries(value ?? {}).map(([k, v]) => [k, String(v)]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(value)]);
  const commit = (next: [string, string][]) => {
    setRows(next);
    onChange(Object.fromEntries(next.filter(([k]) => k.trim()).map(([k, v]) => [k.trim(), v])));
  };
  return (
    <div className="space-y-2">
      {rows.map(([k, v], i) => (
        <div key={i} className="flex gap-2">
          <Input value={k} placeholder={keyPlaceholder} className="w-2/5 font-mono text-xs" onChange={(e) => commit(rows.map((r, j) => (j === i ? [e.target.value, r[1]] : r)))} />
          <Input value={v} placeholder={valuePlaceholder} className="flex-1" onChange={(e) => commit(rows.map((r, j) => (j === i ? [r[0], e.target.value] : r)))} />
          <Button variant="ghost" size="icon" onClick={() => commit(rows.filter((_, j) => j !== i))} aria-label="Remove">
            <Trash2 className="size-4 text-muted" />
          </Button>
        </div>
      ))}
      <Button variant="outline" size="sm" icon={<Plus className="size-3.5" />} onClick={() => setRows([...rows, ["", ""]])}>
        Add
      </Button>
    </div>
  );
}

/** Textarea that edits a JSON value and reports parse errors. */
export function JsonEditor({ value, onChange, rows = 8, placeholder }: { value: any; onChange: (v: any) => void; rows?: number; placeholder?: string }) {
  const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2));
  const [error, setError] = useState("");
  useEffect(() => {
    try {
      if (JSON.stringify(JSON.parse(text)) !== JSON.stringify(value)) setText(JSON.stringify(value ?? {}, null, 2));
    } catch {
      /* keep user's text while invalid */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(value)]);
  return (
    <div>
      <Textarea
        mono
        rows={rows}
        value={text}
        placeholder={placeholder}
        spellCheck={false}
        onChange={(e) => {
          setText(e.target.value);
          try {
            const parsed = e.target.value.trim() ? JSON.parse(e.target.value) : {};
            setError("");
            onChange(parsed);
          } catch (err) {
            setError((err as Error).message);
          }
        }}
        className={cn(error && "border-danger focus:ring-red-500/30")}
      />
      {error && <p className="mt-1 text-xs text-danger">Invalid JSON: {error}</p>}
    </div>
  );
}

/** Comma/enter separated tag list. */
export function TagInput({ value, onChange, placeholder = "Type and press Enter" }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const parts = draft.split(",").map((s) => s.trim()).filter(Boolean);
    if (parts.length) onChange(Array.from(new Set([...value, ...parts])));
    setDraft("");
  };
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-lg border border-border bg-surface px-2 py-1.5 focus-within:ring-2 focus-within:ring-[var(--ring)]">
      {value.map((t) => (
        <span key={t} className="inline-flex items-center gap-1 rounded-md bg-surface-2 px-2 py-0.5 text-xs">
          {t}
          <button onClick={() => onChange(value.filter((x) => x !== t))} className="cursor-pointer text-muted hover:text-fg" aria-label={`Remove ${t}`}>
            <X className="size-3" />
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            add();
          } else if (e.key === "Backspace" && !draft && value.length) onChange(value.slice(0, -1));
        }}
        onBlur={add}
        placeholder={value.length ? "" : placeholder}
        className="min-w-[120px] flex-1 bg-transparent text-sm focus:outline-none"
      />
    </div>
  );
}

export function CopyButton({ text, label, className }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      variant="outline"
      size={label ? "sm" : "icon"}
      className={className}
      icon={done ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          toast.error("Clipboard not available");
        }
      }}
      aria-label="Copy"
    >
      {label}
    </Button>
  );
}

export function SearchInput({ value, onChange, placeholder = "Search…", className }: { value: string; onChange: (v: string) => void; placeholder?: string; className?: string }) {
  return (
    <div className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted" />
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="pl-8" />
    </div>
  );
}
