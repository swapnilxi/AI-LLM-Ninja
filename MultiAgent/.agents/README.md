# .agents

Project-level agent resources for AgentForge, using the same layout as the `npx skills` CLI (`.agents/skills/<name>/SKILL.md`), which is also how your home folder is set up (`~/.agents/skills`).

```
.agents/
├── skills/        17 skills, complete folders (SKILL.md plus references, scripts, assets)
├── references/    awesome-harness-engineering lists (reference reading, not skills)
├── mcp.json       5 MCP servers that need no key (ready to use)
├── mcp.keyed.json 5 MCP servers that need a key, with secrets as ${ENV_VAR} placeholders
├── sources.md     where every file came from: repo, commit, publisher trust, license
└── README.md      this file
```

## What is in `skills/`

| Skill | For |
|---|---|
| `find-skills` | Discover and install more skills. This is Vercel's original, which uses `npx skills find`, so it is meant for agents that can run a shell. |
| `frontend-design` | Distinctive, intentional UI (Anthropic) |
| `web-design-guidelines`, `vercel-react-best-practices`, `vercel-composition-patterns` | Web interface guidelines and React/Next.js practices (Vercel) |
| `diagram-design` | Branded diagrams as HTML/SVG. It is large (about 5.7 MB) because it ships 239 example files that it uses as templates. |
| `karpathy-guidelines` | Rules that curb common LLM coding mistakes (community, inspired by Karpathy) |
| `cloudflare-one` | Cloudflare Zero Trust (Cloudflare) |
| `detecting-ai-model-prompt-injection-attacks`, `defending-llms-with-guardrails`, `building-incident-response-playbook`, `deploying-cloudflare-access-for-zero-trust`, `continuous-llm-red-teaming-with-promptfoo` | Defensive security playbooks. Community project, **not published by Anthropic**. |
| `browser-use`, `open-source` | Browser control via the browser-use CLI, and writing code against its library |
| `agentmemory-mcp-tools`, `memory-discipline` | Playbooks for agents connected to an agentmemory server |

Details, licenses and pinned commits are in [sources.md](sources.md).

## Making an agent use them

Claude Code reads project skills from `.claude/skills/`, not from `.agents/`. Link them in (this mirrors what you already do in `~/.claude/skills`):

```bash
mkdir -p .claude/skills
for s in .agents/skills/*/; do n=$(basename "$s"); ln -sfn "../../.agents/skills/$n" ".claude/skills/$n"; done
```

Link only the ones you want if you prefer. Each linked skill adds its description to every session, and you already have a user-level `frontend-design`. Agents that follow the `.agents/skills` convention find the folder as it is.

## MCP servers

Both files use Claude Code's `.mcp.json` format.

- `mcp.json` has DeepWiki, Context7, Cloudflare Docs, Exa and Hugging Face. None needs a key, so you can copy it to the repo root as `.mcp.json` and use it straight away.
- `mcp.keyed.json` has Browser Use Cloud, GitHub, Stripe, Neon and Supabase. Merge in only the servers you want, and export their variables first (`BROWSER_USE_API_KEY`, `GITHUB_MCP_TOKEN`, `STRIPE_API_KEY`, `NEON_API_KEY`, `SUPABASE_ACCESS_TOKEN`). An unset variable can stop the whole config from loading, which is why these are kept apart.

These servers can change real data (GitHub, Stripe, Neon, Supabase), so use scoped or test credentials. Never put a real key in either file.

## How this relates to the AgentForge app

The app keeps its own skills in its database, so nothing here is picked up automatically. Install skills for the app's agents from **Discover**, which attaches them to a project. This folder is for the agents that work on this codebase.

## Adding OpenViking (not included, AGPL-3.0)

Its three skills (`openviking-memory`, `openviking-skills`, `ov-resources`) are under `agent-plugins/skills/` in `volcengine/OpenViking`. They also need an OpenViking server connected as an MCP server. If you accept AGPL-3.0 for those files:

```bash
npx skills add volcengine/OpenViking --skill openviking-memory openviking-skills ov-resources
```

## Review notes

- A skill is third-party text that steers an agent. Read the community ones before linking them.
- No script here is run by anything in this repository. They are only used if an agent follows a skill's instructions and you let it execute them.
- `deploying-cloudflare-access-for-zero-trust` documents `sudo` install steps for `cloudflared`. An agent following it to deploy would run them, so keep your approval prompts on.
- Total size is about 6 MB, almost all of it `diagram-design`.
