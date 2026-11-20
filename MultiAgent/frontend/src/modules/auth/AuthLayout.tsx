import type { ReactNode } from "react";
import { Bot, Plug, ShieldCheck, Workflow } from "lucide-react";

const FEATURES = [
  { icon: Bot, title: "Agents, skills & tools", text: "Build reusable agents once and run them in any project or organization." },
  { icon: Workflow, title: "Teams & workflows", text: "Pipelines, supervisors, routers, debates and visual DAG workflows." },
  { icon: Plug, title: "Connectors & browser", text: "Web search, a real browser, MCP servers, GitHub, Slack, Notion and more." },
  { icon: ShieldCheck, title: "Secure multi-tenant", text: "RBAC, encrypted secrets, rate limits, SSRF guards and audit logs." },
];

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-[#0d0f1a] p-12 text-white lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -right-40 -top-40 size-[520px] rounded-full bg-indigo-600/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-48 -left-24 size-[480px] rounded-full bg-violet-600/25 blur-3xl" />
        <div className="relative flex items-center gap-2.5">
          <img src="/favicon.svg" alt="" className="size-8" />
          <span className="text-lg font-semibold tracking-tight">AgentForge</span>
        </div>
        <div className="relative mt-auto max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            Orchestrate AI agents <span className="bg-gradient-to-r from-indigo-300 to-violet-300 bg-clip-text text-transparent">across every team and project.</span>
          </h2>
          <ul className="mt-8 space-y-5">
            {FEATURES.map((f) => (
              <li key={f.title} className="flex gap-3">
                <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-white/10 ring-1 ring-inset ring-white/15">
                  <f.icon className="size-4 text-indigo-200" />
                </div>
                <div>
                  <div className="text-sm font-medium">{f.title}</div>
                  <div className="text-sm text-white/60">{f.text}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <img src="/favicon.svg" alt="" className="size-7" />
            <span className="font-semibold tracking-tight">AgentForge</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
