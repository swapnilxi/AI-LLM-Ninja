/** Flat icon system (Lucide). Agents store an icon key + color; no emoji anywhere. */
import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Bot,
  Brain,
  Briefcase,
  Bug,
  Calculator,
  ChartColumn,
  Code,
  Compass,
  Cpu,
  Database,
  FileText,
  GitBranch,
  Globe,
  GraduationCap,
  Handshake,
  Headphones,
  HeartPulse,
  Landmark,
  Languages,
  Lightbulb,
  Mail,
  Megaphone,
  MessageCircle,
  MessageSquare,
  Microscope,
  Newspaper,
  Palette,
  PenLine,
  Plug,
  Rocket,
  Scale,
  ScanEye,
  Search,
  Send,
  Shield,
  ShoppingCart,
  Sparkles,
  SquareKanban,
  Target,
  Ticket,
  TrendingUp,
  WandSparkles,
  Zap,
} from "lucide-react";
import { cn } from "@/shared/lib/utils";

export const AGENT_ICONS: Record<string, LucideIcon> = {
  bot: Bot,
  search: Search,
  "pen-line": PenLine,
  "scan-eye": ScanEye,
  "chart-column": ChartColumn,
  brain: Brain,
  compass: Compass,
  sparkles: Sparkles,
  rocket: Rocket,
  shield: Shield,
  code: Code,
  database: Database,
  globe: Globe,
  mail: Mail,
  "message-square": MessageSquare,
  lightbulb: Lightbulb,
  briefcase: Briefcase,
  target: Target,
  "file-text": FileText,
  calculator: Calculator,
  headphones: Headphones,
  megaphone: Megaphone,
  "graduation-cap": GraduationCap,
  microscope: Microscope,
  scale: Scale,
  palette: Palette,
  zap: Zap,
  cpu: Cpu,
  "book-open": BookOpen,
  "wand-sparkles": WandSparkles,
  "trending-up": TrendingUp,
  "shopping-cart": ShoppingCart,
  newspaper: Newspaper,
  languages: Languages,
  bug: Bug,
  handshake: Handshake,
  landmark: Landmark,
  "heart-pulse": HeartPulse,
};

/** Soft gradient tiles per accent color (class names spelled out for Tailwind). */
export const ACCENTS: Record<string, { tile: string; dot: string }> = {
  indigo: { tile: "from-indigo-500/20 to-violet-500/10 text-indigo-600 ring-indigo-500/20 dark:text-indigo-300", dot: "bg-indigo-500" },
  sky: { tile: "from-sky-500/20 to-cyan-500/10 text-sky-600 ring-sky-500/20 dark:text-sky-300", dot: "bg-sky-500" },
  violet: { tile: "from-violet-500/20 to-fuchsia-500/10 text-violet-600 ring-violet-500/20 dark:text-violet-300", dot: "bg-violet-500" },
  emerald: { tile: "from-emerald-500/20 to-teal-500/10 text-emerald-600 ring-emerald-500/20 dark:text-emerald-300", dot: "bg-emerald-500" },
  amber: { tile: "from-amber-500/20 to-orange-500/10 text-amber-600 ring-amber-500/20 dark:text-amber-300", dot: "bg-amber-500" },
  rose: { tile: "from-rose-500/20 to-pink-500/10 text-rose-600 ring-rose-500/20 dark:text-rose-300", dot: "bg-rose-500" },
  teal: { tile: "from-teal-500/20 to-emerald-500/10 text-teal-600 ring-teal-500/20 dark:text-teal-300", dot: "bg-teal-500" },
  slate: { tile: "from-slate-500/20 to-slate-400/10 text-slate-600 ring-slate-500/20 dark:text-slate-300", dot: "bg-slate-500" },
};

export function AgentIcon({ name, className }: { name?: string; className?: string }) {
  const Icon = AGENT_ICONS[name ?? ""] ?? Bot;
  return <Icon className={className} />;
}

const SIZES = { xs: "size-6 rounded-md [&_svg]:size-3.5", sm: "size-8 rounded-lg [&_svg]:size-4", md: "size-10 rounded-xl [&_svg]:size-5", lg: "size-14 rounded-2xl [&_svg]:size-7" };

/** Gradient tile with a flat icon - used for agents, teams, workflows… */
export function IconTile({ icon, color = "indigo", size = "md", className }: { icon?: string | LucideIcon; color?: string; size?: keyof typeof SIZES; className?: string }) {
  const accent = ACCENTS[color] ?? ACCENTS.indigo;
  const Icon = typeof icon === "string" || icon === undefined ? AGENT_ICONS[icon ?? ""] ?? Bot : icon;
  return (
    <div className={cn("flex shrink-0 items-center justify-center bg-gradient-to-br ring-1 ring-inset", accent.tile, SIZES[size], className)}>
      <Icon strokeWidth={1.9} />
    </div>
  );
}

export const AgentAvatar = ({ agent, size = "md", className }: { agent?: { avatar?: string; color?: string } | null; size?: keyof typeof SIZES; className?: string }) => (
  <IconTile icon={agent?.avatar} color={agent?.color} size={size} className={className} />
);

const CONNECTOR_ICONS: Record<string, LucideIcon> = {
  github: GitBranch,
  slack: MessageSquare,
  notion: BookOpen,
  linear: SquareKanban,
  jira: Ticket,
  rest_api: Globe,
  telegram: Send,
  discord: MessageCircle,
  email: Mail,
  mcp: Plug,
};
const CONNECTOR_COLORS: Record<string, string> = {
  github: "slate", slack: "violet", notion: "slate", linear: "indigo", jira: "sky", rest_api: "teal", telegram: "sky", discord: "indigo", email: "amber", mcp: "emerald",
};

export function ConnectorIcon({ connectorKey, size = "md", className }: { connectorKey: string; size?: keyof typeof SIZES; className?: string }) {
  return <IconTile icon={CONNECTOR_ICONS[connectorKey] ?? Plug} color={CONNECTOR_COLORS[connectorKey] ?? "indigo"} size={size} className={className} />;
}

/** Icon + accent picker for agents. */
export function IconPicker({ icon, color, onChange }: { icon: string; color: string; onChange: (v: { icon: string; color: string }) => void }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {Object.entries(ACCENTS).map(([key, a]) => (
          <button
            key={key}
            type="button"
            onClick={() => onChange({ icon, color: key })}
            aria-label={key}
            className={cn("size-6 cursor-pointer rounded-full ring-offset-2 ring-offset-[var(--surface)] transition", a.dot, color === key ? "ring-2 ring-[var(--primary)]" : "opacity-70 hover:opacity-100")}
          />
        ))}
      </div>
      <div className="grid grid-cols-8 gap-1.5 sm:grid-cols-10">
        {Object.entries(AGENT_ICONS).map(([key, Icon]) => (
          <button
            key={key}
            type="button"
            title={key}
            onClick={() => onChange({ icon: key, color })}
            className={cn(
              "flex aspect-square cursor-pointer items-center justify-center rounded-lg border transition-colors",
              icon === key ? "border-primary bg-primary-soft text-primary" : "border-transparent text-muted hover:bg-surface-2 hover:text-fg",
            )}
          >
            <Icon className="size-4" strokeWidth={1.9} />
          </button>
        ))}
      </div>
    </div>
  );
}
