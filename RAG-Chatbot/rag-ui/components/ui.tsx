"use client";

import { createContext, ReactNode, useCallback, useContext, useState } from "react";
import { Icon } from "./Icons";

export const Spinner = ({ size = 16, className = "" }: { size?: number; className?: string }) => {
  const s = size;
  return (
    <span
      className={`apple-spinner spinner ${className}`}
      style={{ width: s, height: s }}
      role="status"
      aria-label="Loading"
    >
      <svg viewBox="0 0 20 20" width={s} height={s} fill="currentColor">
        <rect x="9" y="1.5" width="2" height="4.5" rx="1" opacity="1.0" />
        <rect x="9" y="1.5" width="2" height="4.5" rx="1" opacity="0.875" transform="rotate(45 10 10)" />
        <rect x="9" y="1.5" width="2" height="4.5" rx="1" opacity="0.75" transform="rotate(90 10 10)" />
        <rect x="9" y="1.5" width="2" height="4.5" rx="1" opacity="0.625" transform="rotate(135 10 10)" />
        <rect x="9" y="1.5" width="2" height="4.5" rx="1" opacity="0.5" transform="rotate(180 10 10)" />
        <rect x="9" y="1.5" width="2" height="4.5" rx="1" opacity="0.375" transform="rotate(225 10 10)" />
        <rect x="9" y="1.5" width="2" height="4.5" rx="1" opacity="0.25" transform="rotate(270 10 10)" />
        <rect x="9" y="1.5" width="2" height="4.5" rx="1" opacity="0.125" transform="rotate(315 10 10)" />
      </svg>
    </span>
  );
};

export const Badge = ({ tone = "muted", children }: { tone?: "ok" | "warn" | "bad" | "info" | "muted"; children: ReactNode }) => (
  <span className={`badge ${tone}`}>{children}</span>
);

// ---- toasts: replace alert() with unobtrusive messages -----------------------------------------
type Toast = { id: number; kind: "ok" | "bad" | "info"; text: string };
const Ctx = createContext<(kind: Toast["kind"], text: string) => void>(() => {});
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "bad" ? 7000 : 3500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            <Icon name={t.kind === "ok" ? "check" : t.kind === "bad" ? "alert" : "info"} size={16} />
            <span>{t.text}</span>
            <button className="icon-btn" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))} aria-label="Dismiss"><Icon name="x" size={14} /></button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function Card({ title, icon, actions, children, className = "" }: {
  title?: ReactNode; icon?: Parameters<typeof Icon>[0]["name"]; actions?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          <h3>{icon && <Icon name={icon} size={16} />}{title}</h3>
          {actions && <div className="row">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}
