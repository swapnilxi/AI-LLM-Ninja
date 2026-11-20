/**
 * Module contract. Every feature lives in `src/modules/<name>/` and exposes one `index.tsx` built with
 * `defineModule`: its URLs (routes), its sidebar entries (nav) and its command-palette shortcuts (commands).
 * `src/modules/registry.ts` lists the modules; App, the sidebar and the palette are composed from it.
 */
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export type NavSection = "" | "Build" | "Operate" | "Workspace";
export const NAV_SECTIONS: NavSection[] = ["", "Build", "Operate", "Workspace"];

export interface NavEntry {
  to: string;
  label: string;
  icon: LucideIcon;
  section: NavSection;
  /** Sort order inside the section (lower first). */
  order: number;
  end?: boolean;
  keywords?: string;
}

export interface ModuleRoute {
  /** Path relative to the app root, e.g. "agents/:id". Omit with `index`. */
  path?: string;
  index?: boolean;
  element: ReactNode;
  /** Public routes render outside the authenticated shell (login, register). */
  public?: boolean;
}

export interface ModuleCommand {
  id: string;
  label: string;
  to: string;
  icon: LucideIcon;
  group?: "Go to" | "Create";
  keywords?: string;
}

export interface AppModule {
  id: string;
  routes: ModuleRoute[];
  nav?: NavEntry[];
  commands?: ModuleCommand[];
}

export const defineModule = (m: AppModule): AppModule => m;
