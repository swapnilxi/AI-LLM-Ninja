"use client";

import { useEffect, useState } from "react";
import type { Chat } from "@/lib/chats";
import { applyTheme, getTheme, Theme } from "@/lib/theme";
import { Icon, IconName } from "./Icons";
import { Spinner } from "./ui";

export type View = "overview" | "chat" | "documents" | "profiles" | "settings";
const NAV: { id: View; label: string; icon: IconName }[] = [
  { id: "overview", label: "Overview", icon: "grid" },
  { id: "chat", label: "Chat", icon: "chat" },
  { id: "documents", label: "Documents", icon: "doc" },
  { id: "profiles", label: "Profiles", icon: "database" },
  { id: "settings", label: "Settings", icon: "sliders" },
];

export type Health = {
  be: boolean | null;
  db: boolean | null;
  dbDetail: string;
  model: string; // "gemini · gemini-flash-latest"
  syncing: boolean;
  pending: number;
};

type Props = {
  view: View;
  onView: (v: View) => void;
  chats: Chat[];
  activeChatId: string;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  profileName: string;
  onDeleteChat: (id: string) => void;
  health: Health;
  probing: boolean;
  onProbe: () => void;
  signedIn: boolean;
  onSignOut: () => void;
  open: boolean; // mobile drawer
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
};

const dot = (v: boolean | null) => (v === null ? "checking" : v ? "online" : "offline");

export default function Sidebar(p: Props) {
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => setTheme(getTheme()), []);
  const pick = (t: Theme) => { setTheme(t); applyTheme(t); };

  const recent = [...p.chats].filter((c) => c.messages.length > 0).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 15);

  return (
    <>
      {p.open && <div className="scrim" onClick={p.onClose} />}
      <aside className={`sidebar ${p.collapsed ? "collapsed" : ""} ${p.open ? "open" : ""}`} aria-label="Main navigation">
        <div className="brand">
          <div className="logo"><Icon name="sparkles" size={18} /></div>
          <span className="brand-name">RAG Chat</span>
          <button className="icon-btn collapse-btn" onClick={p.onToggleCollapsed} title={p.collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            <Icon name={p.collapsed ? "right" : "left"} size={16} />
          </button>
          <button className="icon-btn close-btn" onClick={p.onClose} aria-label="Close menu"><Icon name="x" size={16} /></button>
        </div>

        <button className="new-chat" onClick={() => { p.onNewChat(); p.onView("chat"); p.onClose(); }} title="New chat">
          <Icon name="plus" size={16} /><span className="lbl">New chat</span>
        </button>

        <nav className="nav">
          {NAV.map((n) => (
            <button key={n.id} className={`nav-item ${p.view === n.id ? "active" : ""}`} title={n.label}
              onClick={() => { p.onView(n.id); p.onClose(); }}>
              <Icon name={n.icon} />
              <span className="lbl">{n.label}</span>
              {n.id === "documents" && p.health.pending > 0 && <span className="count" title="Files waiting to be indexed">{p.health.pending}</span>}
              {n.id === "documents" && p.health.syncing && <Spinner size={12} />}
            </button>
          ))}
        </nav>

        <div className="recent">
          <div className="recent-title lbl">Recent chats · {p.profileName}</div>
          {recent.length === 0 && <div className="muted small lbl recent-empty">Your conversations appear here.</div>}
          {recent.map((c) => (
            <div key={c.id} className={`recent-item ${c.id === p.activeChatId && p.view === "chat" ? "active" : ""}`}>
              <button className="recent-btn" title={c.title} onClick={() => { p.onSelectChat(c.id); p.onView("chat"); p.onClose(); }}>
                <Icon name="chat" size={14} /><span className="lbl">{c.title}</span>
              </button>
              <button className="icon-btn recent-del lbl" title="Delete chat" onClick={() => p.onDeleteChat(c.id)}><Icon name="trash" size={13} /></button>
            </div>
          ))}
        </div>

        <div className="side-foot">
          <div className="status-card" title={p.health.dbDetail ? `Vector DB: ${p.health.dbDetail}` : undefined}>
            <div className="status-row">
              <span className={`status-pill ${dot(p.health.be)}`}><span className="dot" /><span className="lbl">Backend {p.health.be === null ? "…" : p.health.be ? "online" : "offline"}</span></span>
              <button className={`icon-btn ${p.probing ? "spinning" : ""}`} onClick={p.onProbe} title="Refresh connection status"><Icon name="refresh" size={14} /></button>
            </div>
            <div className="status-row">
              <span className={`status-pill ${dot(p.health.db)}`}><span className="dot" /><span className="lbl">Vector DB {p.health.db === null ? "…" : p.health.db ? "online" : "offline"}</span></span>
            </div>
            {p.health.model && <div className="status-model lbl" title="Active LLM"><Icon name="cpu" size={13} />{p.health.model}</div>}
          </div>

          <div className="foot-row">
            <div className="theme-switch" role="group" aria-label="Theme">
              {(["light", "system", "dark"] as Theme[]).map((t) => (
                <button key={t} className={theme === t ? "active" : ""} onClick={() => pick(t)} title={`${t[0].toUpperCase()}${t.slice(1)} theme`}>
                  <Icon name={t === "light" ? "sun" : t === "dark" ? "moon" : "monitor"} size={14} />
                </button>
              ))}
            </div>
            {p.signedIn && <button className="icon-btn" onClick={p.onSignOut} title="Sign out (forget API token)"><Icon name="logout" size={16} /></button>}
          </div>
        </div>
      </aside>
    </>
  );
}
