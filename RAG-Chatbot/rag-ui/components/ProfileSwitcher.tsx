"use client";

import { useEffect, useRef, useState } from "react";
import type { Profile } from "@/lib/api";
import { Icon } from "./Icons";

/** Compact profile picker for the top bar: current profile + a menu to switch, create or manage. */
export default function ProfileSwitcher({ profiles, activeId, onSelect, onCreate, onManage }: {
  profiles: Profile[]; activeId: string; onSelect: (id: string) => void; onCreate: () => void; onManage: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const active = profiles.find((p) => p.id === activeId);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  const icon = (p: Profile) => (p.is_common ? "layers" : "database");
  return (
    <div className="profile-switch" ref={ref}>
      <button className="profile-btn" onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open} title="Active profile — chat only searches this profile's documents">
        <Icon name={active ? icon(active) : "database"} size={15} />
        <span className="profile-btn-name">{active?.name ?? "Select profile"}</span>
        <Icon name="right" size={12} style={{ transform: "rotate(90deg)" }} />
      </button>
      {open && (
        <div className="profile-menu" role="listbox">
          <div className="profile-menu-title">Profile</div>
          {profiles.map((p) => (
            <button key={p.id} role="option" aria-selected={p.id === activeId} className={`profile-opt ${p.id === activeId ? "active" : ""}`}
              onClick={() => { onSelect(p.id); setOpen(false); }}>
              <Icon name={icon(p)} size={15} />
              <span className="profile-opt-name">{p.name}</span>
              <span className="muted small">{p.stats.indexed}/{p.stats.documents}</span>
              {p.id === activeId && <Icon name="check" size={15} />}
            </button>
          ))}
          <div className="profile-menu-sep" />
          <button className="profile-opt" onClick={() => { setOpen(false); onCreate(); }}><Icon name="plus" size={15} /><span className="profile-opt-name">Create profile</span></button>
          <button className="profile-opt" onClick={() => { setOpen(false); onManage(); }}><Icon name="sliders" size={15} /><span className="profile-opt-name">Manage profiles</span></button>
        </div>
      )}
    </div>
  );
}
