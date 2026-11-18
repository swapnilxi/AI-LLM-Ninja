/** Shared building blocks for library pages (agents, skills, tools, teams, workflows). */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Building2, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge, Card } from "@/components/ui/primitives";

export function ScopeBadge({ orgId }: { orgId: string | null }) {
  return orgId === null ? (
    <Badge tone="primary" icon={<Globe className="size-2.5" />}>Global</Badge>
  ) : (
    <Badge tone="muted" icon={<Building2 className="size-2.5" />}>Org</Badge>
  );
}

/** Clickable card used in library grids. */
export function ResourceCard({ to, icon, title, subtitle, description, badges, footer, actions, className }: {
  to: string;
  icon: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
  badges?: ReactNode;
  footer?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("group relative flex flex-col transition-all hover:-translate-y-0.5 hover:border-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/5", className)}>
      <Link to={to} className="flex flex-1 flex-col p-4">
        <div className="flex items-start gap-3">
          {icon}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-sm font-semibold">{title}</h3>
            </div>
            {subtitle && <div className="mt-0.5 truncate text-xs text-muted">{subtitle}</div>}
          </div>
        </div>
        {description && <p className="mt-3 line-clamp-2 text-sm text-muted">{description}</p>}
        {badges && <div className="mt-3 flex flex-wrap gap-1.5">{badges}</div>}
        {footer && <div className="mt-auto pt-3 text-xs text-muted">{footer}</div>}
      </Link>
      {actions && <div className="absolute right-3 top-3 flex gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100">{actions}</div>}
    </Card>
  );
}

export function Grid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">{children}</div>;
}

/** Notice shown when viewing a read-only global item. */
export function GlobalNotice({ onDuplicate, busy }: { onDuplicate: () => void; busy?: boolean }) {
  return (
    <div className="mb-5 flex flex-col gap-3 rounded-xl border border-indigo-500/20 bg-gradient-to-r from-primary-soft to-transparent p-4 sm:flex-row sm:items-center">
      <Globe className="size-5 shrink-0 text-primary" />
      <div className="flex-1 text-sm">
        <span className="font-medium">Global library item.</span> <span className="text-muted">Shared with every organization and read-only here. Duplicate it to customize for your org.</span>
      </div>
      <button onClick={onDuplicate} disabled={busy} className="cursor-pointer rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60 dark:text-[#0b0d12]">
        Duplicate to my org
      </button>
    </div>
  );
}

/** Sticky bottom action bar for editors (mobile friendly). */
export function SaveBar({ children }: { children: ReactNode }) {
  return (
    <div className="surface-glass sticky bottom-0 z-10 -mx-4 mt-6 flex justify-end gap-2 border-t border-border px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      {children}
    </div>
  );
}
