# AgentForge architecture and design notes

## 1. Goals

| Requirement | How it is met |
|---|---|
| Manage agents, skills and tools from a UI and an API | REST API (`/api/*`) plus a React dashboard. Every screen calls the same API, and org API keys can call it too. |
| Multi-org, multi-tenant, multi-project | `Organization → Project`, with memberships and roles. Every query is scoped by `org_id`. |
| Agents independent of project and org | Library items have `org_id = NULL` (global) or an owning org. They are never tied to a project. Each run injects org and project context. |
| Choose model and orchestration style | Every agent has its own provider and model, or uses the org default. Teams have one of 5 styles. Workflows are DAGs. |
| Build, save and automate workflows and pipelines | Visual workflow builder. Automations trigger on a cron schedule, an interval, a webhook or manually. |
| End-to-end browser and search tool calls | `web_search` and `browse_webpage` (optionally JavaScript-rendered with Playwright), with toggles per agent and per project. |
| Document context for agents and projects | `Document` rows owned by an org, project or agent. They are chunked and searched with BM25. Pinned documents go into every prompt. |
| Memory for each agent and project | `Memory(scope=agent|project)`, managed by the `memory` tool and the UI. Recent memories are added to the prompt. |
| App connectors | `Connection` = connector plus encrypted config: GitHub, Slack, Notion, Linear, Jira, REST, Telegram, Discord, Email and MCP. |
| Rate limiting and safeguards | See §6. |
| Mobile-responsive dashboard | Tailwind responsive layouts, drawer navigation, bottom-sheet dialogs, touch-friendly React Flow. |

## 2. Tenancy and resource model

```
User ──< Membership(role) >── Organization ──< Project ──< Conversation, Run, Automation
                                  │                └─< Document(owner=project), Memory(scope=project)
                                  ├─< ProviderCredential (encrypted), Secret (encrypted), ApiKey (hashed)
                                  ├─< Connection (app connector, encrypted config)
                                  ├─< AuditLog
                                  └─< Agent / Skill / Tool / Team / Workflow   (org-owned)
Global library (org_id = NULL): Agent / Skill / Tool / Team / Workflow  - visible to every org
Document(owner=agent|org), Memory(scope=agent) are always stored with the *running* org's id,
so a global agent keeps separate documents and memories in each tenant.
```

**Roles.**
- `viewer`: read-only.
- `member`: build and run.
- `admin`: members, keys, providers, secrets and connectors.
- `owner`: everything, including deleting the org.

The first registered user becomes the platform superadmin and is the only one who can edit the global library. Everyone else uses **Duplicate** to fork a global item into their org.

## 3. Runtime

```
POST /api/runs | chat message | automation | webhook
        │  guardrails: per-org rate limit, concurrency cap, daily token budget
        ▼
   Run(queued) ──► asyncio task ──► RunContext{org snapshot, project snapshot, usage, budget, cancel}
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
     run_agent()                    run_team(style)                 run_workflow(DAG)
          │                              │                              │
   system prompt = agent + org + project + skills + pinned docs + memory + safety rules
   tools = agent ∪ skills ∪ project-shared ∪ capabilities ∪ connectors ∪ delegates − policy
   loop: provider.stream() → tool calls (parallel, timeout, size cap, untrusted wrapping) → …
          │
   EventBus → RunEvent rows (trace) + live SSE subscribers (incl. token deltas)
```

**Providers** (`engine/llm`): there are three adapters:
- `AnthropicProvider` uses the official SDK. It supports streaming, adaptive thinking with `output_config.effort`, server-side refusal fallbacks, and append-only replay of assistant turns inside a run.
- `OpenAICompatProvider` covers OpenAI, Groq, Gemini, OpenRouter, DeepSeek, Mistral, Ollama and custom endpoints.
- `MockProvider` is a deterministic offline model.

Credentials are resolved in this order: the org's `ProviderCredential`, then the server environment, then a clear error.

**Orchestration styles** (`engine/orchestrator.py`):

| Style | Behaviour |
|---|---|
| `sequential` | Pipeline: step *n* receives the task plus the output of step *n−1*. |
| `parallel` | Every member answers concurrently (with a concurrency limit). An optional aggregator agent synthesises the answers. |
| `supervisor` | A manager agent gets one `delegate_to_<member>` tool per member, delegates, reviews the results and composes the answer. |
| `router` | A router model picks one member, which then answers. |
| `round_robin` | Group chat or debate over a shared transcript. It ends on the termination keyword or after max rounds. An optional summariser writes the final answer. |

**Workflows** (`engine/workflow.py`):
- Nodes: `input`, `agent`, `team`, `tool`, `llm`, `condition` (with `true`/`false` handles), `template` and `output`.
- Nodes that are ready run concurrently, and branches a condition doesn't take are skipped.
- Templates use sandboxed Jinja and can read `{{ input.* }}`, `{{ last }}`, `{{ nodes.<id>.output }}`, `{{ vars.* }}` and `{{ project.* }}`.
- Graphs are validated for cycles and missing references, and are limited to 60 nodes.

**Automations** (`engine/scheduler.py`): an in-process loop runs every 20 seconds. It claims a due automation by updating `next_run_at` with a compare-and-swap, so running several instances is safe. Webhook automations get a `whk_…` token. The token is stored encrypted for display, and requests are looked up by its SHA-256 hash.

## 4. Tools, knowledge and memory

- **Built-in tools:** `web_search`, `browse_webpage`, `http_request`, `calculator` (AST-safe), `current_datetime`, `knowledge_search`, `read_document` and `memory`.
- **Custom tools:**
  - HTTP tools with templated URL, headers, query and body. They can use `{{ args.x }}`, `{{ secrets.NAME }}` and `{{ vars.x }}`, and secrets are scrubbed from responses.
  - Agent-as-tool, which runs another agent. Nesting is limited to depth 3.
- **Capabilities** are agent toggles that add tools automatically:
  - browser adds `web_search` and `browse_webpage`
  - memory adds `memory`
  - knowledge adds `knowledge_search` and `read_document`, but only when documents exist
- **Project policies:**
  - `web_access` (off removes all web tools)
  - `browser_for_all_agents`
  - `browser_render_js`
  - `allowed_domains` and `blocked_domains`
  - `blocked_tools`
  - `memory_enabled`
  - `shared_tool_ids` and `connection_ids`
  - `default_agent_id`
- **Knowledge:**
  - Text is extracted from PDF (pypdf), DOCX (python-docx), HTML (BeautifulSoup) and text formats.
  - Documents are split into roughly 1,200-character chunks with overlap and scored with BM25.
  - An agent searches its own documents, the current project's and the org's.

### Skills and slash commands

`Skill.command`, `argument_hint` and `command_template` turn a skill into a `/command`. This is handled in `engine/commands.py`, called from `runs._execute`:

1. If the agent's or team's task starts with `/name`, the resolver looks up a visible skill with that command. An org's own skill shadows a global one.
2. The task becomes the rendered template, or the text after the command if there is no template.
3. The skill id goes into `RunContext.extra_skill_ids`.
4. `run_agent` merges `extra_skill_ids` with the agent's own skills, and child contexts pass them on so every team member gets them.

Conversations also carry `skill_ids`, which are added to every run in that chat. Command names must be unique among the skills an org can see. The names `new`, `clear`, `help`, `skills` and `stop` are reserved for the UI's built-in commands.

`engine/skill_templates.py` holds 12 one-click templates. If a template's command is already taken, it is imported without one.

## 5. Connectors

`engine/connectors/catalog.py` holds the static connectors. `mcp_connector.py` discovers tools dynamically from a remote MCP server over Streamable HTTP.

Each action becomes a tool named `<connector>_<action>`. *Write* actions are hidden when the connection is in **read-only mode**, and admins can restrict which actions are exposed.

To add a connector, define a `Connector` with `ConfigField`s (mark secrets with `secret=True`) and `Action`s, then register it in `registry.py`.

## 6. Security safeguards

| Threat | Safeguard |
|---|---|
| Brute force or credential stuffing | Per-IP and per-email limits on login and register (10/min), account lockout (5 failures → 15 min), timing equalised for unknown users, generic error messages. |
| API abuse or DoS | Global per-IP sliding-window limit, which can be shared through Redis. Per-org limits on run starts and webhooks. Per-org concurrency cap and daily token budget. Run and tool timeouts. Max agent steps and nesting depth. |
| Oversized payloads | 2 MB JSON and 15 MB upload limits, enforced on the streamed body as well. Pydantic length limits on every field. Per-org limits on resource counts. |
| SSRF from tools, connectors, URL import or MCP | Only http/https, no credentials in URLs, DNS resolved and every IP checked against public ranges, the connection **pinned to the checked IP** (SNI keeps TLS hostname verification), redirects re-checked on every hop, body size caps, port allow-list, and per-project domain allow and block lists. Playwright subresource requests are filtered the same way. |
| Prompt injection through tool output | Web, connector and HTTP output is wrapped in an *untrusted content* header. The system prompt says tool content is data, not instructions. Secrets never go into prompts. |
| Template or code injection | Sandboxed, immutable Jinja environment. The calculator walks the AST and allows only whitelisted operations. There is no arbitrary code execution tool. |
| Tenant data leaks | Every lookup is checked against the org. References to another tenant's tools, skills or connections are dropped on save. Conversations are private to their user. Tests cover cross-tenant access. |
| Secret exposure | Provider keys, secrets and connector configs are Fernet-encrypted at rest and masked in responses. API keys are stored only as SHA-256 hashes and shown once. Webhook tokens are high-entropy and can be rotated. |
| Session theft | Short-lived HS256 JWTs with an issuer and a `token_version`. "Sign out everywhere" and password changes revoke all tokens. An API key's role can never exceed its creator's. |
| Browser attacks on the UI | CSP (`default-src 'none'` on the API, a strict policy on the SPA), `X-Frame-Options: DENY`, `nosniff`, Referrer-Policy, Permissions-Policy, COOP/CORP, HSTS on HTTPS. CORS limited to an allow-list. Markdown is rendered without raw HTML, and links open with `noopener noreferrer`. |
| Auditing | `AuditLog` records logins, lockouts, member and role changes, keys, provider and secret changes, connectors, and creates and deletes, along with the client IP. |
| Production misconfiguration | `ENV=production` requires a `SECRET_KEY` of at least 32 characters and hides `/docs`. `TRUSTED_HOSTS` is supported. Proxy headers are trusted only when this is turned on. |

## 6b. Portability, feedback and upgrades

- **Export and import** (`api/transfer.py`):
  - `POST /library/export` collects the selected items and, optionally, their dependencies (workflow → team → agent → skill → tool).
  - Items refer to each other by their original id (`ref`). Built-in tools are referenced as `builtin:<key>`.
  - `POST /library/import` re-creates the items in dependency order and remaps every reference.
  - Every item is validated with the regular API input schemas and prep hooks. Names that already exist get an "(imported)" suffix.
  - Clashing `/commands` are dropped, and connections are never included.
- **Feedback:** `PATCH /conversations/{id}/messages/{mid}` stores `{rating, note}` in `Message.meta.feedback`.
- **Re-run:** `POST /runs/{id}/rerun` starts the same target in the same project with the same input.
- **Schema upgrades:** `db._add_missing_columns` runs after `create_all` and adds any model columns the database is missing, using their server defaults. Changes beyond adding columns should use Alembic.

## 7. API surface (prefix `/api`)

- **Auth:** `auth/register|login|me|logout-all`
- **Organizations:** `orgs`, plus `org` with `members`, `providers` (`/{p}/test`), `secrets`, `api-keys`, `audit` and `usage`
- **Projects:** `projects`
- **Library:** `agents|skills|tools|teams|workflows`, each with CRUD and `/{id}/duplicate`. Also `skills/import`, `skills/commands`, `skills/templates` (with `POST /{key}` to add one), `tools/{id}/test` and `workflows/validate`.
- **Import / export:** `library/export` and `library/import`
- **Connectors:** `connectors/catalog`, `connections` (CRUD, `/{id}/test`, `/{id}/tools`)
- **Knowledge:** `documents` (text, `upload`, `from-url`, `search`) and `memories`
- **Runs:** `runs` (create, optionally waiting for the result), `runs/{id}`, `/events`, `/stream` (SSE), `/cancel` and `/rerun`
- **Chat:** `conversations` (PATCH sets the title and `skill_ids`), `/{id}/messages`, and `PATCH /{id}/messages/{mid}` for feedback
- **Automations:** `automations` (CRUD, `/{id}/run`, `/{id}/rotate-token`). The public trigger is `POST /api/hooks/{token}`.
- **Other:** `dashboard`, `catalog`, `health`

## 8. Extending

- **New built-in tool:** add a handler and a `BuiltinDef` in `engine/tools/builtin.py`. It is seeded as a global tool on startup.
- **New provider:** add an entry to `PROVIDERS` in `engine/llm/registry.py`. If it is OpenAI-compatible, a base URL is enough.
- **New node type:** add it to `NODE_TYPES` and `_run_node` in `engine/workflow.py`, and give it a node component in the workflow builder UI.

## 9. Roadmap ideas

- Embeddings or vector search (pgvector) alongside BM25.
- Human-in-the-loop approval for tools that write data.
- A distributed worker queue (arq or Celery) for horizontal scaling.
- OAuth flows for connectors.
- Per-tool cost accounting.
- Alembic migrations.
