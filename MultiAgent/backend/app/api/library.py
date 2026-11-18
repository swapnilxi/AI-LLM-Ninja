"""Library CRUD: agents, skills, tools, teams, workflows.

All are project-independent. `scope=org` items belong to the current org;
`scope=global` items (platform admins only) are shared with every org and can be
duplicated into an org to customise.
"""

import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import OrgContext, audit, get_org_ctx, get_project, get_visible, get_writable, require_role, visible
from ..engine.context import OrgSnap, ProjectSnap, RunContext
from ..engine.llm.registry import PROVIDERS
from ..engine.tools.builtin import BUILTINS
from ..engine.tools.registry import runtime_for
from ..engine.workflow import NODE_TYPES, validate_graph
from ..models import Agent, Document, Lesson, Memory, Skill, Team, Tool, Workflow, new_id
from ..schemas import (
    AgentIn,
    AgentOut,
    SkillImport,
    SkillIn,
    SkillInstall,
    SkillOut,
    TeamIn,
    TeamOut,
    ToolIn,
    ToolOut,
    ToolTest,
    WorkflowIn,
    WorkflowOut,
)
from ..engine import skill_install
from ..engine.commands import COMMAND_NAME_RE, RESERVED
from ..engine.skill_install import parse_skill_md
from ..engine.skill_templates import BY_KEY as TEMPLATE_BY_KEY
from ..engine.skill_templates import TEMPLATES
from .common import check_agent_ids, check_team_ids, clean_refs, scope_org_id

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


# ============================================================================ agents
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


# ============================================================================ skills
async def prep_skill(session, ctx, data, owner):
    cmd = data.get("command")
    if cmd:
        if not COMMAND_NAME_RE.match(cmd):
            raise HTTPException(400, "Command must be 1-40 chars: lowercase letters, digits, - or _")
        if cmd in RESERVED:
            raise HTTPException(400, f"/{cmd} is reserved")
        clash = (
            await session.execute(select(Skill.id, Skill.name).where(Skill.command == cmd, visible(Skill, ctx.org_id), Skill.id != data.get("_self_id", "")))
        ).first()
        if clash:
            raise HTTPException(409, f"/{cmd} is already used by the skill '{clash.name}'")
    data["argument_hint"] = (data.get("argument_hint") or "").strip()
    return await clean_refs(session, ctx, data, owner)


skills_extra_router = APIRouter(prefix="/skills", tags=["skill"])


@skills_extra_router.get("/commands")
async def list_commands(ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    """Slash commands available in this org (org skills shadow global ones)."""
    rows = (await session.execute(select(Skill).where(Skill.command.is_not(None), visible(Skill, ctx.org_id)))).scalars().all()
    rows = sorted(rows, key=lambda s: (s.command, s.org_id is None))
    seen, out = set(), []
    for s in rows:
        if s.command in seen:
            continue
        seen.add(s.command)
        out.append({"command": s.command, "skill_id": s.id, "name": s.name, "description": s.description, "argument_hint": s.argument_hint or "", "scope": "global" if s.org_id is None else "org"})
    return out


@skills_extra_router.get("/templates")
async def list_templates(ctx: OrgContext = Depends(get_org_ctx)):
    return [{k: v for k, v in t.items() if k != "instructions"} | {"preview": t["instructions"][:240]} for t in TEMPLATES]


@skills_extra_router.post("/templates/{key}", response_model=SkillOut, status_code=201)
async def add_template(key: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    t = TEMPLATE_BY_KEY.get(key)
    if not t:
        raise HTTPException(404, "Template not found")
    builtin = dict((await session.execute(select(Tool.builtin_key, Tool.id).where(Tool.kind == "builtin"))).all())
    cmd = t["command"]
    taken = (await session.execute(select(Skill.id).where(Skill.command == cmd, visible(Skill, ctx.org_id)))).first()
    skill = Skill(
        org_id=ctx.org_id, name=t["name"], description=t["description"], instructions=t["instructions"],
        tool_ids=[builtin[k] for k in t["tools"] if k in builtin], tags=["template", t["category"].lower()],
        command=None if taken else cmd, argument_hint=t["argument_hint"], command_template=t["command_template"], created_by=ctx.user.id,
    )
    session.add(skill)
    await session.commit()
    return skill


skills_router = crud_router("/skills", Skill, SkillIn, SkillOut, prep_skill, "skill")


@skills_router.post("/import", response_model=SkillOut, status_code=201)
async def import_skill(body: SkillImport, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Import a SKILL.md (YAML-ish front matter with name/description + markdown body)."""
    name, desc, instructions = parse_skill_md(body.markdown)
    skill = Skill(org_id=ctx.org_id, name=name[:120], description=desc[:4000], instructions=instructions[:50000], created_by=ctx.user.id)
    session.add(skill)
    await session.commit()
    return skill


@skills_router.post("/install/preview")
async def install_preview(body: SkillInstall, ctx: OrgContext = Depends(require_role("member"))):
    """Resolve an `npx skills add …` command to the SKILL.md files it would install (nothing is saved)."""
    try:
        src = skill_install.parse_command(body.command)
        items = await skill_install.list_skills(src)
    except skill_install.InstallError as exc:
        raise HTTPException(400, str(exc))
    return {"source": src.label, "ref": src.ref, "items": items}


@skills_router.post("/install")
async def install_skills(body: SkillInstall, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Install the skills named by an `npx skills add …` command. Re-installing a skill updates it."""
    try:
        src = skill_install.parse_command(body.command)
        items = await skill_install.list_skills(src)
        if body.paths:
            items = [i for i in items if i["path"] in set(body.paths)]
        if not items:
            raise skill_install.InstallError("Nothing selected to install.")
        if len(items) > skill_install.MAX_SKILLS_PER_INSTALL:
            raise skill_install.InstallError(f"This source has {len(items)} skills; pick up to {skill_install.MAX_SKILLS_PER_INSTALL} (add --skill <name>).")
        texts = [(i, await skill_install.fetch_skill(src, i["path"])) for i in items]
    except skill_install.InstallError as exc:
        raise HTTPException(400, str(exc))
    total = (await session.execute(select(func.count()).select_from(Skill).where(Skill.org_id == ctx.org_id))).scalar_one()
    results = []
    for item, text in texts:
        name, desc, instructions = parse_skill_md(text, item["name"])
        name = name[:120]
        existing = (await session.execute(select(Skill).where(Skill.org_id == ctx.org_id, Skill.name == name))).scalars().first()
        tags = ["installed", f"src:{src.label}"[:40]]
        if existing:
            existing.description, existing.instructions = desc[:4000], instructions[:50000]
            existing.tags = list(dict.fromkeys([*(existing.tags or []), *tags]))
            skill, status = existing, "updated"
        else:
            if total >= LIMIT_PER_ORG:
                raise HTTPException(400, "Skill limit reached")
            skill = Skill(org_id=ctx.org_id, name=name, description=desc[:4000], instructions=instructions[:50000], tags=tags, created_by=ctx.user.id)
            session.add(skill)
            total += 1
            status = "installed"
        await session.flush()
        results.append({"id": skill.id, "name": skill.name, "status": status, "path": item["path"]})
    await audit(session, action="skill.install", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="skill", target_id=src.label, commit=False)
    await session.commit()
    return {"source": src.label, "results": results}


# ============================================================================ tools
async def prep_tool(session, ctx, data, owner):
    cfg = data.get("config") or {}
    if data["kind"] == "http":
        url = str(cfg.get("url", ""))
        if not url.startswith(("https://", "http://")):
            raise HTTPException(400, "HTTP tools need config.url starting with http(s)://")
        cfg["method"] = str(cfg.get("method") or "GET").upper()
        if cfg["method"] not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            raise HTTPException(400, "Unsupported HTTP method")
        if not isinstance(cfg.get("headers") or {}, dict) or not isinstance(cfg.get("query") or {}, dict):
            raise HTTPException(400, "headers and query must be objects")
    elif data["kind"] == "agent":
        await check_agent_ids(session, ctx, [cfg.get("agent_id", "")])
        if not data["parameters"].get("properties"):
            data["parameters"] = {"type": "object", "properties": {"task": {"type": "string", "description": "Task for the agent"}}, "required": ["task"]}
    if data["name"] in BUILTINS:
        raise HTTPException(400, "That name is reserved for a built-in tool")
    data["config"] = cfg
    return data


tools_router = crud_router("/tools", Tool, ToolIn, ToolOut, prep_tool, "tool")


@tools_router.post("/{tool_id}/test")
async def test_tool(tool_id: str, body: ToolTest, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    tool = await get_visible(session, Tool, tool_id, ctx.org_id)
    project = await get_project(session, body.project_id, ctx.org_id)
    rt = runtime_for(tool)
    if rt is None:
        raise HTTPException(400, "Tool cannot be executed")
    rctx = RunContext(run_id=new_id("test"), org=OrgSnap.of(ctx.org), project=ProjectSnap.of(project), user_id=ctx.user.id, trigger="test")
    from ..engine.tools.base import validate_args

    if err := validate_args(rt.parameters, body.arguments):
        return {"ok": False, "output": err}
    if rt.category == "web" and not rctx.web_access:
        return {"ok": False, "output": "Web access is disabled for this project"}
    res = await rt.handler(body.arguments, rctx)
    return {"ok": not res.is_error, "output": res.content[:20000]}


# ============================================================================ teams
async def prep_team(session, ctx, data, owner):
    ids = [m["agent_id"] for m in data.get("members") or []]
    extra = [data.get("manager_agent_id"), (data.get("config") or {}).get("aggregator_agent_id"), (data.get("config") or {}).get("router_agent_id")]
    await check_agent_ids(session, ctx, ids + [i for i in extra if i])
    if data["style"] == "supervisor" and not data.get("manager_agent_id"):
        raise HTTPException(400, "Supervisor teams need a manager agent")
    if not ids:
        raise HTTPException(400, "Add at least one member")
    cfg = data.get("config") or {}
    data["config"] = {
        k: cfg[k] for k in ("max_rounds", "termination_keyword", "aggregator_agent_id", "router_agent_id", "max_concurrency") if cfg.get(k) not in (None, "")
    }
    return data


teams_router = crud_router("/teams", Team, TeamIn, TeamOut, prep_team, "team")


# ============================================================================ workflows
async def prep_workflow(session, ctx, data, owner):
    graph = data.get("graph") or {"nodes": [], "edges": []}
    nodes = graph.get("nodes") or []
    if len(nodes) > 60:
        raise HTTPException(400, "Workflows are limited to 60 nodes")
    agent_ids = [(n.get("data") or {}).get("agent_id") for n in nodes if n.get("type") == "agent"]
    team_ids = [(n.get("data") or {}).get("team_id") for n in nodes if n.get("type") == "team"]
    await check_agent_ids(session, ctx, [i for i in agent_ids if i])
    await check_team_ids(session, ctx, [i for i in team_ids if i])
    for n in nodes:
        if n.get("type") not in NODE_TYPES:
            raise HTTPException(400, f"Unknown node type '{n.get('type')}'")
    data["graph"] = {"nodes": nodes, "edges": graph.get("edges") or [], "viewport": graph.get("viewport")}
    return data


workflows_router = crud_router("/workflows", Workflow, WorkflowIn, WorkflowOut, prep_workflow, "workflow")


@workflows_router.post("/validate")
async def validate_workflow(body: WorkflowIn, ctx: OrgContext = Depends(get_org_ctx)):
    errors = validate_graph(body.graph)
    return {"valid": not errors, "errors": errors}


ROUTERS = [agents_router, skills_extra_router, skills_router, tools_router, teams_router, workflows_router]
