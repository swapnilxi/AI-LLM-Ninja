"""Curated catalog for the Discover page: skill packs, popular MCP servers and knowledge docs.

Every entry was checked against the live source when it was added (repo has the SKILL.md, MCP endpoint answers an
`initialize` request). `trust` says who publishes it: "official" (the vendor), "community" (third party, review before
use) or "built-in" (ships with AgentForge). Installs never execute anything from these sources: skills are copied as
instructions only, MCP servers are called over HTTPS through the SSRF-safe client.
"""
from __future__ import annotations

import re
from typing import Any

BUILTIN_FIND_SKILLS = "Find Skills"  # name of the seeded global skill (see seed.py)

SKILL_PACKS: list[dict[str, Any]] = [
    {
        "id": "find-skills",
        "name": "Find Skills",
        "tagline": "Agents search for a skill and use it on the spot",
        "description": (
            "Adds a playbook plus the find_skills and use_skill tools. An agent searches your installed skills, this catalog and the skills.sh registry, "
            "then loads the best match for the task at hand. Adapted from the find-skills skill in vercel-labs/skills for agents that cannot run npx."
        ),
        "category": "Skills ecosystem",
        "trust": "built-in",
        "repo_url": "https://github.com/vercel-labs/skills",
        "builtin": BUILTIN_FIND_SKILLS,
        "skills": ["find-skills"],
    },
    {
        "id": "anthropic-frontend-design",
        "name": "Frontend Design (Anthropic)",
        "tagline": "Distinctive, intentional UI instead of templated defaults",
        "description": "Anthropic's frontend-design skill: aesthetic direction, typography and layout choices for building new UI or reshaping an existing one.",
        "category": "Design & frontend",
        "trust": "official",
        "repo_url": "https://github.com/anthropics/skills",
        "command": "npx skills add anthropics/skills --skill frontend-design",
        "paths": [
            "skills/frontend-design/SKILL.md",
        ],
        "skills": ["frontend-design"],
    },
    {
        "id": "vercel-web-design",
        "name": "Web Design & React (Vercel)",
        "tagline": "Vercel's web interface guidelines and React best practices",
        "description": "Three skills from vercel-labs/agent-skills: review UI code against the Web Interface Guidelines, apply React/Next.js performance practices, and use composition patterns.",
        "category": "Design & frontend",
        "trust": "official",
        "repo_url": "https://github.com/vercel-labs/agent-skills",
        "command": "npx skills add vercel-labs/agent-skills --skill web-design-guidelines react-best-practices composition-patterns",
        "paths": [
            "skills/web-design-guidelines/SKILL.md",
            "skills/react-best-practices/SKILL.md",
            "skills/composition-patterns/SKILL.md",
        ],
        "skills": ["web-design-guidelines", "react-best-practices", "composition-patterns"],
    },
    {
        "id": "diagram-design",
        "name": "Diagram Design",
        "tagline": "Branded diagrams as self-contained HTML/SVG",
        "description": "Creates architecture diagrams, flowcharts, sequence and state diagrams as self-contained HTML/SVG.",
        "category": "Design & frontend",
        "trust": "community",
        "repo_url": "https://github.com/cathrynlavery/diagram-design",
        "command": "npx skills add cathrynlavery/diagram-design",
        "paths": [
            "skills/diagram-design/SKILL.md",
        ],
        "skills": ["diagram-design"],
        "caveat": "Most useful for an agent that can hand back HTML/SVG files.",
    },
    {
        "id": "karpathy-guidelines",
        "name": "Karpathy Coding Guidelines",
        "tagline": "Short rules that curb common LLM coding mistakes",
        "description": "A compact set of coding guidelines condensed from Andrej Karpathy's public observations on how LLMs go wrong when writing code.",
        "category": "Engineering",
        "trust": "community",
        "repo_url": "https://github.com/forrestchang/andrej-karpathy-skills",
        "command": "npx skills add forrestchang/andrej-karpathy-skills",
        "paths": [
            "skills/karpathy-guidelines/SKILL.md",
        ],
        "skills": ["karpathy-guidelines"],
        "caveat": "Community project inspired by Karpathy. It is not published by him.",
    },
    {
        "id": "cloudflare-zero-trust",
        "name": "Cloudflare One (Zero Trust)",
        "tagline": "Cloudflare's own skill for Access, Gateway and related security products",
        "description": "From Cloudflare's official skills repo: guidance for Cloudflare One, the Zero Trust platform (Access, Gateway and related products).",
        "category": "Security",
        "trust": "official",
        "repo_url": "https://github.com/cloudflare/skills",
        "command": "npx skills add cloudflare/skills --skill cloudflare-one",
        "paths": [
            "skills/cloudflare-one/SKILL.md",
        ],
        "skills": ["cloudflare-one"],
    },
    {
        "id": "cyber-defense",
        "name": "Cybersecurity Defense Playbooks",
        "tagline": "Prompt-injection defence, LLM guardrails, incident response, Zero Trust",
        "description": (
            "Five defensive playbooks picked from a 750+ skill community library: detecting prompt-injection attacks, defending LLMs with guardrails, "
            "building an incident-response playbook, deploying Cloudflare Access for Zero Trust, and continuous LLM red-teaming of your own apps with Promptfoo."
        ),
        "category": "Security",
        "trust": "community",
        "repo_url": "https://github.com/mukul975/Anthropic-Cybersecurity-Skills",
        "command": (
            "npx skills add mukul975/Anthropic-Cybersecurity-Skills --skill detecting-ai-model-prompt-injection-attacks defending-llms-with-guardrails "
            "building-incident-response-playbook deploying-cloudflare-access-for-zero-trust continuous-llm-red-teaming-with-promptfoo"
        ),
        "paths": [
            "skills/detecting-ai-model-prompt-injection-attacks/SKILL.md",
            "skills/defending-llms-with-guardrails/SKILL.md",
            "skills/building-incident-response-playbook/SKILL.md",
            "skills/deploying-cloudflare-access-for-zero-trust/SKILL.md",
            "skills/continuous-llm-red-teaming-with-promptfoo/SKILL.md",
        ],
        "skills": [
            "detecting-ai-model-prompt-injection-attacks", "defending-llms-with-guardrails", "building-incident-response-playbook",
            "deploying-cloudflare-access-for-zero-trust", "continuous-llm-red-teaming-with-promptfoo",
        ],
        "caveat": "Despite its name this is a community project, not published by Anthropic. Review the instructions before attaching them to an agent.",
    },
    {
        "id": "browser-use-guide",
        "name": "Browser Use (library guide)",
        "tagline": "How to build agents with the browser-use Python library",
        "description": "The open-source skill from the browser-use repo, covering the library's Agent and Browser APIs.",
        "category": "Agent building blocks",
        "trust": "official",
        "repo_url": "https://github.com/browser-use/browser-use",
        "command": "npx skills add browser-use/browser-use --skill open-source",
        "paths": ["skills/open-source/SKILL.md"],
        "skills": ["open-source"],
        "caveat": "For live browsing add the Browser Use Cloud connector (Connectors tab). The repo's other skills drive its CLI, which agents here cannot run.",
    },
    {
        "id": "agentmemory",
        "name": "agentmemory",
        "tagline": "Playbooks for agents connected to an agentmemory server",
        "description": "Two skills from rohitg00/agentmemory: a map of its MCP memory tools and the recall-before-work / save-at-decisions loop.",
        "category": "Agent building blocks",
        "trust": "community",
        "repo_url": "https://github.com/rohitg00/agentmemory",
        "command": "npx skills add rohitg00/agentmemory --skill agentmemory-mcp-tools memory-discipline",
        "paths": [
            "plugin/skills/agentmemory-mcp-tools/SKILL.md",
            "plugin/skills/memory-discipline/SKILL.md",
        ],
        "skills": ["agentmemory-mcp-tools", "memory-discipline"],
        "caveat": "Only useful alongside an agentmemory MCP server. It runs locally by default, so expose it on a public HTTPS URL first. Agents here already have built-in memory.",
    },
    {
        "id": "openviking",
        "name": "OpenViking",
        "tagline": "Context database for agents: memory, resources and skills as a file system",
        "description": "Three skills from volcengine/OpenViking: recalling and persisting long-term memory, working with its skills, and searching resources stored under viking://.",
        "category": "Agent building blocks",
        "trust": "community",
        "repo_url": "https://github.com/volcengine/OpenViking",
        "command": "npx skills add volcengine/OpenViking --skill openviking-memory openviking-skills ov-resources",
        "paths": [
            "agent-plugins/skills/openviking-memory/SKILL.md",
            "agent-plugins/skills/openviking-skills/SKILL.md",
            "agent-plugins/skills/ov-resources/SKILL.md",
        ],
        "skills": ["openviking-memory", "openviking-skills", "ov-resources"],
        "caveat": "These skills call OpenViking's MCP tools, so they need an OpenViking server connected as an MCP connector.",
    },
]

MCP_SERVERS: list[dict[str, Any]] = [
    {
        "id": "deepwiki", "name": "DeepWiki", "category": "Developer", "popular": True, "auth": "none",
        "tagline": "Ask questions about any public GitHub repository",
        "url": "https://mcp.deepwiki.com/mcp", "docs_url": "https://docs.devin.ai/work-with-devin/deepwiki-mcp",
    },
    {
        "id": "context7", "name": "Context7", "category": "Developer", "popular": True, "auth": "none",
        "tagline": "Up-to-date documentation and code examples for libraries",
        "url": "https://mcp.context7.com/mcp", "docs_url": "https://github.com/upstash/context7",
    },
    {
        "id": "cloudflare-docs", "name": "Cloudflare Docs", "category": "Developer", "popular": False, "auth": "none",
        "tagline": "Search the Cloudflare documentation",
        "url": "https://docs.mcp.cloudflare.com/mcp", "docs_url": "https://developers.cloudflare.com/agents/model-context-protocol/mcp-servers-for-cloudflare/",
    },
    {
        "id": "exa", "name": "Exa Search", "category": "Search & browsing", "popular": True, "auth": "none",
        "tagline": "Web and code search built for AI agents",
        "url": "https://mcp.exa.ai/mcp", "docs_url": "https://docs.exa.ai/reference/exa-mcp",
    },
    {
        "id": "huggingface", "name": "Hugging Face", "category": "AI & data", "popular": False, "auth": "optional",
        "tagline": "Search models, datasets, Spaces and papers on the Hub",
        "url": "https://huggingface.co/mcp", "token_label": "Hugging Face access token", "token_url": "https://huggingface.co/settings/tokens",
        "docs_url": "https://huggingface.co/settings/mcp",
    },
    {
        "id": "browser-use-cloud", "name": "Browser Use Cloud", "category": "Search & browsing", "popular": True, "auth": "bearer",
        "tagline": "Cloud browsers your agents can drive to complete web tasks",
        "url": "https://api.browser-use.com/v3/mcp", "token_label": "Browser Use API key", "token_url": "https://cloud.browser-use.com/settings",
        "docs_url": "https://docs.browser-use.com/cloud/guides/mcp-server",
    },
    {
        "id": "github-mcp", "name": "GitHub (full MCP server)", "category": "Developer", "popular": True, "auth": "bearer",
        "tagline": "GitHub's official server: repos, issues, pull requests, code search",
        "url": "https://api.githubcopilot.com/mcp/", "token_label": "GitHub personal access token", "token_url": "https://github.com/settings/personal-access-tokens/new",
        "docs_url": "https://github.com/github/github-mcp-server",
        "caveat": "Exposes many tools including write actions. Use a fine-grained token with only the permissions you need.",
    },
    {
        "id": "stripe", "name": "Stripe", "category": "Business", "popular": False, "auth": "bearer",
        "tagline": "Customers, invoices, subscriptions and docs search",
        "url": "https://mcp.stripe.com", "token_label": "Stripe restricted API key", "token_url": "https://dashboard.stripe.com/apikeys",
        "docs_url": "https://docs.stripe.com/mcp",
        "caveat": "Use a restricted key limited to what the agent needs, and a test-mode key first.",
    },
    {
        "id": "neon", "name": "Neon", "category": "AI & data", "popular": False, "auth": "bearer",
        "tagline": "Manage Postgres projects, branches and run SQL",
        "url": "https://mcp.neon.tech/mcp", "token_label": "Neon API key", "token_url": "https://console.neon.tech/app/settings/api-keys",
        "docs_url": "https://neon.com/docs/ai/neon-mcp-server",
        "caveat": "Can run SQL against your databases. Prefer a branch or a throwaway project.",
    },
    {
        "id": "supabase", "name": "Supabase", "category": "AI & data", "popular": False, "auth": "bearer",
        "tagline": "Manage projects, tables and run SQL on Supabase",
        "url": "https://mcp.supabase.com/mcp", "token_label": "Supabase personal access token", "token_url": "https://supabase.com/dashboard/account/tokens",
        "docs_url": "https://supabase.com/docs/guides/getting-started/mcp",
        "caveat": "Can change your database. Use a development project.",
    },
]

KNOWLEDGE_DOCS: list[dict[str, Any]] = [
    {
        "id": "awesome-harness-engineering",
        "name": "Awesome Harness Engineering (walkinglabs)",
        "tagline": "Articles, playbooks, benchmarks and open-source projects for harness engineering",
        "description": "Adds the list's README to project knowledge so agents can search it with knowledge_search.",
        "url": "https://raw.githubusercontent.com/walkinglabs/awesome-harness-engineering/HEAD/README.md",
        "repo_url": "https://github.com/walkinglabs/awesome-harness-engineering",
        "trust": "community",
    },
]

_BY_ID = {
    "skill": {p["id"]: p for p in SKILL_PACKS},
    "mcp": {m["id"]: m for m in MCP_SERVERS},
    "knowledge": {k["id"]: k for k in KNOWLEDGE_DOCS},
}


def get_pack(pack_id: str) -> dict[str, Any] | None:
    return _BY_ID["skill"].get(pack_id)


def get_mcp(server_id: str) -> dict[str, Any] | None:
    return _BY_ID["mcp"].get(server_id)


def get_knowledge(item_id: str) -> dict[str, Any] | None:
    return _BY_ID["knowledge"].get(item_id)


def search_packs(terms: list[str], limit: int = 5) -> list[dict[str, Any]]:
    """Rank skill packs by how many search terms appear in their name, tagline, description or skill names."""
    scored = []
    for p in SKILL_PACKS:
        hay = " ".join([p["name"], p["tagline"], p["description"], p["category"], *p.get("skills", [])]).lower()
        score = sum(1 for t in terms if t in hay)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:limit]]


SOURCE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9 _.\-]{1,120}$")
