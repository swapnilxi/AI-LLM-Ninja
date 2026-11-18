"""Assemble the effective toolset for an agent run.

Effective tools = agent tools ∪ skill tools ∪ project shared tools
                ∪ capability tools (browser / memory / knowledge)
                ∪ connector tools (agent connections ∪ project connections)
                ∪ runtime extras (e.g. supervisor delegation)
                − tools blocked by project policy
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...deps import visible
from ...models import Agent, Connection, Skill, Tool
from .. import knowledge
from ..connectors.registry import connection_tools
from .base import RuntimeTool
from .builtin import BUILTINS
from .custom import agent_tool, http_tool

if TYPE_CHECKING:
    from ..context import RunContext

log = logging.getLogger("agentforge.tools")
MAX_TOOLS = 100


def runtime_for(row: Tool) -> RuntimeTool | None:
    if row.kind == "builtin" and row.builtin_key in BUILTINS:
        return BUILTINS[row.builtin_key].runtime()
    if row.kind == "http":
        return http_tool(row)
    if row.kind == "agent":
        return agent_tool(row)
    return None


async def build_toolset(
    session: AsyncSession,
    ctx: "RunContext",
    agent: Agent,
    skills: list[Skill],
    extra: list[RuntimeTool] | None = None,
) -> list[RuntimeTool]:
    a_set: dict[str, Any] = agent.settings or {}
    p_set: dict[str, Any] = ctx.project.settings or {}

    ids = list(
        dict.fromkeys(
            [*(agent.tool_ids or []), *[t for s in skills for t in (s.tool_ids or [])], *(p_set.get("shared_tool_ids") or [])]
        )
    )
    tools: list[RuntimeTool] = []
    if ids:
        rows = (
            (await session.execute(select(Tool).where(Tool.id.in_(ids), visible(Tool, ctx.org.id), Tool.enabled.is_(True))))
            .scalars()
            .all()
        )
        by_id = {r.id: r for r in rows}
        for tid in ids:
            if tid in by_id and (rt := runtime_for(by_id[tid])):
                tools.append(rt)

    # capability toggles
    if a_set.get("browser_enabled") or p_set.get("browser_for_all_agents"):
        tools += [BUILTINS["web_search"].runtime(), BUILTINS["browse_webpage"].runtime()]
    if a_set.get("memory_enabled") and p_set.get("memory_enabled", True) is not False:
        tools.append(BUILTINS["memory"].runtime())
    if a_set.get("knowledge_enabled", True):
        owners = knowledge.owners_for(ctx.org.id, ctx.project.id, agent.id)
        if await knowledge.has_documents(session, ctx.org.id, owners):
            tools += [BUILTINS["knowledge_search"].runtime(), BUILTINS["read_document"].runtime()]

    # app connectors
    conn_ids = list(dict.fromkeys([*(agent.connection_ids or []), *(p_set.get("connection_ids") or [])]))
    if conn_ids:
        conns = (
            (await session.execute(select(Connection).where(Connection.id.in_(conn_ids), Connection.org_id == ctx.org.id)))
            .scalars()
            .all()
        )
        for conn in conns:
            try:
                tools += await connection_tools(conn)
            except Exception as exc:  # a broken connector must not break the agent
                log.warning("connector %s unavailable: %s", conn.id, exc)

    tools += extra or []

    if not ctx.web_access:
        tools = [t for t in tools if t.category != "web"]
    blocked = set(p_set.get("blocked_tools") or [])

    out, seen = [], set()
    for t in tools:
        name = t.name
        if name in blocked:
            continue
        i = 2
        while name in seen:
            if t.source == "builtin":
                break
            name = f"{t.name[:60]}_{i}"
            i += 1
        if name in seen:
            continue
        t.name = name
        seen.add(name)
        out.append(t)
    return out[:MAX_TOOLS]
