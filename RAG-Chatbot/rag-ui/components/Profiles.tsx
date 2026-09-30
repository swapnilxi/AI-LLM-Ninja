"use client";

import { useEffect, useState } from "react";
import { api, ApiError, profileUrl, Profile } from "@/lib/api";
import { Icon } from "./Icons";
import { Badge, Card, PageHeader, Spinner, useToast } from "./ui";

type Props = {
  profiles: Profile[];
  activeId: string;
  canEdit: boolean; // allow_ui_config
  canDeleteFiles: boolean; // allow_ui_upload
  creating: boolean; // open the create dialog immediately
  onCloseCreate: () => void;
  onSelect: (id: string) => void;
  onOpenDocuments: (id: string) => void;
  onChanged: () => void;
};

const ago = (t: number | null) => (t ? new Date(t * 1000).toLocaleString() : "never");

export default function Profiles(p: Props) {
  const toast = useToast();
  const [editing, setEditing] = useState<Profile | "new" | null>(null);
  useEffect(() => { if (p.creating) setEditing("new"); }, [p.creating]);

  const close = () => { setEditing(null); p.onCloseCreate(); };

  async function reindex(pr: Profile) {
    try {
      await api(profileUrl(pr.id, "/documents/reindex"), "POST");
      toast("info", `Re-indexing ${pr.name}…`);
      p.onChanged();
    } catch (e) { toast("bad", (e as Error).message); }
  }

  return (
    <div className="page">
      <PageHeader title="Profiles" subtitle={<>Each folder inside <code>data/</code> is one profile. Chat only searches the active profile{" "}plus the shared <b>Common</b> knowledge.</>}
        actions={p.canEdit && <button onClick={() => setEditing("new")}><Icon name="plus" size={15} />Create profile</button>} />

      <div className="profile-grid">
        {p.profiles.map((pr) => {
          const busy = pr.indexing?.state === "running";
          return (
            <Card key={pr.id} className={`profile-card ${pr.id === p.activeId ? "current" : ""}`}>
              <div className="profile-card-head">
                <Icon name={pr.is_common ? "layers" : "database"} size={18} />
                <h3>{pr.name}</h3>
                {pr.id === p.activeId && <Badge tone="info">active</Badge>}
                {pr.is_common && <Badge tone="muted">shared</Badge>}
                {pr.status === "missing" && <Badge tone="bad">folder missing</Badge>}
              </div>
              {pr.description && <p className="muted small">{pr.description}</p>}
              <div className="profile-stats">
                <span><b>{pr.stats.documents}</b> documents · <b>{pr.stats.indexed}</b> indexed</span>
                {pr.stats.pending > 0 && <Badge tone="warn">{pr.stats.pending} pending</Badge>}
                {pr.stats.failed > 0 && <Badge tone="bad">{pr.stats.failed} failed</Badge>}
                {busy && <span className="row"><Spinner size={12} /><span className="muted small">indexing…</span></span>}
              </div>
              <div className="muted small"><code>{pr.folder}</code> · last sync {ago(pr.last_sync_at)}</div>
              <div className="row wrap profile-actions">
                <button className="sm" onClick={() => p.onOpenDocuments(pr.id)}>Documents</button>
                {!pr.is_common && pr.id !== p.activeId && <button className="sm secondary" onClick={() => p.onSelect(pr.id)}>Use in chat</button>}
                <button className="sm secondary" onClick={() => setEditing(pr)}>{p.canEdit ? "Edit" : "Details"}</button>
                <button className="sm secondary" disabled={busy || pr.status === "missing"} onClick={() => reindex(pr)}>Re-index</button>
              </div>
            </Card>
          );
        })}
      </div>
      {p.profiles.length <= 1 && <div className="banner info"><Icon name="info" size={16} /><span>Create a profile (or add a folder inside <code>data/</code>) to start chatting with its documents.</span></div>}

      {editing && <ProfileDialog profile={editing === "new" ? null : editing} canEdit={p.canEdit} canDeleteFiles={p.canDeleteFiles}
        onClose={close} onSaved={(id) => { close(); p.onChanged(); if (id) p.onSelect(id); }} onDeleted={() => { close(); p.onChanged(); }} />}
    </div>
  );
}

function ProfileDialog({ profile, canEdit, canDeleteFiles, onClose, onSaved, onDeleted }: {
  profile: Profile | null; canEdit: boolean; canDeleteFiles: boolean;
  onClose: () => void; onSaved: (createdId?: string) => void; onDeleted: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(profile?.name ?? "");
  const [description, setDescription] = useState(profile?.description ?? "");
  const [instructions, setInstructions] = useState(profile?.instructions ?? "");
  const [includeCommon, setIncludeCommon] = useState(profile?.include_common ?? true);
  const [saving, setSaving] = useState(false);
  const [danger, setDanger] = useState(false);
  const [deleteFiles, setDeleteFiles] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  async function save() {
    setSaving(true);
    try {
      if (profile) {
        await api(profileUrl(profile.id), "PATCH", { name, description, instructions, include_common: includeCommon });
        toast("ok", "Profile saved");
        onSaved();
      } else {
        const created = await api<Profile>("/profiles", "POST", { name, description, instructions, include_common: includeCommon });
        toast("ok", `Profile created — folder ${created.folder}`);
        onSaved(created.id);
      }
    } catch (e) { toast("bad", e instanceof ApiError ? e.message : (e as Error).message); }
    finally { setSaving(false); }
  }

  async function remove() {
    if (!profile) return;
    try {
      const q = deleteFiles ? `?delete_files=true&confirm=${encodeURIComponent(confirmText)}` : "";
      await api(profileUrl(profile.id) + q, "DELETE");
      toast("ok", deleteFiles ? `${profile.name} and its files deleted` : `${profile.name} removed (files kept in ${profile.folder})`);
      onDeleted();
    } catch (e) { toast("bad", (e as Error).message); }
  }

  return (
    <>
      <div className="scrim light" onClick={onClose} />
      <div className="modal card" role="dialog" aria-label={profile ? `Edit ${profile.name}` : "Create profile"}>
        <div className="card-head">
          <h3>{profile ? profile.name : "Create profile"}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" size={16} /></button>
        </div>
        <div className="form">
          <label>Name
            <input value={name} onChange={(e) => setName(e.target.value)} disabled={!canEdit} placeholder="e.g. Acme" autoFocus />
            {!profile && name.trim() && <span className="muted small">Creates the folder <code>data/{name.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^[-_]+|[-_]+$/g, "")}</code></span>}
          </label>
          <label>Description
            <input value={description} onChange={(e) => setDescription(e.target.value)} disabled={!canEdit} placeholder="What this profile is for" />
          </label>
          <label>Instructions
            <textarea rows={5} value={instructions} onChange={(e) => setInstructions(e.target.value)} disabled={!canEdit}
              placeholder={profile?.is_common ? "Instructions applied to every profile…" : "Extra instructions for the assistant when this profile is active…"} />
            <span className="muted small">{profile?.is_common ? "Common instructions apply to all profiles." : "Added after the common instructions. Retrieved documents can never override them."}</span>
          </label>
          {!profile?.is_common && (
            <label className="check"><input type="checkbox" checked={includeCommon} onChange={(e) => setIncludeCommon(e.target.checked)} disabled={!canEdit} />
              Also search the shared Common knowledge base</label>
          )}
          {profile && <div className="muted small"><code>{profile.folder}</code> · {profile.stats.documents} documents, {profile.stats.indexed} indexed · last sync {ago(profile.last_sync_at)}</div>}
        </div>
        <div className="row modal-actions">
          {canEdit && <button onClick={save} disabled={saving || !name.trim()}>{saving ? <Spinner size={14} /> : profile ? "Save" : "Create"}</button>}
          <button className="secondary" onClick={onClose}>Cancel</button>
          {profile && !profile.is_common && canEdit && <button className="secondary danger" style={{ marginLeft: "auto" }} onClick={() => setDanger((d) => !d)}>Delete…</button>}
        </div>

        {danger && profile && (
          <div className="danger-zone">
            <b>Delete {profile.name}</b>
            <p className="small">This removes the profile and its vector index from the app. <b>Your files stay on disk</b> in <code>{profile.folder}</code> unless you also choose to delete them.</p>
            {canDeleteFiles && (
              <label className="check"><input type="checkbox" checked={deleteFiles} onChange={(e) => setDeleteFiles(e.target.checked)} />
                Also permanently delete all {profile.stats.documents} document(s) from the filesystem</label>
            )}
            {deleteFiles && (
              <label>Type <code>{profile.id}</code> to confirm
                <input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} placeholder={profile.id} />
              </label>
            )}
            <button className="secondary danger" onClick={remove} disabled={deleteFiles && confirmText !== profile.id}>
              {deleteFiles ? "Delete profile and files" : "Remove profile (keep files)"}
            </button>
          </div>
        )}
      </div>
    </>
  );
}
