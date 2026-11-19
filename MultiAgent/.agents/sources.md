# Sources and licenses

Everything here was copied unmodified from the upstream repositories below (pinned to the commit shown) on 2026-11-19. Symlinks were not followed and file permissions were reset so nothing is executable by accident. To update a skill, re-download it from its repo and bump the commit.

**Trust** says who publishes it. *Official* means the vendor's own repo. *Community* means a third party: read the instructions before you rely on them, because a skill is text that steers an agent.

## Skills (`skills/`)

| Directory | What it is | Upstream (path @ commit) | Trust | License | Size |
|---|---|---|---|---|---|
| `frontend-design` | Distinctive, intentional UI design | [anthropics/skills](https://github.com/anthropics/skills/tree/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/skills/frontend-design) `skills/frontend-design` @ `e4bb5d9` | official (Anthropic) | Complete terms in LICENSE.txt | 2 files, 19 KB |
| `web-design-guidelines` | Review UI code against Web Interface Guidelines | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/web-design-guidelines) `skills/web-design-guidelines` @ `1a2c79d` | official (Vercel) | not declared in SKILL.md | 1 files, 1 KB |
| `vercel-react-best-practices` | React / Next.js performance rules | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/react-best-practices) `skills/react-best-practices` @ `1a2c79d` | official (Vercel) | MIT | 76 files, 224 KB |
| `vercel-composition-patterns` | React composition patterns | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/1a2c79d4e6c4a2283dc2c614b6538cbe1ed5ca62/skills/composition-patterns) `skills/composition-patterns` @ `1a2c79d` | official (Vercel) | MIT | 14 files, 49 KB |
| `find-skills` | Discover and install more skills (npx skills find) | [vercel-labs/skills](https://github.com/vercel-labs/skills/tree/57217cf86ba38148a57af9e90d14a4c049558330/skills/find-skills) `skills/find-skills` @ `57217cf` | official (Vercel) | not declared in SKILL.md | 1 files, 5 KB |
| `diagram-design` | Branded diagrams as self-contained HTML/SVG | [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design/tree/bddddb607f0416815084b7db25255ee646076ca9/skills/diagram-design) `skills/diagram-design` @ `bddddb6` | community | MIT | 317 files, 5666 KB |
| `karpathy-guidelines` | Rules that curb common LLM coding mistakes | [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills/tree/2c606141936f1eeef17fa3043a72095b4765b9c2/skills/karpathy-guidelines) `skills/karpathy-guidelines` @ `2c60614` | community (inspired by Karpathy; not by him) | MIT | 1 files, 2 KB |
| `cloudflare-one` | Cloudflare One / Zero Trust | [cloudflare/skills](https://github.com/cloudflare/skills/tree/5108325ecceabc899c761e07aa617b09c02445ee/skills/cloudflare-one) `skills/cloudflare-one` @ `5108325` | official (Cloudflare) | not declared in SKILL.md | 2 files, 28 KB |
| `detecting-ai-model-prompt-injection-attacks` | Detect prompt injection | [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills/tree/54a798831d2266a3ca61ce68a7acb80b81160d57/skills/detecting-ai-model-prompt-injection-attacks) `skills/detecting-ai-model-prompt-injection-attacks` @ `54a7988` | community (NOT published by Anthropic) | Apache-2.0 | 4 files, 41 KB |
| `defending-llms-with-guardrails` | LLM guardrails | [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills/tree/54a798831d2266a3ca61ce68a7acb80b81160d57/skills/defending-llms-with-guardrails) `skills/defending-llms-with-guardrails` @ `54a7988` | community (NOT published by Anthropic) | Apache-2.0 | 5 files, 33 KB |
| `building-incident-response-playbook` | Incident-response playbooks | [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills/tree/54a798831d2266a3ca61ce68a7acb80b81160d57/skills/building-incident-response-playbook) `skills/building-incident-response-playbook` @ `54a7988` | community (NOT published by Anthropic) | Apache-2.0 | 4 files, 32 KB |
| `deploying-cloudflare-access-for-zero-trust` | Cloudflare Access / Zero Trust | [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills/tree/54a798831d2266a3ca61ce68a7acb80b81160d57/skills/deploying-cloudflare-access-for-zero-trust) `skills/deploying-cloudflare-access-for-zero-trust` @ `54a7988` | community (NOT published by Anthropic) | Apache-2.0 | 8 files, 45 KB |
| `continuous-llm-red-teaming-with-promptfoo` | Red-team your own LLM apps in CI | [mukul975/Anthropic-Cybersecurity-Skills](https://github.com/mukul975/Anthropic-Cybersecurity-Skills/tree/54a798831d2266a3ca61ce68a7acb80b81160d57/skills/continuous-llm-red-teaming-with-promptfoo) `skills/continuous-llm-red-teaming-with-promptfoo` @ `54a7988` | community (NOT published by Anthropic) | Apache-2.0 | 5 files, 29 KB |
| `browser-use` | Browser control via the browser-use CLI | [browser-use/browser-use](https://github.com/browser-use/browser-use/tree/ccbdb8095fbaf903c748880a600054a34c7b6191/skills/browser-use) `skills/browser-use` @ `ccbdb80` | official (browser-use) | not declared in SKILL.md | 1 files, 11 KB |
| `open-source` | Writing code against the browser-use library | [browser-use/browser-use](https://github.com/browser-use/browser-use/tree/ccbdb8095fbaf903c748880a600054a34c7b6191/skills/open-source) `skills/open-source` @ `ccbdb80` | official (browser-use) | not declared in SKILL.md | 1 files, 6 KB |
| `agentmemory-mcp-tools` | Map of agentmemory's MCP tools | [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory/tree/5c9e2e698bda138dcb7de50ee4dd3260ee4fb8eb/plugin/skills/agentmemory-mcp-tools) `plugin/skills/agentmemory-mcp-tools` @ `5c9e2e6` | community | not declared in SKILL.md | 3 files, 18 KB |
| `memory-discipline` | Recall-before-work / save-at-decisions loop | [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory/tree/5c9e2e698bda138dcb7de50ee4dd3260ee4fb8eb/plugin/skills/memory-discipline) `plugin/skills/memory-discipline` @ `5c9e2e6` | community | not declared in SKILL.md | 2 files, 7 KB |

## Reference lists (`references/`)

| File | Upstream | License |
|---|---|---|
| `awesome-harness-engineering-walkinglabs.md` | [walkinglabs/awesome-harness-engineering](https://github.com/walkinglabs/awesome-harness-engineering) @ `ae9024f` | CC0-1.0 (repo LICENSE) |
| `awesome-harness-engineering-ai-boost.md` | [ai-boost/awesome-harness-engineering](https://github.com/ai-boost/awesome-harness-engineering) @ `a0db6f2` | CC0-1.0 (repo LICENSE) |

Two different repositories are called *awesome-harness-engineering*, so both are included.

## License notes

- Skills that declare a license in their `SKILL.md` front matter are listed above. `frontend-design` ships its own `LICENSE.txt`. The cybersecurity skills ship their `LICENSE` (Apache-2.0).
- **No license is stated** by `anthropics/skills` (beyond `frontend-design`'s file), `vercel-labs/agent-skills` (for `web-design-guidelines`) or `forrestchang/andrej-karpathy-skills` (the skill declares MIT, the repo has no LICENSE file). These are distributed for exactly this use through the skills registry, but check upstream before redistributing this folder publicly.
- **OpenViking is deliberately not included.** `volcengine/OpenViking` is licensed AGPL-3.0, and copying its files into this repository would bring copyleft terms with it. See the README for how to add it if you accept that.
- `mukul975/Anthropic-Cybersecurity-Skills` is a community project and is **not** published by Anthropic, despite its name.
