"""Agents API (library resource)."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import clean_refs
from app.core.crud import crud_router
from app.core.deps import OrgContext
from app.engine.llm.registry import PROVIDERS
from app.modules.agents.models import Agent
from app.modules.agents.schemas import AgentIn, AgentOut
from app.modules.knowledge.models import Document, Memory
from app.modules.training.models import Lesson


async def prep_agent(session: AsyncSession, ctx: OrgContext, data: dict[str, Any], owner: str | None) -> dict[str, Any]:
    if data.get("provider") not in ("default", "", None) and data["provider"] not in PROVIDERS:
        raise HTTPException(400, f"Unknown provider '{data['provider']}'")
    allowed_settings = {"browser_enabled", "memory_enabled", "knowledge_enabled", "show_thinking", "auto_learn"}
    data["settings"] = {k: bool(v) for k, v in (data.get("settings") or {}).items() if k in allowed_settings}
    data["tags"] = [t[:40] for t in data.get("tags") or []]
    return await clean_refs(session, ctx, data, owner)


async def del_agent(session: AsyncSession, ctx: OrgContext, obj: Agent) -> None:
    await session.execute(delete(Document).where(Document.owner_type == "agent", Document.owner_id == obj.id, Document.org_id == ctx.org_id))
    await session.execute(delete(Memory).where(Memory.agent_id == obj.id, Memory.org_id == ctx.org_id))
    await session.execute(delete(Lesson).where(Lesson.agent_id == obj.id, Lesson.org_id == ctx.org_id))


agents_router = crud_router("/agents", Agent, AgentIn, AgentOut, prep_agent, "agent", del_agent)

ROUTERS = [agents_router]
