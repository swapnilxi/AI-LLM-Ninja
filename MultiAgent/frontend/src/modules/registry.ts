/** Every feature module, in one place. Add a module here and its routes, sidebar entries and palette commands appear. */
import { NAV_SECTIONS, type AppModule, type NavEntry, type NavSection } from "@/shared/lib/modules";
import agents from "./agents";
import auth from "./auth";
import chat from "./chat";
import connectors from "./connectors";
import dashboard from "./dashboard";
import discover from "./discover";
import projects from "./projects";
import runs from "./runs";
import scheduler from "./scheduler";
import settings from "./settings";
import skills from "./skills";
import tasks from "./tasks";
import teams from "./teams";
import tools from "./tools";
import training from "./training";
import workflows from "./workflows";

export const MODULES: AppModule[] = [auth, dashboard, chat, agents, training, teams, workflows, skills, tools, connectors, discover, tasks, scheduler, runs, projects, settings];

export const NAV: { section: NavSection; items: NavEntry[] }[] = NAV_SECTIONS.map((section) => ({
  section,
  items: MODULES.flatMap((m) => m.nav ?? [])
    .filter((n) => n.section === section)
    .sort((a, b) => a.order - b.order),
})).filter((s) => s.items.length);
