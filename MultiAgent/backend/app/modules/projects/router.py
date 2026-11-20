from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import OrgContext, audit, filter_visible_ids, get_org_ctx, get_project, require_role
from app.modules.agents.models import Agent
from app.modules.connectors.models import Connection
from app.modules.knowledge.models import Document, Memory
from app.modules.projects.models import Project
from app.modules.projects.schemas import ProjectIn, ProjectOut, ProjectUpdate
from app.modules.skills.models import Skill
from app.modules.tools.models import Tool

router = APIRouter(prefix="/projects", tags=["projects"])

_BOOL = ("web_access", "memory_enabled", "browser_for_all_agents", "browser_render_js", "tasks_enabled", "scheduling_enabled", "skill_discovery_enabled")
_LIST = ("allowed_domains", "blocked_domains", "shared_tool_ids", "connection_ids", "blocked_tools", "skill_ids")
_STR = ("default_agent_id", "timezone")


async def clean_settings(session: AsyncSession, ctx: OrgContext, raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k in _BOOL:
            out[k] = bool(v)
        elif k in _LIST:
            if not isinstance(v, list):
                raise HTTPException(400, f"{k} must be a list")
            out[k] = [str(x).strip() for x in v if str(x).strip()][:200]
        elif k in _STR:
            out[k] = str(v or "")[:120]
        else:
            raise HTTPException(400, f"Unknown project setting '{k}'")
    if "shared_tool_ids" in out:
        out["shared_tool_ids"] = await filter_visible_ids(session, Tool, out["shared_tool_ids"], ctx.org_id)
    if "skill_ids" in out:  # project-level skills: given to every agent that runs in this project
        out["skill_ids"] = await filter_visible_ids(session, Skill, list(dict.fromkeys(out["skill_ids"])), ctx.org_id)
    if "connection_ids" in out:
        rows = (await session.execute(select(Connection.id).where(Connection.id.in_(out["connection_ids"]), Connection.org_id == ctx.org_id))).scalars().all()
        out["connection_ids"] = [i for i in out["connection_ids"] if i in set(rows)]
    if out.get("default_agent_id"):
        ok = await filter_visible_ids(session, Agent, [out["default_agent_id"]], ctx.org_id)
        out["default_agent_id"] = ok[0] if ok else ""
    for k in ("allowed_domains", "blocked_domains"):
        if k in out:
            out[k] = [d.lower().removeprefix("https://").removeprefix("http://").split("/")[0] for d in out[k]]
    return out


def _vars(v: dict[str, Any]) -> dict[str, Any]:
    if len(v) > 100:
        raise HTTPException(400, "Too many variables (max 100)")
    return {str(k)[:80]: (val if isinstance(val, (int, float, bool)) else str(val)[:2000]) for k, val in v.items()}


@router.get("", response_model=list[ProjectOut])
async def list_projects(include_archived: bool = False, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    stmt = select(Project).where(Project.org_id == ctx.org_id).order_by(Project.created_at)
    if not include_archived:
        stmt = stmt.where(Project.archived.is_(False))
    return (await session.execute(stmt)).scalars().all()


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectIn, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    count = (await session.execute(select(func.count()).select_from(Project).where(Project.org_id == ctx.org_id))).scalar_one()
    if count >= 500:
        raise HTTPException(400, "Project limit reached")
    settings = {"web_access": True, "memory_enabled": True, **(await clean_settings(session, ctx, body.settings))}
    p = Project(org_id=ctx.org_id, name=body.name, description=body.description, context=body.context, variables=_vars(body.variables), settings=settings)
    session.add(p)
    await audit(session, action="project.create", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="project", target_id=p.id, commit=False)
    await session.commit()
    return p


@router.get("/{project_id}", response_model=ProjectOut)
async def read_project(project_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    return await get_project(session, project_id, ctx.org_id)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: str, body: ProjectUpdate, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    p = await get_project(session, project_id, ctx.org_id)
    data = body.model_dump(exclude_none=True)
    if "settings" in data:
        p.settings = {**(p.settings or {}), **(await clean_settings(session, ctx, data.pop("settings")))}
    if "variables" in data:
        p.variables = _vars(data.pop("variables"))
    for k, v in data.items():
        setattr(p, k, v)
    await session.commit()
    return p


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    p = await get_project(session, project_id, ctx.org_id)
    count = (await session.execute(select(func.count()).select_from(Project).where(Project.org_id == ctx.org_id))).scalar_one()
    if count <= 1:
        raise HTTPException(400, "An organization needs at least one project")
    await session.execute(delete(Document).where(Document.org_id == ctx.org_id, Document.owner_type == "project", Document.owner_id == p.id))
    await session.execute(delete(Memory).where(Memory.org_id == ctx.org_id, Memory.project_id == p.id))
    await session.delete(p)
    await audit(session, action="project.delete", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="project", target_id=project_id)
