# AgentForge: a multi-tenant multi-agent platform

AgentForge is a full-stack app for building, running and managing AI agents from a web dashboard or a REST API.

- **Agents, skills, tools and connectors** are reusable library items. They are never tied to a project. Each run happens inside an *(organization, project)*, and the agent receives that org's guidelines and keys, plus the project's brief, documents, memory and policies, when it runs.
- **Orchestration styles:** you can run single agents or teams. Teams can be sequential pipelines, parallel fan-out, a supervisor that delegates, a router, or a round-robin debate.
- **Workflows:** a visual DAG builder (React Flow) with agent, team, tool, LLM, condition, template and output nodes.
- **Automations:** runs can be triggered on a cron schedule, on an interval, by a webhook, or manually.
- **Browser use:** web search (DuckDuckGo with no key, or Tavily/Brave) and a browser tool that reads web pages. JavaScript rendering through Playwright is optional. Both can be switched on or off per agent and per project, with domain allow and block lists.
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
│   │   ├── api/        REST routers (auth, orgs, projects, library, connectors, knowledge, runs, chat, automations, dashboard, transfer)
│   │   ├── engine/     runtime: llm providers, tools, connectors, runner, orchestrator, workflow DAG, scheduler, SSRF-safe net
│   │   ├── models.py   tenancy + library + execution tables
│   │   └── main.py     app, middleware, lifespan (DB init, seed, scheduler)
│   └── tests/          end-to-end tests using the mock model
├── frontend/           React 19 + Vite + Tailwind v4 + React Query + React Flow
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

Commands are handled on the server, so they work everywhere: chat, `POST /api/runs` (`{"input": {"task": "/brief solar panels"}}`), automations and webhooks. They work for teams too, where every member gets the skill. The run trace shows which skill a command applied.

**Templates:** the Skills page → **Templates** has 12 ready-made skills, each with its own command. They include `/summarize`, `/brief`, `/email`, `/translate`, `/codereview`, `/sql`, `/notes`, `/swot`, `/extract`, `/post`, `/eli5` and `/okrs`. You can also **import a SKILL.md** file, or **Install** one by pasting a command such as `npx skills add anthropics/skills --skill pdf`. The server downloads the SKILL.md from GitHub and never runs npx. The 6 starter skills come with `/research`, `/write`, `/calc`, `/docs`, `/review` and `/remember`.

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

There are 33 end-to-end tests. They cover:
- web search, context injection, knowledge and memory
- all 5 team styles, workflows with branching, chat, SSE and webhooks
- the scheduler, connectors and SSRF blocking
- tenant isolation, RBAC, API keys, brute-force lockout and input limits
- slash commands and templates, conversation skills, feedback, re-run, export/import between tenants, and the database auto-upgrade

## Using the API

Everything in the UI is also available over REST. The interactive docs are at `http://localhost:8000/docs` in development.

```bash
# create an org API key in Settings → API keys, then:
curl -X POST http://localhost:8000/api/runs \
  -H "Authorization: Bearer afk_..." -H "Content-Type: application/json" \
  -d '{"project_id":"prj_...","target_type":"agent","target_id":"agt_...","input":{"task":"Summarise the latest AI agent news"},"wait":true}'

# stream a run (Server-Sent Events: replay + live tokens)
curl -N http://localhost:8000/api/runs/run_.../stream -H "Authorization: Bearer afk_..."

# trigger an automation from anywhere
curl -X POST http://localhost:8000/api/hooks/whk_... -H "Content-Type: application/json" -d '{"ticket":"URGENT: checkout down"}'
```

Send `X-Org-Id: org_...` to pick the organization when you authenticate with a user token (JWT). An API key is already bound to its org.

## How context flows into an agent

When an agent runs, its system prompt is built in this order:

1. The agent's own instructions.
2. The operating context: org name, project name and today's date.
3. **Organization guidelines**, set in Settings → General.
4. **Project brief**: description, context and variables.
5. **Skills**: the instruction packs attached to the agent.
6. **Pinned documents** from the agent, the project and the org.
7. **Long-term memory**: recent project memory, plus agent memory if enabled.
8. Rules for tool use and safety, including that tool output is untrusted data.

The agent's tools are the union of:
- its own tools and the tools bundled with its skills
- the project's shared tools
- capability tools (browser, memory, knowledge)
- tools from connections attached to the agent or the project

Project policy is then applied, for example turning off web access or blocking specific tools.

See [multiagent.md](multiagent.md) for the full design.
