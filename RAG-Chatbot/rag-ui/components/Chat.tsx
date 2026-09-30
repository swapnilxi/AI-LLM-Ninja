"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ApiError, Catalog, ChatMessage, DocRow, Profile, profileUrl, queryContext, Settings, Source, streamChat } from "@/lib/api";
import { Chat as ChatT, chatToMarkdown } from "@/lib/chats";
import { citationLabel, kindOf, openDocument } from "@/utils/files";
import { Icon, fileIcon } from "./Icons";
import type { View } from "./Sidebar";
import { useToast } from "./ui";

type Props = {
  chat: ChatT;
  onChange: (fn: (c: ChatT) => ChatT) => void;
  onNavigate: (v: View) => void;
  config: Settings | null;
  storeChunks: number | null;
  profile: Profile; // the active profile: the only knowledge (plus Common) this chat may use
};

/** Group citations by where they came from (the active profile first, then Common), keeping their [n] numbers. */
function groupSources(sources: Source[]): [string, Source[]][] {
  const groups = new Map<string, Source[]>();
  for (const s of sources) {
    const label = s.scope === "common" ? "Common" : s.profile_name;
    groups.set(label, [...(groups.get(label) ?? []), s]);
  }
  return [...groups.entries()].sort(([a], [b]) => (a === "Common" ? 1 : 0) - (b === "Common" ? 1 : 0));
}

export default function Chat({ chat, onChange, onNavigate, config, storeChunks, profile }: Props) {
  const toast = useToast();
  const messages = chat.messages;
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [providers, setProviders] = useState<Record<string, string>>({});
  const [docNames, setDocNames] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [focus, setFocus] = useState<{ msg: number; n: number } | null>(null);
  const abort = useRef<AbortController | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api<Catalog>("/catalog").then((c) => setProviders(Object.fromEntries(Object.entries(c.llm).map(([id, p]) => [id, p.label])))).catch(() => {});
    api<{ documents: DocRow[] }>(profileUrl(profile.id, "/documents")).then((d) => setDocNames(d.documents.filter((f) => f.status === "INDEXED").map((f) => f.relative_path))).catch(() => setDocNames([]));
  }, [storeChunks, profile.id, profile.stats.indexed]);

  // keep the newest message in view unless the reader scrolled up
  useEffect(() => { if (stick.current) box.current?.scrollTo({ top: box.current.scrollHeight, behavior: "smooth" }); }, [messages]);
  useEffect(() => { setExpanded(new Set()); setFocus(null); stick.current = true; area.current?.focus(); }, [chat.id]);
  useEffect(() => {
    const el = area.current;
    if (el) { el.style.height = "auto"; el.style.height = `${Math.min(Math.max(el.scrollHeight, 30), 200)}px`; }  // min 30: scrollHeight is 0 while the tab is hidden
  }, [input]);

  const patchLast = (fn: (m: ChatMessage) => ChatMessage) =>
    onChange((c) => ({ ...c, messages: c.messages.map((m, i) => (i === c.messages.length - 1 ? fn(m) : m)) }));

  async function send(text: string, base: ChatMessage[] = messages) {
    const q = text.trim();
    if (!q || busy) return;
    const history = base.filter((m) => !m.error && !m.searchOnly);
    stick.current = true;
    onChange((c) => ({
      ...c,
      title: c.title === "New chat" ? q.slice(0, 48) : c.title,
      messages: [...base, { role: "user", content: q, at: Date.now() }, { role: "assistant", content: "", at: Date.now(), searchOnly: c.searchOnly }],
    }));
    setInput("");
    setBusy(true);
    abort.current = new AbortController();
    try {
      if (chat.searchOnly) {
        const r = await queryContext(profile.id, q);
        patchLast((m) => ({ ...m, sources: r.sources, content: r.sources.length ? `Found **${r.sources.length}** relevant passage(s). *(Search only — no LLM was used.)*` : "No relevant passages found." }));
        setExpanded((s) => new Set(s).add(base.length + 1));
      } else {
        await streamChat(profile.id, q, history, {
          sources: (sources) => patchLast((m) => ({ ...m, sources })),
          token: (t) => patchLast((m) => ({ ...m, content: m.content + t })),
        }, abort.current.signal, { provider: chat.provider, model: chat.model });
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        let errorMsg = (e as Error).message;
        if (errorMsg.includes("Failed to fetch") || errorMsg.includes("NetworkError") || errorMsg.includes("Load failed")) {
          errorMsg = "Backend is offline. Start the backend server (./startup.sh) to send messages.";
        }
        const hint = e instanceof ApiError && e.code === "index_mismatch" ? " Rebuild the index in Documents." : "";
        if (e instanceof ApiError && e.code === "profile_not_found") errorMsg = `Profile "${profile.name}" no longer exists. Pick another profile.`;
        patchLast((m) => ({ ...m, error: errorMsg + hint }));
      }
    } finally {
      setBusy(false);
    }
  }

  function regenerate() {
    const idx = messages.map((m) => m.role).lastIndexOf("user");
    if (idx >= 0 && !busy) send(messages[idx].content, messages.slice(0, idx));
  }

  const copy = (text: string) => navigator.clipboard.writeText(text).then(() => toast("ok", "Copied"), () => toast("bad", "Copy failed"));
  const exportMd = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([chatToMarkdown(chat)], { type: "text/markdown" }));
    a.download = `${chat.title.replace(/[^\w-]+/g, "_") || "chat"}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  };

  const suggestions = useMemo(() => {
    const s: string[] = [];
    if (docNames[0]) s.push(`Summarize ${docNames[0]}`);
    s.push(`What topics do the ${profile.name} documents cover?`, "List the key facts, with sources");
    if (docNames[1]) s.push(`What does ${docNames[1]} say about its main topic?`);
    return s.slice(0, 4);
  }, [docNames, profile.name]);

  const defaultLabel = config ? `Default (${config.llm_provider})` : "Default";
  const lastIdx = messages.length - 1;

  return (
    <div className="chat">
      <div className="chat-head">
        <div className="row" style={{ marginLeft: "auto" }}>  {/* the title itself is shown in the top bar */}
          {chat.provider && <span className="badge info">{chat.provider}{chat.model ? ` · ${chat.model}` : ""}</span>}
          <button className="icon-btn" title="Export as Markdown" disabled={!messages.length} onClick={exportMd}><Icon name="download" size={16} /></button>
          <button className="icon-btn" title="Clear this chat" disabled={!messages.length || busy} onClick={() => onChange((c) => ({ ...c, messages: [], title: "New chat" }))}><Icon name="trash" size={16} /></button>
        </div>
      </div>

      <div className="messages" ref={box} onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}>
        <div className="messages-inner">
          {messages.length === 0 && (
            <div className="empty">
              <div className="empty-logo"><Icon name="sparkles" size={26} /></div>
              <h2>Ask {profile.name} anything</h2>
              <p className="muted">Answers use only <b>{profile.name}</b>{profile.include_common && !profile.is_common ? " and the shared Common documents" : ""}, and cite their sources.</p>
              {profile.stats.indexed === 0 && (
                <div className="banner info inline"><Icon name="info" size={16} /><span>{profile.name} has no indexed documents yet.</span><button onClick={() => onNavigate("documents")}>Add documents</button></div>
              )}
              <div className="suggest">
                {suggestions.map((s) => (
                  <button key={s} className="suggest-card" onClick={() => send(s)}><Icon name="sparkles" size={14} /><span>{s}</span></button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => {
            const isLast = i === lastIdx;
            const streaming = busy && isLast && m.role === "assistant";
            const md = m.content.replace(/\[(\d{1,2})\](?!\()/g, "[$1](#cite-$1)"); // [1] -> clickable citation chip
            return (
              <div key={i} className={`msg ${m.role}`}>
                {m.role === "assistant" && <div className="avatar"><Icon name="sparkles" size={15} /></div>}
                <div className="msg-body">
                  <div className="bubble">
                    {m.role === "user" ? m.content : (
                      <>
                        {m.content ? (
                          <div className="md">
                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
                              a: ({ href, children }) => href?.startsWith("#cite-")
                                ? <button className="cite" onClick={() => { const n = Number(href.slice(6)); setExpanded((s) => new Set(s).add(i)); setFocus({ msg: i, n }); }}>{children}</button>
                                : <a href={href} target="_blank" rel="noreferrer">{children}</a>,
                            }}>{md}</ReactMarkdown>
                          </div>
                        ) : streaming && !m.error ? <span className="typing"><i /><i /><i /></span> : null}
                        {m.error && <div className="error-box"><Icon name="alert" size={15} /><span>{m.error}</span></div>}
                      </>
                    )}
                  </div>

                  {m.role === "assistant" && !streaming && (m.content || m.error) && (
                    <div className="msg-actions">
                      <button className="icon-btn" title="Copy" onClick={() => copy(m.content)}><Icon name="copy" size={14} /></button>
                      {isLast && <button className="icon-btn" title="Regenerate" onClick={regenerate}><Icon name="refresh" size={14} /></button>}
                    </div>
                  )}

                  {m.sources && m.sources.length > 0 && (
                    <div className="sources">
                      <button className="sources-toggle" onClick={() => setExpanded((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; })}>
                        <Icon name="layers" size={14} />{m.sources.length} source{m.sources.length > 1 ? "s" : ""}
                        <Icon name="right" size={12} style={{ transform: expanded.has(i) ? "rotate(90deg)" : undefined }} />
                      </button>
                      {expanded.has(i) && (
                        <div className="source-list">
                          {groupSources(m.sources).map(([group, list]) => (
                            <div key={group} className="source-group">
                              <div className="source-group-title">{group}</div>
                              {list.map((s: Source) => (
                                <div key={s.id} className={`source-card ${focus?.msg === i && focus.n === s.id ? "focus" : ""}`}
                                  ref={(el) => { if (el && focus?.msg === i && focus.n === s.id) el.scrollIntoView({ block: "nearest", behavior: "smooth" }); }}>
                                  <div className="source-head">
                                    <span className="cite static">{s.id}</span>
                                    <Icon name={fileIcon(s.source)} size={14} />
                                    <button className="link source-name" title="Open the source document"
                                      onClick={() => openDocument({ profileId: s.profile_id, documentId: s.document_id, name: s.source }, s.page).catch((e) => toast("bad", e.message))}>{citationLabel(s.source, s.page)}</button>
                                    <span className="badge muted">{kindOf(s.source)?.label ?? "file"}</span>
                                    <span className="score" title={`${(s.score * 100).toFixed(1)}% similarity`}><span style={{ width: `${Math.max(4, Math.min(100, s.score * 100))}%` }} /></span>
                                    <span className="muted small">{(s.score * 100).toFixed(0)}%</span>
                                  </div>
                                  <p>{s.text}</p>
                                </div>
                              ))}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {m.sources && m.sources.length === 0 && m.role === "assistant" && !streaming && <div className="muted small">No relevant sources found in your documents.</div>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="composer-wrap">
        <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
          <textarea ref={area} value={input} rows={1} placeholder={chat.searchOnly ? `Search ${profile.name}…` : `Ask about ${profile.name}…`}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(input); } }} />
          <div className="composer-bar">
            <div className="row wrap">
              <label className="chip-select" title="Which LLM answers in this chat">
                <Icon name="cpu" size={14} />
                <select value={chat.provider ?? ""} onChange={(e) => onChange((c) => ({ ...c, provider: e.target.value || undefined, model: "" }))} disabled={chat.searchOnly}>
                  <option value="">{defaultLabel}</option>
                  {Object.entries(providers).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
                </select>
              </label>
              {chat.provider && !chat.searchOnly && (
                <input className="chip-input" placeholder="model (optional)" value={chat.model ?? ""} onChange={(e) => onChange((c) => ({ ...c, model: e.target.value }))} />
              )}
              <button type="button" className={`chip ${chat.searchOnly ? "on" : ""}`} onClick={() => onChange((c) => ({ ...c, searchOnly: !c.searchOnly }))}
                title="Retrieve matching passages only — no LLM call, no API cost"><Icon name="search" size={14} />Search only</button>
            </div>
            {busy
              ? <button type="button" className="send stop" onClick={() => abort.current?.abort()} title="Stop generating"><Icon name="stop" size={15} /></button>
              : <button className="send" disabled={!input.trim()} title="Send (Enter)"><Icon name="send" size={16} /></button>}
          </div>
        </form>
        <div className="composer-hint muted small">Enter to send · Shift+Enter for a new line · answers can be wrong — check the sources</div>
      </div>
    </div>
  );
}
