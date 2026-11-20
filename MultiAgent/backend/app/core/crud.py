"""Generic library CRUD router factory (list/create/read/update/delete/duplicate).

Library resources (agents, skills, tools, teams, workflows) are project-independent: `scope=org` items belong to the
current org; `scope=global` items (platform admins only) are shared with every org and can be duplicated to customise.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import scope_org_id
from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_org_ctx, get_visible, get_writable, require_role, visible
from app.modules.tools.models import Tool

Prepare = Callable[[AsyncSession, OrgContext, dict[str, Any], str | None], Awaitable[dict[str, Any]]]
LIMIT_PER_ORG = 1000


def crud_router(
    prefix: str,
    model: Any,
    in_schema: type[BaseModel],
    out_schema: type[BaseModel],
    prepare: Prepare,
    label: str,
    on_delete: Callable[[AsyncSession, OrgContext, Any], Awaitable[None]] | None = None,
) -> APIRouter:
    r = APIRouter(prefix=prefix, tags=[label])

    @r.get("", response_model=list[out_schema])
    async def list_items(
        q: str | None = None,
        scope: str | None = Query(None, pattern="^(org|global)$"),
        ctx: OrgContext = Depends(get_org_ctx),
        session: AsyncSession = Depends(get_session),
    ):
        stmt = select(model).where(visible(model, ctx.org_id))
        if scope == "org":
            stmt = stmt.where(model.org_id == ctx.org_id)
        elif scope == "global":
            stmt = stmt.where(model.org_id.is_(None))
        if q:
            like = f"%{q[:100]}%"
            stmt = stmt.where(or_(model.name.ilike(like), model.description.ilike(like)))
        return (await session.execute(stmt.order_by(model.org_id.is_(None), model.created_at.desc()))).scalars().all()

    @r.post("", response_model=out_schema, status_code=201)
    async def create_item(body: in_schema, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):  # type: ignore[valid-type]
        data = body.model_dump()
        owner = scope_org_id(ctx, data.pop("scope", "org"))
        if owner:
            count = (await session.execute(select(func.count()).select_from(model).where(model.org_id == owner))).scalar_one()
            if count >= LIMIT_PER_ORG:
                raise HTTPException(400, f"{label.title()} limit reached")
        data = await prepare(session, ctx, data, owner)
        obj = model(org_id=owner, created_by=ctx.user.id, **data)
        session.add(obj)
        await audit(session, action=f"{label}.create", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type=label, target_id=obj.id, commit=False)
        await session.commit()
        return obj

    @r.get("/{item_id}", response_model=out_schema)
    async def read_item(item_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
        return await get_visible(session, model, item_id, ctx.org_id)

    @r.put("/{item_id}", response_model=out_schema)
    async def update_item(item_id: str, body: in_schema, request: Request, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):  # type: ignore[valid-type]
        obj = await get_writable(session, model, item_id, ctx)
        if getattr(obj, "kind", None) == "builtin":
            raise HTTPException(403, "Built-in tools cannot be edited")
        data = body.model_dump()
        data.pop("scope", None)
        data = await prepare(session, ctx, {**data, "_self_id": obj.id}, obj.org_id)
        data.pop("_self_id", None)
        for k, v in data.items():
            setattr(obj, k, v)
        await audit(session, action=f"{label}.update", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type=label, target_id=obj.id, commit=False)
        await session.commit()
        return obj

    @r.delete("/{item_id}", status_code=204)
    async def delete_item(item_id: str, request: Request, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
        obj = await get_writable(session, model, item_id, ctx)
        if getattr(obj, "kind", None) == "builtin":
            raise HTTPException(403, "Built-in tools cannot be deleted")
        if on_delete:
            await on_delete(session, ctx, obj)
        await session.delete(obj)
        await audit(session, action=f"{label}.delete", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type=label, target_id=item_id)

    @r.post("/{item_id}/duplicate", response_model=out_schema, status_code=201)
    async def duplicate_item(item_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
        src = await get_visible(session, model, item_id, ctx.org_id)
        if getattr(src, "kind", None) == "builtin":
            raise HTTPException(400, "Built-in tools cannot be duplicated")
        cols = {c.name: getattr(src, c.name) for c in model.__table__.columns if c.name not in ("id", "org_id", "created_at", "updated_at", "created_by")}
        cols["name"] = f"{src.name}-copy" if model is Tool else f"{src.name} (copy)"
        if "command" in cols:
            cols["command"] = None  # slash commands must stay unique
        obj = model(org_id=ctx.org_id, created_by=ctx.user.id, **cols)
        session.add(obj)
        await session.commit()
        return obj

    return r


