import { Fragment, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileText, FlaskConical, Search } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { withReturn } from "@/shared/hooks/useReturnTo";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Select, Spinner } from "@/shared/ui/primitives";
import type { TabProps } from "../AgentTraining";
import { useKnowledgeSearch, useTraining } from "../api";

// Mirrors the backend tokenizer (knowledge/service.py) closely enough to highlight matched terms.
const STOP = new Set(
  "a an the and or but if of to in on for with by at from as is are was were be been it its this that these those i you he she we they them our your their my me do does did can could should would will shall may might not no what which who whom how when where why about into over than then so such there here also just".split(" "),
);
const terms = (q: string) => Array.from(new Set(q.toLowerCase().match(/[a-z0-9]+/g) ?? [])).filter((t) => t.length > 1 && !STOP.has(t));

function Highlight({ text, words }: { text: string; words: string[] }) {
  if (!words.length) return <>{text}</>;
  const re = new RegExp(`\\b(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`, "gi");
  const parts = text.split(re);
  return (
    <>
      {parts.map((p, i) => (i % 2 === 1 ? <mark key={i} className="rounded bg-amber-400/25 px-0.5 text-fg">{p}</mark> : <Fragment key={i}>{p}</Fragment>))}
    </>
  );
}

const SCOPE_TONE = { agent: "primary", project: "success", org: "muted" } as const;

export function TestTab({ agent }: TabProps) {
  const { projects, projectId } = useAuth();
  const overview = useTraining(agent.id);
  const nav = useNavigate();
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"agent" | "all">("agent");
  const [project, setProject] = useState<string>(projectId ?? "");
  const [topK, setTopK] = useState(10);
  const search = useKnowledgeSearch({ q, agent_id: agent.id, agent_only: scope === "agent" || undefined, project_id: scope === "all" ? project || undefined : undefined, top_k: topK });
  const words = useMemo(() => terms(q), [q]);
  const hits = search.data ?? [];
  const max = hits[0]?.score || 1;
  const here = `/training/${agent.id}/test`;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setQ(draft.trim());
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Knowledge playground" description="Ask what a user might ask. You see exactly the chunks knowledge_search would hand the agent, ranked by BM25 keyword relevance." />
        <form onSubmit={submit} className="space-y-3 p-3 sm:p-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <Input value={draft} maxLength={500} onChange={(e) => setDraft(e.target.value)} placeholder="e.g. How long do refunds take?" className="pl-9" autoFocus />
            </div>
            <Button type="submit" icon={<FlaskConical className="size-4" />} disabled={!draft.trim()} loading={search.isFetching}>Test retrieval</Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Search in">
              <Select value={scope} onChange={(e) => setScope(e.target.value as "agent" | "all")}>
                <option value="agent">This agent's documents only</option>
                <option value="all">Everything it can see (agent + project + org)</option>
              </Select>
            </Field>
            {scope === "all" && (
              <Field label="Project context">
                <Select value={project} onChange={(e) => setProject(e.target.value)}>
                  <option value="">No project (agent + org)</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </Select>
              </Field>
            )}
            <Field label="Results">
              <Select value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
                {[5, 10, 20, 50].map((n) => <option key={n} value={n}>Top {n}</option>)}
              </Select>
            </Field>
          </div>
        </form>
      </Card>

      {overview.data && overview.data.documents === 0 && scope === "agent" ? (
        <EmptyState
          icon={<FileText className="size-5" />}
          title="This agent has no documents yet"
          description="Ingest some files or text first, or switch to “Everything it can see” to include project and organization documents."
          action={<Button onClick={() => nav(`/training/${agent.id}/ingest`)}>Ingest documents</Button>}
        />
      ) : !q ? (
        <EmptyState icon={<Search className="size-5" />} title="Run a test query" description="Results show the document, chunk number and relevance score, with matched keywords highlighted." />
      ) : search.isLoading ? (
        <div className="flex justify-center py-10"><Spinner className="size-5" /></div>
      ) : search.isError ? (
        <EmptyState icon={<Search className="size-5" />} title="Search failed" description={String((search.error as Error)?.message ?? "")} />
      ) : !hits.length ? (
        <EmptyState
          icon={<Search className="size-5" />}
          title="No matching chunks"
          description={words.length ? "Retrieval matches keywords, so the agent would get nothing for this question. Try the words your documents use, or ingest a document that covers it." : "Use more specific words: very common words are ignored."}
        />
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-muted">{hits.length} chunk{hits.length === 1 ? "" : "s"} retrieved · keywords: {words.join(", ") || "none"}</div>
          {hits.map((h, i) => (
            <Card key={`${h.document_id}:${h.chunk}`} className="overflow-hidden">
              <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
                <span className="flex size-6 items-center justify-center rounded-md bg-surface-2 text-[11px] font-semibold tabular-nums text-muted">{i + 1}</span>
                <Link to={withReturn(`/training/documents/${h.document_id}`, here)} className="min-w-0 flex-1 truncate text-sm font-medium hover:text-primary">{h.title || "Untitled"}</Link>
                <Badge tone={SCOPE_TONE[h.scope] ?? "muted"}>{h.scope}</Badge>
                <span className="text-[11px] text-muted">chunk {h.chunk + 1}</span>
                <div className="flex items-center gap-1.5" title={`BM25 score ${h.score}`}>
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-2">
                    <div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500" style={{ width: `${Math.max(6, Math.round((h.score / max) * 100))}%` }} />
                  </div>
                  <span className="w-10 text-right text-[11px] tabular-nums text-muted">{h.score.toFixed(2)}</span>
                </div>
              </div>
              <p className="max-h-60 overflow-y-auto whitespace-pre-wrap break-words px-4 py-3 text-sm leading-relaxed">
                <Highlight text={h.text} words={words} />
              </p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
