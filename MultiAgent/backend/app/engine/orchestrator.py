"""Multi-agent orchestration styles for Teams.

sequential  - pipeline: each agent refines the previous agent's output
parallel    - fan-out to all members concurrently, then an aggregator synthesises
supervisor  - a manager agent delegates sub-tasks to members (members exposed as tools)
router      - a router picks the single best member for the task
round_robin - group chat / debate: members take turns on a shared transcript
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from ..db import SessionLocal
from ..models import Agent, Team
from .context import RunContext
from .llm.base import LLMError, ModelSettings
from .llm.registry import get_provider, resolve_model
from .runner import run_agent
from .tools.base import RuntimeTool, ToolResult, sanitize_name, schema

STYLES = {
    "sequential": "Pipeline - each agent builds on the previous agent's output",
    "parallel": "Fan-out / fan-in - all members work concurrently, an aggregator merges results",
    "supervisor": "Manager delegates sub-tasks to specialist members and composes the answer",
    "router": "A router picks the single best member for each task",
    "round_robin": "Group chat / debate - members take turns until consensus or max rounds",
}


async def _load_members(team: Team, org_id: str) -> list[tuple[Agent, dict[str, Any]]]:
    async with SessionLocal() as s:
        out = []
        for m in team.members or []:
            a = await s.get(Agent, m.get("agent_id", ""))
            if a and (a.org_id is None or a.org_id == org_id):
                out.append((a, m))
    if not out:
        raise LLMError("Team has no valid members")
    return out


async def _load_agent(agent_id: str | None, org_id: str) -> Agent | None:
    if not agent_id:
        return None
    async with SessionLocal() as s:
        a = await s.get(Agent, agent_id)
    return a if a and (a.org_id is None or a.org_id == org_id) else None


def _label(agent: Agent, member: dict[str, Any]) -> str:
    return f"{agent.name} ({member['role']})" if member.get("role") else agent.name


def _member_note(member: dict[str, Any]) -> str:
    bits = []
    if member.get("role"):
        bits.append(f"Your role in this team: {member['role']}.")
    if member.get("instructions"):
        bits.append(str(member["instructions"]))
    return "## Team role\n" + " ".join(bits) if bits else ""


async def run_team(ctx: RunContext, team: Team, task: str, history: list[dict[str, Any]] | None = None) -> str:
    style = team.style if team.style in STYLES else "sequential"
    members = await _load_members(team, ctx.org.id)
    cfg = team.config or {}
    await ctx.emit("team_start", {"team_id": team.id, "style": style, "members": [_label(a, m) for a, m in members]})
    runner = {
        "sequential": _sequential,
        "parallel": _parallel,
        "supervisor": _supervisor,
        "router": _router,
        "round_robin": _round_robin,
    }[style]
    out = await runner(ctx, team, members, task, history or [], cfg)
    await ctx.emit("team_end", {"team_id": team.id, "output": out[:4000]})
    return out


async def _sequential(ctx, team, members, task, history, cfg) -> str:
    current = task
    for i, (agent, m) in enumerate(members):
        ctx.check()
        if i == 0:
            prompt = task
        else:
            prompt = (
                f"Original task:\n{task}\n\nOutput from the previous step ({_label(*members[i - 1])}):\n{current}\n\n"
                "Continue the pipeline: improve, extend or transform this output according to your role. Return the full result."
            )
        res = await run_agent(ctx.child(agent.id), agent, prompt, history=history if i == 0 else None, label=_label(agent, m), extra_system=_member_note(m))
        current = res.text
        await ctx.emit("team_message", {"step": i + 1, "from": _label(agent, m), "text": current[:4000]})
    return current


async def _parallel(ctx, team, members, task, history, cfg) -> str:
    limit = asyncio.Semaphore(int(cfg.get("max_concurrency") or 4))

    async def one(agent, m):
        async with limit:
            res = await run_agent(ctx.child(agent.id), agent, task, history=history, label=_label(agent, m), extra_system=_member_note(m))
            await ctx.emit("team_message", {"from": _label(agent, m), "text": res.text[:4000]})
            return _label(agent, m), res.text

    results = await asyncio.gather(*[one(a, m) for a, m in members])
    combined = "\n\n".join(f"### {name}\n{text}" for name, text in results)
    aggregator = await _load_agent(cfg.get("aggregator_agent_id") or team.manager_agent_id, ctx.org.id)
    if not aggregator:
        return combined
    prompt = (
        f"Task:\n{task}\n\nIndependent answers from team members:\n\n{combined}\n\n"
        "Synthesise these into one best final answer. Resolve disagreements, keep the strongest points and cite sources if present."
    )
    res = await run_agent(ctx.child(aggregator.id), aggregator, prompt, label=f"{aggregator.name} (aggregator)")
    return res.text


async def _supervisor(ctx, team, members, task, history, cfg) -> str:
    manager = await _load_agent(team.manager_agent_id, ctx.org.id)
    if not manager:
        raise LLMError("Supervisor teams need a manager agent")
    delegates: list[RuntimeTool] = []
    roster = []
    for agent, m in members:
        if agent.id == manager.id:
            continue
        tool_name = sanitize_name(f"delegate_to_{agent.name.lower()}")[:64]
        roster.append(f"- {tool_name}: {agent.name} — {m.get('role') or agent.description[:200]}")

        async def handler(args, c, _a=agent, _m=m):
            res = await run_agent(
                c.child(_a.id),
                _a,
                f"{args.get('task', '')}\n\nContext from the manager:\n{args.get('context', '')}".strip(),
                label=_label(_a, _m),
                extra_system=_member_note(_m),
            )
            await ctx.emit("team_message", {"from": _label(_a, _m), "text": res.text[:4000]})
            return ToolResult(res.text)

        delegates.append(
            RuntimeTool(
                name=tool_name,
                description=f"Delegate a sub-task to {agent.name}: {m.get('role') or agent.description}"[:1000],
                parameters=schema(
                    {"task": {"type": "string", "description": "Clear, self-contained sub-task"}, "context": {"type": "string", "description": "Relevant context"}},
                    ["task"],
                ),
                handler=handler,
                source="delegate",
                category="agent",
            )
        )
    extra = (
        "## You are the team manager\nBreak the task down, delegate sub-tasks to your team using the delegate tools, "
        "review their work and then write the final answer yourself.\nYour team:\n" + "\n".join(roster)
    )
    res = await run_agent(ctx.child(manager.id), manager, task, history=history, extra_tools=delegates, label=f"{manager.name} (manager)", extra_system=extra)
    return res.text


async def _router(ctx, team, members, task, history, cfg) -> str:
    options = {sanitize_name(a.name.lower()): (a, m) for a, m in members}
    router_agent = await _load_agent(cfg.get("router_agent_id") or team.manager_agent_id, ctx.org.id) or members[0][0]
    menu = "\n".join(f"- {key}: {a.name} — {m.get('role') or a.description}" for key, (a, m) in options.items())
    system = (
        "ROUTE_SELECTION\nYou are a router. Pick the single best agent for the user's task.\n"
        f"Options:\n{menu}\nReply with ONLY the option key, nothing else."
    )
    async with SessionLocal() as s:
        pk, model = await resolve_model(s, ctx.org, router_agent.provider, router_agent.model)
        provider = await get_provider(s, ctx.org, pk)
    resp = await provider.complete(system=system, messages=[{"role": "user", "content": task}], tools=[], settings=ModelSettings(model=model, max_tokens=2000, effort="low"))
    ctx.add_usage(resp.usage.input_tokens, resp.usage.output_tokens)
    choice = resp.text.strip().strip("`'\" .").lower()
    picked = options.get(choice) or next((v for k, v in options.items() if k in choice), None) or members[0]
    agent, m = picked
    await ctx.emit("route", {"choice": _label(agent, m), "raw": resp.text[:200]})
    res = await run_agent(ctx.child(agent.id), agent, task, history=history, label=_label(agent, m), extra_system=_member_note(m))
    return res.text


async def _round_robin(ctx, team, members, task, history, cfg) -> str:
    rounds = max(1, min(int(cfg.get("max_rounds") or 2), 6))
    keyword = (cfg.get("termination_keyword") or "TERMINATE").strip()
    transcript: list[tuple[str, str]] = []
    last = ""
    for r in range(rounds):
        for agent, m in members:
            ctx.check()
            convo = "\n\n".join(f"**{who}:** {text}" for who, text in transcript) or "(no messages yet)"
            prompt = (
                f"Group task:\n{task}\n\nConversation so far (round {r + 1}/{rounds}):\n{convo}\n\n"
                f"Contribute your next message according to your role. If the team has reached a complete, agreed answer, "
                f"write the final answer and end with the word {keyword}."
            )
            res = await run_agent(ctx.child(agent.id), agent, prompt, label=_label(agent, m), extra_system=_member_note(m))
            text = res.text.strip()
            transcript.append((_label(agent, m), text))
            await ctx.emit("team_message", {"round": r + 1, "from": _label(agent, m), "text": text[:4000]})
            last = text
            if keyword and re.search(rf"\b{re.escape(keyword)}\b", text):
                return re.sub(rf"\s*\b{re.escape(keyword)}\b\.?", "", text).strip()
    summarizer = await _load_agent(cfg.get("aggregator_agent_id") or team.manager_agent_id, ctx.org.id)
    if summarizer:
        convo = "\n\n".join(f"**{who}:** {text}" for who, text in transcript)
        res = await run_agent(ctx.child(summarizer.id), summarizer, f"Task:\n{task}\n\nDiscussion:\n{convo}\n\nWrite the final answer.", label=f"{summarizer.name} (summary)")
        return res.text
    return last
