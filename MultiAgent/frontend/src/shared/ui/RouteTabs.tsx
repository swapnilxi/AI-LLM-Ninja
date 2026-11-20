/** Tabs backed by URLs: each tab is a route, so every section is linkable and survives reloads. */
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/shared/lib/utils";

export interface RouteTab {
  to: string;
  label: ReactNode;
  icon?: LucideIcon;
  count?: number;
  /** Match the path exactly (use for an index tab). */
  end?: boolean;
}

export function RouteTabs({ tabs, className }: { tabs: RouteTab[]; className?: string }) {
  return (
    <nav className={cn("-mx-1 flex gap-1 overflow-x-auto border-b border-border px-1", className)} aria-label="Sections">
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            cn(
              "relative -mb-px flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              isActive ? "border-primary text-fg" : "border-transparent text-muted hover:text-fg",
            )
          }
        >
          {t.icon && <t.icon className="size-4" />}
          {t.label}
          {t.count !== undefined && <span className="rounded bg-surface-2 px-1.5 text-[11px] text-muted">{t.count}</span>}
        </NavLink>
      ))}
    </nav>
  );
}
