# AgentForge: a multi-tenant multi-agent platform

AgentForge is a full-stack app for building, running and managing AI agents from a web dashboard or a REST API.

- **Agents, skills, tools and connectors** are reusable library items. They are never tied to a project. Each run happens inside an *(organization, project)*, and the agent receives that org's guidelines and keys, plus the project's brief, documents, memory and policies, when it runs.
- **Orchestration styles:** you can run single agents or teams. Teams can be sequential pipelines, parallel fan-out, a supervisor that delegates, a router, or a round-robin debate.
- **Workflows:** a visual DAG builder (React Flow) with agent, team, tool, LLM, condition, template and output nodes.
- **Scheduler:** runs can be triggered once at a set time, on a recurring schedule, on an interval, by a webhook, or manually. You can set one up by chatting with the scheduling assistant or with a form.
- **Browser use:** web search (DuckDuckGo with no key, or Tavily/Brave) and a browser tool that reads web pages. JavaScript rendering through Playwright is optional. Both can be switched on or off per agent and per project, with domain allow and block lists.
- **Discover (one-click installs):** a catalog of top skills (Anthropic and Vercel frontend design, diagram design, Karpathy guidelines, Cloudflare Zero Trust, cybersecurity playbooks, Browser Use, agentmemory, OpenViking), 10 popular MCP servers, a live search of the public skills.sh registry, and `find-skills`. Installs can be **attached to a project**, so every agent running there can use them.
- **Tasks:** to-dos per project. Turn any chat reply or pasted text into tasks, give them context, and hand a task to an agent. Agents get `create_tasks`, `list_tasks` and `update_task` tools.
- **Scheduler with AI:** describe a schedule in plain English ("every weekday at 9am summarise my open PRs") in one message or a short conversation, review the draft, then create it. Agents can also schedule runs from chat when you enable it.
- **Skills and `/commands`:** skills can be attached to an agent or to a single chat, or invoked for one message with a slash command. Twelve ready-made templates are included.
- **Knowledge:** you can attach documents (PDF, DOCX, MD, TXT, CSV, HTML or a URL) to an agent, a project or a whole org. Documents are searched with BM25. You can also *pin* a document so it is added to every prompt.
- **Memory:** each agent has private memory, and each project has memory shared by all its agents. The agent writes to it with the `memory` tool, and you can edit it in the UI.
- **Training:** the agent editor's **Train** tab lets you teach an agent in plain language, turn on **auto-learn** so it proposes lessons after each chat (and after every thumbs-down), approve or edit them in a review queue, and **distill** everything into a `<agent> playbook` skill. Approved lessons become agent memory and are always read by the agent.
- **App connectors:** GitHub, Slack, Notion, Linear, Jira, any REST API, Telegram, Discord, email (SMTP), and **any remote MCP server**.
- **Model providers:** Anthropic Claude, OpenAI, Groq, Gemini, OpenRouter, DeepSeek, Mistral, Ollama, any OpenAI-compatible endpoint, and an **offline mock model** so the whole app works without API keys.
- **Multi-org and multi-project:** RBAC roles are owner, admin, member and viewer. There are also API keys, encrypted secrets and an audit log.
- **Security:** rate limiting, brute-force lockout, an SSRF-hardened HTTP client, sandboxed templates, strict security headers, body size limits, tenant isolation checks, per-org token budgets and concurrency limits.
- **Responsive UI:** the dashboard works on phones (drawer navigation and bottom sheets) and supports light and dark themes.

```
MultiAgent/
├── backend/            FastAPI + async SQLAlchemy (SQLite by default, Postgres-ready)
│   ├── app/
│   │   ├── main.py     app, middleware, lifespan (DB init, seed, scheduler); routers come from app/modules
│   │   ├── core/       shared plumbing: config, db, auth deps, security, rate limiting, generic CRUD, seed
│   │   ├── engine/     agent runtime kernel: LLM providers, tool framework, run context, SSRF-safe net
│   │   └── modules/    one folder per feature (models.py, schemas.py, router.py, service.py, ...)
│   │       ├── auth/ orgs/ projects/
│   │       ├── agents/ skills/ tools/ teams/ workflows/ connectors/ discover/
│   │       ├── knowledge/ training/        documents, memory, lessons
│   │       ├── chat/ runs/ scheduler/ tasks/
│   │       └── dashboard/ transfer/
│   └── tests/          end-to-end tests using the mock model
├── frontend/           React 19 + Vite + Tailwind v4 + React Query + React Flow
│   └── src/
│       ├── App.tsx      composes every module's routes
│       ├── shared/      ui primitives, layout (shell, palette), api client, auth, hooks
│       └── modules/     one folder per feature, mirroring the backend: index.tsx (routes, nav,
│                        commands), api.ts (data hooks), types.ts, pages. Listed in modules/registry.ts
├── .agents/            project-level skills, MCP configs and reference lists for the agents that work on this repo (see .agents/README.md)
├── Dockerfile          single image: API + built SPA
├── docker-compose.yml  app + Postgres + Redis
├── startup.sh          one-command launcher (dev / prod / docker / test / doctor …)
└── multiagent.md       architecture & design notes
```

## Quick start

```bash
cd MultiAgent
./startup.sh            # installs everything on first run, then starts API :8000 + UI :5173
```

Open http://localhost:5173 and create an account. The **first user becomes the platform admin**, and only that user can edit the global library. Without any API key, agents use the mock model so every feature can still be tried. To use a real model, add a key under **Settings → Models**, which applies to that org only, or set it in `backend/.env` to apply server-wide.

### `startup.sh` commands

| Command | What it does |
|---|---|
| `./startup.sh` or `./startup.sh dev` | Starts the API with auto-reload and the UI with hot reload. |
| `./startup.sh prod` | Builds the UI and serves the UI and API from one server in production mode. It creates `SECRET_KEY` if it is missing, reusing your development key. |
| `./startup.sh docker` | Runs `docker compose up --build`: the app, Postgres and Redis-backed rate limits on :8000. |
| `./startup.sh setup` | Installs or updates dependencies only. |
| `./startup.sh test` | Runs the backend tests and the frontend type-check. |
| `./startup.sh doctor` | Checks Python (3.10+), Node (18+), ports, `.env`, model keys, Playwright and Docker. |
| `./startup.sh stop` / `logs` | Stops or follows servers started with `--detach`. |
| `./startup.sh reset` | Deletes the local development database (it asks first). |

The launcher finds a Python 3.10+ interpreter even when the default `python3` is older. It only re-installs dependencies when `requirements*.txt` or `package-lock.json` change, and it checks that ports are free before starting.

Options:
- `--api-port N` and `--ui-port N` change the ports.
- `--host 0.0.0.0` exposes the app on your LAN.
- `--detach` runs everything in the background.
- `--open` opens the browser.
- `--browser` installs Playwright and Chromium so the browser tool can render JavaScript.
- `-y` skips confirmation prompts.

<details><summary>Manual setup (without the launcher)</summary>

```bash
cd MultiAgent/backend
python3.10 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn app.main:app --reload --port 8000

cd ../frontend && npm install && npm run dev      # http://localhost:5173 (proxies /api -> :8000)
```
</details>

## Skills and slash commands

A **skill** is a reusable instruction pack: markdown instructions plus any tools it bundles. You can attach a skill in three ways:
- **To an agent**, so it is always active (agent editor → Capabilities & tools → Skills, or **New skill** right there).
- **To one chat**, so it applies to every message in that conversation (the **Skills** button in the chat header).
- **For a single message**, with its `/command`.

To give a skill a command, set **Slash command** in the skill editor (for example `research`). You can also add an **argument hint** and a **prompt template**. In the template, `{{ args }}` is the text typed after the command, and `{{ vars.x }}` and `{{ project.name }}` also work.

In chat, type `/` to open the command menu. Arrow keys move through it, and Enter or Tab picks a command. There are also built-in commands:

| Command | What it does |
|---|---|
| `/new` | Starts a new chat with the same agent. |
| `/skills` | Chooses skills for this chat. |
| `/help` | Lists every command. |

Commands are handled on the server, so they work everywhere: chat, `POST /api/runs` (`{"input": {"task": "/brief solar panels"}}`), schedules and webhooks. They work for teams too, where every member gets the skill. The run trace shows which skill a command applied.

**Templates:** the Skills page → **Templates** has 12 ready-made skills, each with its own command. They include `/summarize`, `/brief`, `/email`, `/translate`, `/codereview`, `/sql`, `/notes`, `/swot`, `/extract`, `/post`, `/eli5` and `/okrs`. You can also **import a SKILL.md** file, or **Install** one by pasting a command such as `npx skills add anthropics/skills --skill pdf`. The server downloads the SKILL.md from GitHub and never runs npx. The 6 starter skills come with `/research`, `/write`, `/calc`, `/docs`, `/review` and `/remember`.

## Discover: install skills, tools and connectors

Open **Discover** in the sidebar. With **Attach to project on install** on, whatever you install is added to the active project, so every agent that runs there can use it. You can also attach later under **Projects → Tools & connectors**.

- **Skills:** curated packs, plus a search box over the public [skills.sh](https://skills.sh) registry (most installed first). Each pack shows who publishes it: **Official** (the vendor), **Community** (read it before attaching) or **Built in**. Skills are copied as text and never executed.
- **Connectors (MCP):** one click for remote MCP servers such as DeepWiki, Context7, Exa, Cloudflare Docs, Hugging Face, Browser Use Cloud, GitHub, Stripe, Neon and Supabase. Servers that need a key ask for it and encrypt it. The connection is tested right away. GitHub, Slack, Notion, Linear, Jira, email and REST connectors are still on the **Connectors** page.
- **Knowledge:** reference lists that are not skills (for example awesome-harness-engineering) can be added to a project's knowledge, where agents search them.

Notes:
- "Anthropic-Cybersecurity-Skills" is a **community** project, not published by Anthropic. The catalog says so.
- MCP servers that only support OAuth sign-in, and servers on a private network (such as a local agentmemory), are not supported yet. Put a local server on a public HTTPS URL and add it as a custom MCP connector.
- Installing a pack downloads files straight from GitHub, which has no API limit. Searching a repo uses GitHub's API (60 requests an hour without a token). Set `GITHUB_TOKEN` in `backend/.env` to raise that to 5,000.
- Project-level skills share the prompt budget. If many large skills are attached, the first ~30,000 characters are loaded and the rest are listed by name for the agent to load with `use_skill`.

### Find Skills

`find_skills` and `use_skill` let an agent discover a skill and apply it to the current task. `find_skills` searches your installed skills, the curated catalog and the skills.sh registry. `use_skill` loads the best match for this run only: nothing is installed, and third-party text is labelled as such. Keeping a skill permanently is a deliberate action on the Discover page. They are on by default; switch them off per project under **Tools & connectors → Agent tools**. The built-in **Find Skills** skill (`/find-skills <need>`) teaches the playbook. It is adapted from the `find-skills` skill in `vercel-labs/skills`, which tells agents to run `npx` and so cannot work here.

## Agents and training

Every window is a page with its own URL; nothing important opens in a modal.

- **Agents** (`/agents`): create at `/agents/new` from a starting template. Each agent has its own sections: `/agents/:id` (overview, recent runs), `/profile`, `/instructions` (system-prompt editor with section snippets and a preview of how org/project context is layered), `/model`, `/tools` (capabilities, tools, connectors), `/skills`, `/knowledge` and `/settings` (duplicate, export, delete). All sections share one form with a single Save bar.
- **Training** (`/training`): pick an agent, then:
  - `/ingest`: drag-and-drop multi-file upload with progress, paste text, or import a URL.
  - `/teach`: rules, facts, Q&A examples and corrections.
  - `/review`: approve auto-learned lessons, or learn from your recent chats.
  - `/memory`: view and edit the agent's memories.
  - `/test`: see which chunks a question would retrieve.
  - `/settings`: auto-learn and distill a playbook skill.

  Project and organisation documents use `/training/ingest?owner_type=…`, and any document opens at `/training/documents/:id`.

## Tasks and the AI scheduler

**Tasks** (sidebar → Operate):
- Add a task by typing, or use **Text to tasks** on pasted text. In chat, the checklist button under an answer turns that reply into tasks. You review and edit what was found before anything is saved. Near-duplicates of open tasks are skipped.
- With a real model, extraction is done by the AI. With the offline mock model it falls back to rules (checklists, "Next steps" lists, imperative bullets, "need to / should" sentences).
- Every task carries **context** (what you typed plus the source text). **Run with agent** hands the task and its context to an agent.
- Agents in a project get `create_tasks`, `list_tasks` and `update_task`, on by default and switchable per project.

**Scheduler** (sidebar → Operate → Scheduler, `/scheduler`):
- **Schedule by chat** (`/scheduler/new/chat`): describe what should run and when, e.g. "every weekday at 9am ask Digest Writer to summarise my PRs" or "tomorrow at 3pm remind me to send the invoice". The assistant asks for anything missing (the task or the time), lets you change the agent or the time ("make it 10:30am instead"), shows a live draft, and creates the schedule when you say "yes". "Edit in form" hands the draft to the form.
- **Form** (`/scheduler/new/form`): pick a target and a trigger: **Once** (date and time in a timezone), **Recurring** (cron with presets), **Interval**, **Webhook** or **Manual**. A plain-English box can fill the form for you.
- **Upcoming** (`/scheduler/upcoming`): an agenda of every run the enabled schedules will start in the next 24 hours, 7 days or 30 days.
- Each schedule has its own page (`/scheduler/:id`) with an overview (next runs, webhook URL), `/edit` and `/runs` (its run history).
- The model only extracts the task, the time phrase and the agent. The schedule itself is built and checked by a deterministic parser, so a made-up cron expression or date can never reach the scheduler. The parser handles recurring phrases ("every monday and friday at 5:30pm", "every 2 hours", "monthly on the 15th") and one-time ones ("in 2 hours", "next friday", "on 2026-12-05 at 10:00") offline too. "On friday" means one day; "every friday" or "on fridays" repeats. Dates in the past are refused with an explanation.
- With **Scheduling** switched on for a project (off by default), an agent can create a schedule (recurring or one-time) when you ask for one in chat. Runs started by a schedule or webhook cannot create new schedules, and agents can create at most 25 per project.

## More features

- **⌘K / Ctrl+K command palette:** jump to any page, start a chat with any agent or team, open workflows and skills, switch project, or create something new.
- **Import / Export** (Settings → Import / Export): exports agents, teams, workflows, skills and custom tools as a JSON bundle, with dependencies resolved automatically. You can import a bundle into another org or another installation. Built-in tools are matched by key, connections and secrets are never exported, and imported items go through the same validation as the API.
- **Answer feedback:** each chat answer has 👍/👎 buttons and a copy button. Feedback is stored with the message.
- **Re-run:** the run page has a button that starts the same target with the same input again (`POST /api/runs/{id}/rerun`).
- **Automatic database upgrades:** new columns are added to existing databases at startup, so your data survives upgrades.

### Tests

```bash
./startup.sh test
```

There are 101 end-to-end tests. They cover:
- web search, context injection, knowledge and memory
- all 5 team styles, workflows with branching, chat, SSE and webhooks
- the scheduler, connectors and SSRF blocking
- tenant isolation, RBAC, API keys, brute-force lockout and input limits
- slash commands and templates, conversation skills, feedback, re-run, export/import between tenants, and the database auto-upgrade
- the Discover catalog, skill and MCP installs at project level, `find_skills` / `use_skill`, the skill prompt budget, and the GitHub token only going to `api.github.com`
- tasks (text to task, chat replies, context, running a task with an agent), the agent task tools, and the plain-English scheduler including rejection of invalid model output

## Using the API

Everything in the UI is also available over REST. The interactive docs are at `http://localhost:8000/docs` in development.

```bash
# create an org API key in Settings → API keys, then:
curl -X POST http://localhost:8000/api/runs \
  -H "Authorization: Bearer afk_..." -H "Content-Type: application/json" \
  -d '{"project_id":"prj_...","target_type":"agent","target_id":"agt_...","input":{"task":"Summarise the latest AI agent news"},"wait":true}'

# stream a run (Server-Sent Events: replay + live tokens)
curl -N http://localhost:8000/api/runs/run_.../stream -H "Authorization: Bearer afk_..."

# trigger a webhook schedule from anywhere
curl -X POST http://localhost:8000/api/hooks/whk_... -H "Content-Type: application/json" -d '{"ticket":"URGENT: checkout down"}'
```

Send `X-Org-Id: org_...` to pick the organization when you authenticate with a user token (JWT). An API key is already bound to its org.

## How context flows into an agent

When an agent runs, its system prompt is built in this order:

1. The agent's own instructions.
2. The operating context: org name, project name and today's date.
3. **Organization guidelines**, set in Settings → General.
4. **Project brief**: description, context and variables.
5. **Skills**: the agent's own, then the project's (every agent in the project gets these), then any chosen for this chat or command.
6. **Pinned documents** from the agent, the project and the org.
7. **Long-term memory**: recent project memory, plus agent memory if enabled.
8. Rules for tool use and safety, including that tool output is untrusted data.

The agent's tools are the union of:
- its own tools and the tools bundled with its skills
- the project's shared tools
- capability tools (browser, memory, knowledge, to-dos, find/use skills, and scheduling when enabled)
- tools from connections attached to the agent or the project, including MCP servers installed from Discover

Project policy is then applied, for example turning off web access or blocking specific tools.

See [multiagent.md](multiagent.md) for the full design.
