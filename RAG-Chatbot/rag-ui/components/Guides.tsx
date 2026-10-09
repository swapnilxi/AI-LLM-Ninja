"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { analyzeGuides, GuideAnalysis, GuideAssessment, GuideItemSpec, GuideStatus, streamGuideExplain } from "@/lib/api";
import { Icon, IconName } from "./Icons";
import { Card, PageHeader, Spinner } from "./ui";

type Item = { id: string; title: string; detail: string };
type Tone = "muted" | "info" | "warn" | "bad" | "ok";
type Section = { id: string; icon: IconName; level: string; tone: Tone; title: string; blurb: string; items: Item[] };

const EXAMPLE_REPO = "https://github.com/jamwithai/production-agentic-rag-course";
const FURTHER_READING: { label: string; href: string }[] = [
  { label: "LangChain docs", href: "https://python.langchain.com/" },
  { label: "LlamaIndex docs", href: "https://docs.llamaindex.ai/" },
  { label: "RAGAS (evaluation) docs", href: "https://docs.ragas.io/" },
];

const SECTIONS: Section[] = [
  {
    id: "foundations",
    icon: "layers",
    level: "Foundations",
    tone: "muted",
    title: "1 · Get a basic pipeline working",
    blurb: "New to RAG? Start here. A correct, boring retrieve-then-generate loop beats a clever broken one — nail this before adding anything else.",
    items: [
      { id: "f1", title: "Chunk by structure, not just size", detail: "Split along natural boundaries (headings, paragraphs, Q&A pairs) with ~50–150 token overlap, so facts near a boundary aren't cut in half." },
      { id: "f2", title: "Match the embedding model to your content", detail: "General-purpose embeddings are fine for broad text; switch to a domain-specific or multilingual model if your corpus is jargon-heavy or not in English." },
      { id: "f3", title: "Carry metadata through every chunk", detail: "Store source file, section title, and last-updated date from day one — you'll need it later for filtering, citations, and freshness checks." },
      { id: "f4", title: "Master keyword search (BM25) first", detail: "Unlike tutorials that jump straight to vector search, follow the professional path: build solid search foundations with keyword matching, filtering, and relevance scoring before adding semantic embeddings." },
      { id: "f5", title: "Force the model to stay grounded", detail: "Instruct it explicitly to answer only from the retrieved context, and to say \"I don't know\" rather than guess when the context doesn't cover the question." },
      { id: "f6", title: "Always return citations", detail: "Surface the source chunk or document for every answer so users — and you, during debugging — can verify it's actually grounded." },
      { id: "f7", title: "Spot-check real examples before scaling", detail: "Before investing in automated evals or fancier retrieval, read 20–30 real question/answer pairs yourself. It catches obvious failures no framework will flag for you." },
    ],
  },
  {
    id: "retrieval",
    icon: "search",
    level: "Retrieval quality",
    tone: "info",
    title: "2 · Make retrieval actually reliable",
    blurb: "Most RAG quality problems are retrieval problems, not generation problems. This is where the biggest wins live.",
    items: [
      { id: "i1", title: "Add hybrid search (dense + sparse)", detail: "Combine vector similarity with keyword/BM25 search; exact terms like IDs, names, and error codes are often missed by embeddings alone." },
      { id: "i2", title: "Rerank before you truncate", detail: "Retrieve a wider candidate set (20–50) and rerank with a cross-encoder or dedicated reranker before cutting down to the top-k you send the model." },
      { id: "i3", title: "Rewrite conversational queries", detail: "Turn follow-ups like \"what about pricing?\" into a standalone search query using chat history before retrieval runs." },
      { id: "i4", title: "Use small-to-big (parent-child) retrieval", detail: "Embed small, precise chunks for matching, but return their larger parent section to the model so it has enough context to answer." },
      { id: "i5", title: "Filter by metadata before you search", detail: "Narrow by profile, document type, date range, or access level first, so similarity search runs over a relevant subset, not everything." },
      { id: "i6", title: "Diversify results with MMR", detail: "Maximal Marginal Relevance stops the top-k from being five near-duplicate chunks of the same paragraph." },
      { id: "i7", title: "Debug retrieval separately from generation", detail: "When an answer is wrong, first check what was actually retrieved. If the right chunk never showed up, no amount of prompt tweaking will fix it — the fix belongs in retrieval, not the prompt." },
    ],
  },
  {
    id: "modern",
    icon: "zap",
    level: "Modern techniques",
    tone: "warn",
    title: "3 · Adopt current best practice",
    blurb: "Techniques from the last couple of years that meaningfully move accuracy, latency, or cost — once the basics are solid.",
    items: [
      { id: "m1", title: "Add contextual retrieval", detail: "Prepend a short LLM-written summary of surrounding context to each chunk before embedding and indexing it — this alone meaningfully cuts retrieval misses on ambiguous chunks." },
      { id: "m2", title: "Try HyDE for hard queries", detail: "Have the model draft a hypothetical answer first, then embed and search with that instead of the raw question — it often matches the phrasing of real documents better." },
      { id: "m3", title: "Fuse multiple query reformulations", detail: "Generate a few rephrasings of the question, retrieve for each, and merge the rankings with reciprocal rank fusion (RAG-Fusion)." },
      { id: "m4", title: "Route structured questions to structured stores", detail: "Send table- or number-heavy questions to SQL or a structured index instead of forcing them through vector search." },
      { id: "m5", title: "Cache semantically similar queries", detail: "A semantic cache in front of retrieval cuts latency and cost on repeated or near-duplicate questions." },
      { id: "m6", title: "Evaluate with a real framework", detail: "Adopt RAGAS, TruLens, or DeepEval to score faithfulness, answer relevance, and context precision/recall — not just spot-checking by eye." },
      { id: "m7", title: "Index non-text content deliberately", detail: "Caption or describe images, diagrams, and tables (or use vision-capable embeddings) instead of silently dropping them from the corpus." },
      { id: "m8", title: "Benchmark embedding models on your own data", detail: "Embedding models rank differently depending on your domain, language, and query style. Measure retrieval quality on a handful of real queries before committing to one instead of picking by reputation alone." },
    ],
  },
  {
    id: "agentic",
    icon: "sparkles",
    level: "Agentic & advanced",
    tone: "bad",
    title: "4 · Make retrieval agentic",
    blurb: "Already have a working RAG pipeline? This is where it gets interesting. A fixed retrieve-then-generate loop hits a ceiling on hard questions — these patterns let the system decide, check, and iterate, the core of an agentic RAG project.",
    items: [
      { id: "a1", title: "Make retrieval a tool, not a fixed step", detail: "Give the model a search tool it calls on its own, deciding when to retrieve, how many times, and with what query — instead of a rigid retrieve-then-generate pipeline." },
      { id: "a2", title: "Grade retrieved context before answering", detail: "Add a step (Corrective RAG) that checks whether retrieved chunks actually answer the question; if not, rewrite the query, broaden the search, or fall back to another source." },
      { id: "a3", title: "Support multi-hop retrieval", detail: "For questions that need facts from several documents, let the agent retrieve, reason, and issue follow-up retrievals before producing a final answer." },
      { id: "a4", title: "Route queries across sources", detail: "Add a routing step that picks which index, profile, or tool (docs, FAQs, SQL, web) is relevant before retrieving, rather than searching everything every time." },
      { id: "a5", title: "Make retrieval conversation-aware", detail: "Fold prior turns into the retrieval query so pronouns and follow-ups resolve to the right documents." },
      { id: "a6", title: "Split planner, retriever, and synthesizer roles", detail: "For complex research-style tasks, give each stage its own narrower agent instead of one prompt trying to do everything at once." },
      { id: "a7", title: "Consider graph-augmented retrieval (GraphRAG)", detail: "When relationships between entities matter more than passage similarity — org structures, dependencies, processes — a knowledge graph can outperform pure vector search." },
      { id: "a8", title: "Cap iterations and cost per request", detail: "Give any agentic retrieval loop a hard limit on tool calls and a timeout, so a confused agent can't loop forever or run up API costs on a single request." },
      { id: "a9", title: "Add mobile & multi-channel access", detail: "Expand your agentic RAG (e.g., using LangGraph) to platforms like Telegram, enabling conversational AI access on any device with integrated decision-making." },
    ],
  },
  {
    id: "production",
    icon: "check",
    level: "Production-ready",
    tone: "ok",
    title: "5 · Ship it safely",
    blurb: "What separates a demo from something you can hand to real users without babysitting it.",
    items: [
      { id: "p1", title: "Log every retrieval, not just the answer", detail: "Record the query, retrieved chunk IDs, scores, and final answer so retrieval failures are debuggable after the fact, not just a bad vibe." },
      { id: "p2", title: "Guard against ungrounded answers", detail: "Flag or reject responses whose claims can't be traced back to a cited chunk." },
      { id: "p3", title: "Treat retrieved content as untrusted", detail: "Documents can contain text that looks like instructions; never let content pulled from the index override your system prompt or trigger actions." },
      { id: "p4", title: "Enforce access control at the query level", detail: "Apply per-user/per-profile permissions inside the vector query itself, not only in the UI layer." },
      { id: "p5", title: "Keep a golden regression set", detail: "Maintain a fixed set of Q&A pairs with known-good sources, and re-run it on every change to chunking, prompts, or models." },
      { id: "p6", title: "Re-index incrementally and track versions", detail: "Only re-embed changed files, and retire stale chunks when a document is updated or removed — don't rebuild everything from scratch each time." },
      { id: "p7", title: "Monitor cost, latency, and usage per query", detail: "Track tokens and response time per request so cost spikes or slowdowns get caught before users complain, and so you can see which questions are expensive to answer." },
      { id: "p8", title: "Adopt production monitoring & caching", detail: "Use Langfuse for comprehensive pipeline tracing and prompt monitoring, and implement Redis caching to optimize performance and reduce costs on repeated queries." },
    ],
  },
];

const GLOSSARY: { term: string; def: string }[] = [
  { term: "RAG (Retrieval-Augmented Generation)", def: "Answering questions by first retrieving relevant text from your own documents, then giving that text to an LLM as context — so it answers grounded in your data, not just its training knowledge." },
  { term: "Chunk", def: "A small piece of a document (a paragraph, section, or fixed-size slice) that gets embedded and stored separately, so retrieval can find just the relevant part of a long document." },
  { term: "Embedding", def: "A list of numbers (a vector) that represents the meaning of a piece of text, produced by an embedding model, so that similar meanings end up as similar numbers." },
  { term: "Vector store / vector database", def: "A database specialized in storing embeddings and finding the ones most similar to a query embedding (e.g. Chroma, Postgres with pgvector, Pinecone)." },
  { term: "Retrieval", def: "The step where the system searches the vector store (and/or a keyword index) for the chunks most relevant to the user's question." },
  { term: "Top-k", def: "The number of chunks retrieved and handed to the LLM as context — e.g. \"top-5\" means the 5 most relevant chunks." },
  { term: "Cosine similarity", def: "A common way to measure how similar two embeddings are, based on the angle between them — closer to 1 means more similar." },
  { term: "Hybrid search", def: "Combining vector (semantic) search with traditional keyword search, like BM25, so exact terms such as IDs or names aren't missed." },
  { term: "Reranking", def: "A second pass that re-scores a larger set of retrieved candidates with a more accurate (but slower) model, to put the truly best chunks first." },
  { term: "Grounding", def: "Making sure the model's answer is actually based on the retrieved context, not made up — the core goal of RAG." },
  { term: "Hallucination", def: "When a model states something confidently that isn't actually true or isn't supported by the provided context." },
  { term: "System prompt", def: "The instructions given to the LLM before the conversation starts, defining its role, rules, and how it should use the retrieved context." },
  { term: "Context window", def: "The maximum amount of text (measured in tokens) a model can consider at once, including the system prompt, retrieved chunks, history, and the question." },
  { term: "Agentic RAG", def: "A RAG system where the LLM decides on its own when and how to retrieve (and can take other actions), instead of following one fixed retrieve-then-answer pipeline every time." },
  { term: "Tool use / function calling", def: "Letting the LLM call predefined functions — like \"search documents\" or \"run SQL\" — as part of generating its answer, rather than only producing text." },
];

const ALL_ITEMS: GuideItemSpec[] = SECTIONS.flatMap((s) => s.items.map((i) => ({ id: i.id, title: i.title, detail: i.detail, section: s.level })));

const STATUS_TONE: Record<GuideStatus, Tone> = { done: "ok", partial: "warn", missing: "bad" };
const STATUS_LABEL: Record<GuideStatus, string> = { done: "Done", partial: "Partial", missing: "Missing" };

const LS_KEY = "rag.guides.checked";
const readChecked = (): Record<string, boolean> => { try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch { return {}; } };
const writeChecked = (v: Record<string, boolean>) => { try { localStorage.setItem(LS_KEY, JSON.stringify(v)); } catch {} };

/** Inline AI explain-and-follow-up panel for a single checklist item. Starts itself on mount. */
function ExplainPanel({ item, analysisNote }: { item: GuideItemSpec; analysisNote?: string }) {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const controllerRef = useRef<AbortController | null>(null);
  const started = useRef(false);

  const ask = async (question: string, priorHistory: { role: "user" | "assistant"; content: string }[]) => {
    setError("");
    setMessages((m) => [...m, ...(question ? [{ role: "user" as const, content: question }] : []), { role: "assistant" as const, content: "" }]);
    setLoading(true);
    const ctl = new AbortController();
    controllerRef.current = ctl;
    try {
      await streamGuideExplain(item, question, priorHistory, analysisNote || "", (t) => {
        setMessages((m) => {
          const next = [...m];
          next[next.length - 1] = { ...next[next.length - 1], content: next[next.length - 1].content + t };
          return next;
        });
      }, ctl.signal);
    } catch (e) {
      setError((e as Error).message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    ask("", []);
    return () => controllerRef.current?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    ask(q, messages);
  };

  return (
    <div className="guide-explain">
      {messages.map((m, i) => (
        <div key={i} className={`guide-explain-msg ${m.role}`}>
          {m.content || (loading && i === messages.length - 1 ? <span className="typing"><i /><i /><i /></span> : "")}
        </div>
      ))}
      {error && <div className="error small">{error}</div>}
      <div className="row guide-explain-input">
        <input placeholder="Ask a follow-up…" value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") send(); }} disabled={loading} />
        <button className="secondary sm" onClick={send} disabled={loading || !input.trim()} title="Send">
          <Icon name="send" size={14} />
        </button>
      </div>
    </div>
  );
}

export default function Guides() {
  const [checked, setChecked] = useState<Record<string, boolean>>(() => (typeof window === "undefined" ? {} : readChecked()));
  const [open, setOpen] = useState<Record<string, boolean>>({ foundations: true });
  const [repoUrl, setRepoUrl] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<GuideAnalysis | null>(null);
  const [explainOpen, setExplainOpen] = useState<Record<string, boolean>>({});
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const refs = useRef<Record<string, HTMLDetailsElement | null>>({});

  const toggleItem = (id: string) => setChecked((c) => { const n = { ...c, [id]: !c[id] }; writeChecked(n); return n; });
  const setSectionOpen = (id: string, v: boolean) => setOpen((o) => ({ ...o, [id]: v }));
  const jumpTo = (id: string) => {
    setSectionOpen(id, true);
    requestAnimationFrame(() => refs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  const toggleExplain = (id: string) => setExplainOpen((o) => ({ ...o, [id]: !o[id] }));

  const total = useMemo(() => SECTIONS.reduce((n, s) => n + s.items.length, 0), []);
  const done = useMemo(() => SECTIONS.reduce((n, s) => n + s.items.filter((i) => checked[i.id]).length, 0), [checked]);

  const runAnalysis = async () => {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeGuides(ALL_ITEMS, repoUrl);
      setAnalysis(result);
      setChecked((c) => {
        const n = { ...c };
        for (const [id, a] of Object.entries(result.items)) if (a.status === "done") n[id] = true;
        writeChecked(n);
        return n;
      });
    } catch (e) {
      setAnalyzeError((e as Error).message || "Analysis failed.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="page">
      <PageHeader title="Guides" subtitle="A best-practice checklist for RAG — from first principles to production-grade agentic systems, for new and experienced developers alike." />

      <Card className="hero">
        <div className="hero-top">
          <div>
            <h2>RAG maturity checklist</h2>
            <p className="muted">New to RAG? Start at Foundations and work down — each tier builds on the last. Already shipping a RAG app? Jump to Agentic &amp; Production, or run Analyze below to see exactly what's missing in your own code. {done} of {total} practices checked.</p>
          </div>
          {done > 0 && <button className="secondary" onClick={() => { setChecked({}); writeChecked({}); }}>Reset checklist</button>}
        </div>
        <div className="progress"><div style={{ width: `${total ? (done / total) * 100 : 0}%` }} /></div>
        <div className="row wrap guide-jump">
          {SECTIONS.map((s) => (
            <button key={s.id} className="chip" onClick={() => jumpTo(s.id)}>
              <Icon name={s.icon} size={14} />{s.level}
            </button>
          ))}
        </div>
      </Card>

      <details className="guide-section card" open={glossaryOpen} onToggle={(e) => setGlossaryOpen((e.target as HTMLDetailsElement).open)}>
        <summary className="guide-head">
          <span className="tile-icon guide-head-icon"><Icon name="help" size={18} /></span>
          <span className="guide-head-text">
            <span className="guide-head-title">Glossary — new to RAG? Start here</span>
            <span className="muted small">Plain-language definitions of the terms used throughout this checklist.</span>
          </span>
          <Icon name="right" size={16} className="guide-chevron" />
        </summary>
        <dl className="glossary-grid">
          {GLOSSARY.map((g) => (
            <div key={g.term} className="glossary-entry">
              <dt className="glossary-term">{g.term}</dt>
              <dd className="glossary-def muted small">{g.def}</dd>
            </div>
          ))}
        </dl>
      </details>

      <Card title="Analyze a codebase against this checklist" icon="cpu">
        <p className="muted small">Leave the field blank to analyze this app's own backend, or point it at a public GitHub repo. The AI marks every item below as done, partial, or missing, and suggests the highest-impact next steps.</p>
        <div className="row wrap" style={{ marginTop: 10 }}>
          <input className="guide-repo-input" placeholder="https://github.com/owner/repo (optional — blank = analyze this app)"
            value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} disabled={analyzing} />
          <button onClick={runAnalysis} disabled={analyzing}>
            {analyzing ? <Spinner size={14} /> : <Icon name="sparkles" size={15} />}
            {analyzing ? "Analyzing…" : "Analyze"}
          </button>
        </div>
        <button className="link sm" style={{ marginTop: 8 }} onClick={() => setRepoUrl(EXAMPLE_REPO)} disabled={analyzing}>
          Or try the example repo: jamwithai/production-agentic-rag-course
        </button>
        {analyzeError && <div className="error small">{analyzeError}</div>}
        {analysis && (
          <div className="guide-analysis-result">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b className="small">Reviewed: {analysis.target}</b>
              <span className="muted small">{analysis.files_reviewed.length} file(s) read</span>
            </div>
            <p>{analysis.summary}</p>
            {analysis.next_steps.length > 0 && (
              <>
                <div className="small muted">Highest-impact next steps:</div>
                <ol className="small">{analysis.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              </>
            )}
          </div>
        )}
      </Card>

      <Card title="Resources" icon="book">
        <p className="muted small">A full example worth reading end-to-end, plus official docs if you want to go deeper on any technique above — useful whether this is your first RAG build or your fifth.</p>
        <a className="guide-resource" href={EXAMPLE_REPO} target="_blank" rel="noreferrer">
          <Icon name="book" size={18} />
          <div>
            <div className="guide-resource-title">jamwithai / production-agentic-rag-course</div>
            <div className="muted small">An example project building a production-grade agentic RAG system — a good companion to the "Agentic &amp; advanced" and "Production-ready" tiers below.</div>
          </div>
          <Icon name="external" size={14} />
        </a>
        <div className="row wrap guide-reading-links">
          {FURTHER_READING.map((r) => (
            <a key={r.href} className="chip" href={r.href} target="_blank" rel="noreferrer">
              <Icon name="external" size={12} />{r.label}
            </a>
          ))}
        </div>
      </Card>

      {SECTIONS.map((s) => {
        const doneInSection = s.items.filter((i) => checked[i.id]).length;
        return (
          <details
            key={s.id}
            ref={(el) => { refs.current[s.id] = el; }}
            className="guide-section card"
            open={!!open[s.id]}
            onToggle={(e) => setSectionOpen(s.id, (e.target as HTMLDetailsElement).open)}
          >
            <summary className="guide-head">
              <span className="tile-icon guide-head-icon"><Icon name={s.icon} size={18} /></span>
              <span className="guide-head-text">
                <span className="guide-head-title">{s.title}</span>
                <span className="muted small">{s.blurb}</span>
              </span>
              <span className={`badge ${s.tone}`}>{s.level}</span>
              <span className="muted small guide-head-count">{doneInSection}/{s.items.length}</span>
              <Icon name="right" size={16} className="guide-chevron" />
            </summary>
            <ol className="guide-list">
              {s.items.map((item) => {
                const assessment: GuideAssessment | undefined = analysis?.items[item.id];
                const spec: GuideItemSpec = { id: item.id, title: item.title, detail: item.detail, section: s.level };
                return (
                  <li key={item.id} className="guide-item">
                    <div className="guide-item-row">
                      <label className="check-row">
                        <input type="checkbox" checked={!!checked[item.id]} onChange={() => toggleItem(item.id)} />
                        <div className="guide-item-body">
                          <div className="guide-item-title-row">
                            <div className="guide-item-title">{item.title}</div>
                            {assessment && <span className={`badge ${STATUS_TONE[assessment.status]}`}>{STATUS_LABEL[assessment.status]}</span>}
                          </div>
                          <div className="muted small">{item.detail}</div>
                          {assessment?.note && <div className="muted small guide-item-note"><Icon name="info" size={12} />{assessment.note}</div>}
                        </div>
                      </label>
                      <button className="icon-btn guide-ai-btn" title="Ask AI to explain this task" onClick={() => toggleExplain(item.id)}>
                        <Icon name="sparkles" size={15} />
                      </button>
                    </div>
                    {explainOpen[item.id] && <ExplainPanel item={spec} analysisNote={assessment?.note} />}
                  </li>
                );
              })}
            </ol>
          </details>
        );
      })}
    </div>
  );
}
