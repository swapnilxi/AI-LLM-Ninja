from __future__ import annotations

import re
import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import OrgContext, filter_visible_ids
from app.modules.agents.models import Agent
from app.modules.connectors.models import Connection
from app.modules.orgs.models import Organization
from app.modules.projects.models import Project
from app.modules.skills.models import Skill
from app.modules.teams.models import Team
from app.modules.tools.models import Tool


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "org"
    return f"{base}-{secrets.token_hex(3)}"


def scope_org_id(ctx: OrgContext, scope: str) -> str | None:
    if scope == "global":
        if not ctx.user.is_superadmin:
            raise HTTPException(403, "Only platform admins can publish to the global library")
        return None
    return ctx.org_id


async def clean_refs(session: AsyncSession, ctx: OrgContext, data: dict[str, Any], owner_org: str | None) -> dict[str, Any]:
    """Drop references to resources the org cannot see (prevents cross-tenant references)."""
    for key, model in (("tool_ids", Tool), ("skill_ids", Skill)):
        if key in data and data[key] is not None:
            ids = await filter_visible_ids(session, model, list(dict.fromkeys(data[key])), ctx.org_id)
            if owner_org is None:  # global items may only reference global items
                rows = (await session.execute(select(model.id).where(model.id.in_(ids), model.org_id.is_(None)))).scalars().all()
                ids = [i for i in ids if i in set(rows)]
            data[key] = ids
    if data.get("connection_ids") is not None:
        if owner_org is None:
            data["connection_ids"] = []
        else:
            rows = (
                await session.execute(select(Connection.id).where(Connection.id.in_(data["connection_ids"]), Connection.org_id == ctx.org_id))
            ).scalars().all()
            data["connection_ids"] = [i for i in data["connection_ids"] if i in set(rows)]
    return data


async def check_agent_ids(session: AsyncSession, ctx: OrgContext, ids: list[str]) -> None:
    ids = [i for i in ids if i]
    ok = await filter_visible_ids(session, Agent, ids, ctx.org_id)
    missing = set(ids) - set(ok)
    if missing:
        raise HTTPException(400, f"Unknown agent(s): {', '.join(sorted(missing))}")


async def check_team_ids(session: AsyncSession, ctx: OrgContext, ids: list[str]) -> None:
    ids = [i for i in ids if i]
    ok = await filter_visible_ids(session, Team, ids, ctx.org_id)
    if set(ids) - set(ok):
        raise HTTPException(400, "Unknown team referenced")


async def create_default_project(session: AsyncSession, org: Organization) -> Project:
    p = Project(
        org_id=org.id,
        name="Default Project",
        description="Starter project. Add a brief, documents and variables so every agent knows the context.",
        context="",
        settings={"web_access": True, "memory_enabled": True},
    )
    session.add(p)
    return p


async def pick_agent(session: AsyncSession, ctx: OrgContext, project: Project, agent_id: str | None = None) -> Agent:
    """Agent to run something with: the requested one, else the project's default, else the org's first agent, else a global one."""
    for candidate in (agent_id, (project.settings or {}).get("default_agent_id")):
        if candidate:
            ok = await filter_visible_ids(session, Agent, [candidate], ctx.org_id)
            if ok:
                return await session.get(Agent, ok[0])
            if candidate == agent_id:
                raise HTTPException(404, "Agent not found")
    from app.core.deps import visible

    row = (await session.execute(select(Agent).where(visible(Agent, ctx.org_id)).order_by(Agent.org_id.is_(None), Agent.created_at).limit(1))).scalars().first()
    if not row:
        raise HTTPException(400, "Create an agent first")
    return row
