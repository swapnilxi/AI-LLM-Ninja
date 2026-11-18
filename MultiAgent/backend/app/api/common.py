from __future__ import annotations

import re
import secrets
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import OrgContext, filter_visible_ids
from ..models import Agent, Connection, Organization, Project, Skill, Team, Tool


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
