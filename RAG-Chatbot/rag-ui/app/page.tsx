"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, AppStatus, getToken, Profile, Settings, setToken, SyncStatus } from "@/lib/api";
import { useChats } from "@/lib/chats";
import { applyAppearance } from "@/lib/theme";
import Agents from "@/components/Agents";
import Chat from "@/components/Chat";
import Documents from "@/components/Documents";
import FaqManager from "@/components/FaqManager";
import Guides from "@/components/Guides";
import Overview from "@/components/Overview";
import ProfileSwitcher from "@/components/ProfileSwitcher";
import Profiles from "@/components/Profiles";
import SettingsPanel from "@/components/SettingsPanel";
import Sidebar, { Health, View } from "@/components/Sidebar";
import { Icon } from "@/components/Icons";
import { ToastProvider } from "@/components/ui";

const VIEWS: View[] = ["overview", "chat", "documents", "faqs", "agents", "guides", "profiles", "settings"];
const pref = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const setPref = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch {} };

export default function Home() {
  const [view, setViewState] = useState<View>("chat");
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const chats = useChats();

  // live backend / database status (polled)
  const [be, setBe] = useState<boolean | null>(null);
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [config, setConfig] = useState<Settings | null>(null);
  const [authNeeded, setAuthNeeded] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [probing, setProbing] = useState(false);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileIdState] = useState("");
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [creating, setCreating] = useState(false);

  // restore layout preferences after mount
  useEffect(() => {
    const v = (location.hash.slice(1) || pref("rag.view")) as View;
    if (VIEWS.includes(v)) setViewState(v);
    setCollapsed(pref("rag.sidebar") === "collapsed");
    setProfileIdState(pref("rag.profile") ?? "");
    const onHash = () => { const h = location.hash.slice(1) as View; if (VIEWS.includes(h)) setViewState(h); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const setView = useCallback((v: View) => { setViewState(v); setPref("rag.view", v); history.replaceState(null, "", `#${v}`); }, []);
  const setProfileId = useCallback((id: string) => { setProfileIdState(id); setPref("rag.profile", id); }, []);
  const toggleCollapsed = () => setCollapsed((c) => { setPref("rag.sidebar", c ? "open" : "collapsed"); return !c; });

  useEffect(() => {
    applyAppearance(profileId);
  }, [profileId]);

  const probe = useCallback(async () => {
    setProbing(true);
    try {
      const h = await api<{ ok: boolean; auth_required?: boolean }>("/health");
      setBe(true);
      const [s, c, pr] = await Promise.allSettled([api<AppStatus>("/status"), api<{ values: Settings }>("/config"), api<{ profiles: Profile[]; sync: SyncStatus }>("/profiles")]);
      if (pr.status === "fulfilled") { setProfiles(pr.value.profiles); setSync(pr.value.sync); }
      if (s.status === "fulfilled") { setStatus(s.value); setAuthNeeded(false); }
      else {
        setStatus(null);
        if (s.reason instanceof ApiError && s.reason.status === 401) setAuthNeeded(true);
      }
      setConfig(c.status === "fulfilled" ? c.value.values : null);
      if (h.auth_required && !getToken()) setAuthNeeded(true);
    } catch {
      setBe(false);
      setStatus(null);
    } finally {
      setProbing(false);
    }
  }, []);

  useEffect(() => {
    probe();
    const t = setInterval(probe, sync?.state === "running" ? 1500 : 5000);
    return () => clearInterval(t);
  }, [probe, sync?.state]);

  // the active profile: remembered choice, else the first regular profile, else Common
  const profile = useMemo(
    () => {
      const usable = profiles.filter((p) => p.status === "active"); // a profile whose folder vanished can't be chatted with
      return usable.find((p) => p.id === profileId) ?? usable.find((p) => !p.is_common) ?? usable[0] ?? null;
    },
    [profiles, profileId],
  );
  const activeId = profile?.id ?? "";
  const pending = profile?.stats.pending ?? 0;

  // each profile has its own conversations: follow the active profile
  const { selectForProfile } = chats;
  useEffect(() => {
    if (activeId && chats.active && chats.active.profileId !== activeId) selectForProfile(activeId);
  }, [activeId, chats.active?.id, chats.active?.profileId]); // eslint-disable-line react-hooks/exhaustive-deps
  const profileChats = useMemo(() => chats.chats.filter((c) => c.profileId === activeId), [chats.chats, activeId]);
  const canEditConfig = status?.flags.allow_ui_config ?? true;
  const canUpload = status?.flags.allow_ui_upload ?? true;

  const health: Health = useMemo(() => ({
    be,
    db: be === null ? null : status ? status.store.ok : false,
    dbDetail: status?.store.ok ? `${status.store.backend} (${status.store.chunks ?? 0} chunks)` : status?.store.error ?? "",
    model: config ? `${config.llm_provider} · ${config.llm_model || "default"}` : "",
    syncing: sync?.state === "running",
    pending,
  }), [be, status, config, pending, sync?.state]);

  return (
    <ToastProvider>
      <div className={`shell ${collapsed ? "is-collapsed" : ""}`}>
        <Sidebar
          view={view} onView={setView}
          chats={profileChats} activeChatId={chats.activeId} profileName={profile?.name ?? "—"}
          profiles={profiles} activeProfileId={activeId} onSelectProfile={setProfileId}
          onCreateProfile={() => { setCreating(true); setView("profiles"); }} onManageProfiles={() => setView("profiles")}
          onSelectChat={chats.setActiveId} onNewChat={() => activeId && chats.create(activeId)} onDeleteChat={chats.remove}
          health={health} probing={probing} onProbe={probe}
          signedIn={!!getToken()} onSignOut={() => { setToken(""); location.reload(); }}
          open={drawer} onClose={() => setDrawer(false)}
          collapsed={collapsed} onToggleCollapsed={toggleCollapsed}
        />

        <div className="main">
          <div className="topbar">
            <div className="topbar-left">
              <button className="icon-btn" onClick={() => setDrawer(true)} aria-label="Open menu"><Icon name="menu" size={20} /></button>
              <strong className="topbar-title">{view === "chat" ? (chats.active?.title || "RAG Chat") : view === "faqs" ? "FAQs" : view[0].toUpperCase() + view.slice(1)}</strong>
            </div>

            <div className="header-status-badges">
              {profile && (
                <ProfileSwitcher profiles={profiles} activeId={activeId} onSelect={setProfileId}
                  onCreate={() => { setCreating(true); setView("profiles"); }} onManage={() => setView("profiles")} />
              )}
              <span
                className={`status-pill ${be === null ? "checking" : be ? "online" : "offline"}`}
                title={be ? "Backend API is online and responding" : "Backend is offline (start with ./startup.sh or uvicorn)"}
              >
                <span className="dot" />
                <span>BE {be === null ? "…" : be ? "Online" : "Offline"}</span>
              </span>

              <span
                className={`status-pill ${health.db === null ? "checking" : health.db ? "online" : "offline"}`}
                title={health.dbDetail ? `Vector DB: ${health.dbDetail}` : health.db ? "Vector database connected" : "Vector database offline"}
              >
                <span className="dot" />
                <span>DB {health.db === null ? "…" : health.db ? "Online" : "Offline"}</span>
              </span>

              <button
                type="button"
                className={`icon-btn ${probing ? "spinning" : ""}`}
                onClick={probe}
                title="Refresh connection status"
              >
                <Icon name="refresh" size={13} />
              </button>
            </div>
          </div>

          {be === false && (
            <div className="banner bad">
              <Icon name="alert" size={16} />
              <span><strong>Backend is offline.</strong> Start it with <code>./startup.sh</code> — chat, sync and settings need it.</span>
              <button onClick={probe}>Retry</button>
            </div>
          )}
          {authNeeded && (
            <div className="banner info">
              <Icon name="key" size={16} />
              <span><strong>API token required.</strong> This server has ADMIN_TOKEN set.</span>
              <input type="password" placeholder="ADMIN_TOKEN" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { setToken(tokenInput); probe(); } }} />
              <button onClick={() => { setToken(tokenInput); probe(); }}>Save token</button>
            </div>
          )}

          <div className="content">
            {/* Chat stays mounted so a streaming answer survives switching tabs */}
            <div className="view" hidden={view !== "chat"}>
              {chats.active && profile && chats.active.profileId === activeId && (
                <Chat chat={chats.active} onChange={(fn) => chats.update(chats.active!.id, fn)} onNavigate={setView} config={config} storeChunks={status?.store.chunks ?? null} profile={profile} />
              )}
              {be && !profile && <div className="empty"><h2>No profiles yet</h2><p className="muted">Create a profile to start chatting with its documents.</p><button onClick={() => { setCreating(true); setView("profiles"); }}>Create profile</button></div>}
            </div>
            {view === "overview" && <div className="view scroll"><Overview status={status} config={config} profile={profile} onNavigate={setView} onRefresh={probe} /></div>}
            {view === "documents" && <div className="view scroll">{profile ? <Documents profile={profile} sync={sync} canEdit={canUpload} onChanged={probe} /> : <div className="empty"><p className="muted">No profile selected.</p></div>}</div>}
            {view === "faqs" && <div className="view scroll">{profile ? <FaqManager profile={profile} sync={sync} canEdit={canUpload} onChanged={probe} /> : <div className="empty"><p className="muted">No profile selected.</p></div>}</div>}
            {view === "agents" && <div className="view scroll"><Agents profiles={profiles} activeId={activeId} onChanged={probe} /></div>}
            {view === "guides" && <div className="view scroll"><Guides /></div>}
            {view === "profiles" && (
              <div className="view scroll">
                <Profiles profiles={profiles} activeId={activeId} canEdit={canEditConfig} canDeleteFiles={canUpload} creating={creating}
                  onCloseCreate={() => setCreating(false)} onSelect={setProfileId}
                  onOpenDocuments={(id) => { setProfileId(id); setView("documents"); }} onChanged={probe} />
              </div>
            )}
            {view === "settings" && (
              <div className="view scroll">
                <SettingsPanel onSaved={probe} profile={profile} profiles={profiles} onProfileChange={setProfileId} />
              </div>
            )}
          </div>
        </div>
      </div>
    </ToastProvider>
  );
}
