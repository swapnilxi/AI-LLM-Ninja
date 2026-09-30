"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage } from "./api";

export type Chat = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
  /** the profile this conversation belongs to (chats never mix profiles) */
  profileId?: string;
  /** optional per-chat LLM override (empty = use the configured default) */
  provider?: string;
  model?: string;
  searchOnly?: boolean;
};

const KEY = "rag.chats.v1";
const ACTIVE = "rag.chats.active";
const MAX_CHATS = 50;

const newId = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
export const blankChat = (profileId?: string): Chat => ({ id: newId(), title: "New chat", createdAt: Date.now(), updatedAt: Date.now(), messages: [], profileId });

function read(): Chat[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}
function write(chats: Chat[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(chats.slice(0, MAX_CHATS)));
  } catch {} // storage full / blocked: chats simply stay in memory
}

/** Conversations kept in this browser's localStorage. Nothing about chats is sent to the server. */
export function useChats() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const ready = useRef(false);

  // read after mount (server render has no localStorage)
  useEffect(() => {
    const saved = read();
    const list = saved.length ? saved : [blankChat()];
    let active = "";
    try {
      active = localStorage.getItem(ACTIVE) || "";
    } catch {}
    setChats(list);
    setActiveId(list.some((c) => c.id === active) ? active : list[0].id);
    ready.current = true;
  }, []);

  useEffect(() => {
    if (ready.current) write(chats);
  }, [chats]);
  useEffect(() => {
    if (ready.current && activeId) {
      try {
        localStorage.setItem(ACTIVE, activeId);
      } catch {}
    }
  }, [activeId]);

  const update = useCallback((id: string, fn: (c: Chat) => Chat) => {
    setChats((cs) => cs.map((c) => (c.id === id ? { ...fn(c), updatedAt: Date.now() } : c)));
  }, []);

  const create = useCallback((profileId: string) => {
    // reuse an empty chat of this profile instead of piling up blank ones
    const empty = chats.find((c) => c.messages.length === 0 && c.profileId === profileId);
    if (empty) {
      setActiveId(empty.id);
      return empty.id;
    }
    const c = blankChat(profileId);
    setChats((cs) => [c, ...cs]);
    setActiveId(c.id);
    return c.id;
  }, [chats]);

  /** Switch to the most recent conversation of a profile (or start one). Legacy chats without a profile are adopted when empty. */
  const selectForProfile = useCallback((profileId: string) => {
    const mine = chats.filter((c) => c.profileId === profileId).sort((a, b) => b.updatedAt - a.updatedAt);
    if (mine[0]) return setActiveId(mine[0].id);
    const legacy = chats.find((c) => !c.profileId && c.messages.length === 0);
    if (legacy) {
      setChats((cs) => cs.map((c) => (c.id === legacy.id ? { ...c, profileId } : c)));
      return setActiveId(legacy.id);
    }
    const c = blankChat(profileId);
    setChats((cs) => [c, ...cs]);
    setActiveId(c.id);
  }, [chats]);

  const remove = useCallback(
    (id: string) => {
      const gone = chats.find((c) => c.id === id);
      const rest = chats.filter((c) => c.id !== id);
      const next = rest.find((c) => c.profileId === gone?.profileId) ?? blankChat(gone?.profileId);
      setChats(rest.includes(next) ? rest : [next, ...rest]);
      if (id === activeId) setActiveId(next.id);
    },
    [chats, activeId],
  );

  const active = chats.find((c) => c.id === activeId);
  return { chats, active, activeId, setActiveId, update, create, remove, selectForProfile, ready: ready.current && !!active };
}

export function chatToMarkdown(chat: Chat): string {
  const lines = [`# ${chat.title}`, `_Exported ${new Date().toLocaleString()}_`, ""];
  for (const m of chat.messages) {
    lines.push(m.role === "user" ? `## 🧑 ${m.content}` : m.content, "");
    if (m.sources?.length) {
      lines.push("**Sources**");
      for (const s of m.sources) lines.push(`- [${s.id}] ${s.scope === "common" ? "common/" : ""}${s.source}${s.page ? ` p.${s.page}` : ""} (${Math.round(s.score * 100)}% match)`);
      lines.push("");
    }
  }
  return lines.join("\n");
}
