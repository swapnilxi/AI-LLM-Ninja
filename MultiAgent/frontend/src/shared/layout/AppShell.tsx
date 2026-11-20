import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Blocks, Building2, Check, ChevronsUpDown, FolderKanban, LogOut, Menu as MenuIcon, Moon, Plus, Search, Sun } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { NAV } from "@/modules/registry";
import { cn } from "@/shared/lib/utils";
import { Menu, MenuItem, Sheet } from "@/shared/ui/overlay";
import { useTheme } from "@/shared/hooks/useTheme";
import { withReturn } from "@/shared/hooks/useReturnTo";
import { CommandPalette, usePaletteShortcut } from "./CommandPalette";

function OrgSwitcher() {
  const { org, orgs, switchOrg } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  return (
    <Menu
      align="left"
      className="w-full"
      trigger={
        <button className="flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-surface-2">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand text-sm font-semibold text-white shadow-sm shadow-indigo-500/25">{org?.name?.[0]?.toUpperCase() ?? "?"}</div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold">{org?.name ?? "No organization"}</div>
            <div className="truncate text-[11px] capitalize text-muted">{org?.role}</div>
          </div>
          <ChevronsUpDown className="size-4 text-muted" />
        </button>
      }
    >
      {(close) => (
        <>
          <div className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-muted">Organizations</div>
          {orgs.map((o) => (
            <MenuItem
              key={o.id}
              icon={<Building2 className="size-4 text-muted" />}
              active={o.id === org?.id}
              onClick={() => {
                close();
                if (o.id !== org?.id) {
                  switchOrg(o.id);
                  nav("/");
                }
              }}
            >
              {o.name}
            </MenuItem>
          ))}
          <div className="my-1 border-t border-border" />
          <MenuItem
            icon={<Plus className="size-4" />}
            onClick={() => {
              close();
              nav(withReturn("/settings/organizations/new", loc.pathname + loc.search));
            }}
          >
            New organization
          </MenuItem>
        </>
      )}
    </Menu>
  );
}

export function ProjectSwitcher({ compact }: { compact?: boolean }) {
  const { projects, project, setProjectId } = useAuth();
  const nav = useNavigate();
  return (
    <Menu
      align="left"
      trigger={
        <button className={cn("flex max-w-[220px] cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-2.5 text-sm hover:bg-surface-2", compact ? "h-8" : "h-9")}>
          <FolderKanban className="size-4 shrink-0 text-primary" />
          <span className="truncate font-medium">{project?.name ?? "Select project"}</span>
          <ChevronsUpDown className="size-3.5 shrink-0 text-muted" />
        </button>
      }
    >
      {(close) => (
        <>
          <div className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-muted">Active project · runs use its context</div>
          <div className="max-h-72 overflow-y-auto">
            {projects.map((p) => (
              <MenuItem
                key={p.id}
                active={p.id === project?.id}
                icon={p.id === project?.id ? <Check className="size-4" /> : <span className="size-4" />}
                onClick={() => {
                  setProjectId(p.id);
                  close();
                }}
              >
                {p.name}
              </MenuItem>
            ))}
          </div>
          <div className="my-1 border-t border-border" />
          <MenuItem
            icon={<Blocks className="size-4" />}
            onClick={() => {
              close();
              nav("/projects");
            }}
          >
            Manage projects
          </MenuItem>
        </>
      )}
    </Menu>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 pb-2 pt-4">
        <img src="/favicon.svg" alt="" className="size-6" />
        <span className="text-[15px] font-semibold tracking-tight">AgentForge</span>
      </div>
      <div className="px-2 pb-2">
        <OrgSwitcher />
      </div>
      <nav className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {NAV.map((g) => (
          <div key={g.section} className="mt-3 first:mt-1">
            {g.section && <div className="px-2.5 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted">{g.section}</div>}
            {g.items.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                    isActive ? "bg-gradient-to-r from-primary-soft to-primary-soft/30 text-primary" : "text-muted hover:bg-surface-2 hover:text-fg",
                  )
                }
              >
                <it.icon className="size-4" />
                {it.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="border-t border-border p-2">
        <div className="flex items-center gap-2 rounded-lg px-2 py-1.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-semibold">{user?.name?.[0]?.toUpperCase()}</div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">{user?.name}</div>
            <div className="truncate text-[11px] text-muted">{user?.email}</div>
          </div>
          <button onClick={toggle} className="cursor-pointer rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Toggle theme">
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
          <button onClick={logout} className="cursor-pointer rounded-md p-1.5 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Sign out">
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppShell() {
  const [drawer, setDrawer] = useState(false);
  const [palette, setPalette] = useState(false);
  usePaletteShortcut(setPalette);
  const loc = useLocation();
  useEffect(() => setDrawer(false), [loc.pathname]);
  const fullBleed = /^\/(workflows\/[^/]+|chat)/.test(loc.pathname);

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside className="surface-glass hidden w-60 shrink-0 border-r border-border lg:block">
        <SidebarContent />
      </aside>
      <Sheet open={drawer} onClose={() => setDrawer(false)} side="left" width="w-[280px]">
        <SidebarContent onNavigate={() => setDrawer(false)} />
      </Sheet>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="surface-glass flex h-14 shrink-0 items-center gap-2 border-b border-border px-3 sm:px-4">
          <button onClick={() => setDrawer(true)} className="cursor-pointer rounded-lg p-2 text-muted hover:bg-surface-2 lg:hidden" aria-label="Open menu">
            <MenuIcon className="size-5" />
          </button>
          <div className="flex items-center gap-2 lg:hidden">
            <img src="/favicon.svg" alt="" className="size-6" />
          </div>
          <ProjectSwitcher />
          <div className="flex-1" />
          <button
            onClick={() => setPalette(true)}
            className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-2.5 text-sm text-muted hover:bg-surface-2 hover:text-fg sm:w-64"
            aria-label="Search and commands"
          >
            <Search className="size-4" />
            <span className="hidden flex-1 text-left sm:inline">Search or jump to…</span>
            <kbd className="hidden rounded border border-border px-1.5 text-[10px] sm:inline">⌘K</kbd>
          </button>
        </header>
        <main className={cn("min-h-0 flex-1", fullBleed ? "overflow-hidden" : "overflow-y-auto")}>
          <Outlet />
        </main>
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  );
}
