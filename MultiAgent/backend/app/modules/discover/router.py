"""Discover hub: one-click install of curated skill packs, popular MCP servers and knowledge docs, optionally at project level.

"Project level" means attaching to the project: its skills, connectors and documents then apply to every agent that runs there
(see engine/runner.py and engine/tools/registry.py). Installing never executes third-party code.
"""
from __future__ import annotations

import asyncio
import shlex
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_org_ctx, get_project, require_role
from app.core.security import decrypt_json, encrypt_json
from app.modules.connectors.models import Connection
from app.modules.connectors.registry import CONNECTORS, connection_config
from app.modules.connectors.router import _out as connection_out
from app.modules.discover import catalog as hub
from app.modules.discover.schemas import HubKnowledgeInstall, HubMcpInstall, HubSkillInstall
from app.modules.knowledge.models import Document
from app.modules.knowledge.router import document_from_url
from app.modules.knowledge.schemas import DocumentFromUrl
from app.modules.projects.models import Project
from app.modules.skills import search as skill_search
from app.modules.skills.install import InstallError
from app.modules.skills.models import Skill
from app.modules.skills.router import install_from_command

router = APIRouter(prefix="/discover", tags=["discover"])
MAX_PROJECT_SKILLS = 50


def _merge_ids(project: Project, key: str, new_ids: list[str]) -> bool:
    """Append ids to project.settings[key]. Returns True if the project now has all of them."""
    cur = list((project.settings or {}).get(key) or [])
    merged = list(dict.fromkeys([*cur, *new_ids]))
    if key == "skill_ids" and len(merged) > MAX_PROJECT_SKILLS:
        raise HTTPException(400, f"A project can have at most {MAX_PROJECT_SKILLS} skills attached. Remove some in the project settings first.")
    project.settings = {**(project.settings or {}), key: merged}
    return True


def _pack_tag(pack_id: str) -> str:
    return f"pack:{pack_id}"


async def _find_skills_playbook(session: AsyncSession) -> Skill | None:
    return (await session.execute(select(Skill).where(Skill.org_id.is_(None), Skill.name == hub.BUILTIN_FIND_SKILLS).limit(1))).scalars().first()


@router.get("")
async def catalog(project_id: str | None = None, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    project = await get_project(session, project_id, ctx.org_id) if project_id else None
    p_set = (project.settings or {}) if project else {}
    attached_skills, attached_conns = set(p_set.get("skill_ids") or []), set(p_set.get("connection_ids") or [])

    org_skills = (await session.execute(select(Skill).where(Skill.org_id == ctx.org_id))).scalars().all()
    by_pack: dict[str, list[Skill]] = {}
    for s in org_skills:
        for t in s.tags or []:
            if isinstance(t, str) and t.startswith("pack:"):
                by_pack.setdefault(t[5:], []).append(s)
    playbook = await _find_skills_playbook(session)

    packs = []
    for p in hub.SKILL_PACKS:
        rows = [playbook] if p.get("builtin") and playbook else by_pack.get(p["id"], [])
        ids = [r.id for r in rows]
        packs.append(
            {
                **{k: v for k, v in p.items() if k not in ("paths", "builtin")},
                "installed": bool(ids),
                "skill_ids": ids,
                "instruction_chars": sum(len(r.instructions or "") for r in rows),
                "attached": (bool(ids) and all(i in attached_skills for i in ids)) if project else None,
            }
        )

    conns = (await session.execute(select(Connection).where(Connection.org_id == ctx.org_id, Connection.connector_key == "mcp"))).scalars().all()
    by_url = {(c.public_config or {}).get("url"): c for c in conns}
    servers = []
    for m in hub.MCP_SERVERS:
        c = by_url.get(m["url"])
        servers.append({**m, "connection_id": c.id if c else None, "status": c.status if c else None, "attached": (c.id in attached_conns) if (c and project) else (False if project else None)})

    docs = []
    if project:
        urls = set((await session.execute(select(Document.source_ref).where(Document.org_id == ctx.org_id, Document.owner_type == "project", Document.owner_id == project.id))).scalars().all())
    else:
        urls = set()
    for k in hub.KNOWLEDGE_DOCS:
        docs.append({**{x: y for x, y in k.items() if x != "url"}, "installed": k["url"] in urls if project else None})

    return {"skills": packs, "mcp": servers, "knowledge": docs}


@router.get("/skills/search")
async def search_registry(q: str, limit: int = 12, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    """Search the public skills.sh registry (most-installed first)."""
    try:
        rows = await skill_search.search_registry(q, limit)
        error = None
    except InstallError as exc:
        rows, error = [], str(exc)
    # installed = this exact skill: same name, and it came from this source (a repo can hold many skills)
    mine = (await session.execute(select(Skill.name, Skill.tags).where(Skill.org_id == ctx.org_id))).all()
    have = {(f"src:{src}"[:40], name.lower()) for name, tags in mine for src in [t[4:] for t in (tags or []) if isinstance(t, str) and t.startswith("src:")]}
    have |= {(t, name.lower()) for name, tags in mine for t in (tags or []) if isinstance(t, str) and t.startswith("src:")}
    return {
        "results": [{**r, "ref": f"{r['source']}@{r['skill']}", "installed": (f"src:{r['source']}"[:40], r["skill"].lower()) in have} for r in rows],
        "error": error,
    }


@router.post("/skills/install")
async def install_skill(body: HubSkillInstall, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    project = await get_project(session, body.project_id, ctx.org_id) if body.project_id else None
    if body.pack_id:
        pack = hub.get_pack(body.pack_id)
        if not pack:
            raise HTTPException(404, "Unknown skill pack")
        if pack.get("builtin"):
            row = await _find_skills_playbook(session)
            if not row:
                raise HTTPException(500, "The built-in Find Skills playbook is missing; restart the server to re-seed it.")
            result: dict[str, Any] = {"source": "built-in", "results": [{"id": row.id, "name": row.name, "status": "available"}]}
        else:
            result = await install_from_command(session, ctx, request, pack["command"], pack.get("paths"), [_pack_tag(pack["id"])])
    elif body.source and body.skill:
        if not hub.SOURCE_RE.match(body.source) or not hub.SKILL_NAME_RE.match(body.skill):
            raise HTTPException(400, "Use owner/repo and a plain skill name.")
        result = await install_from_command(session, ctx, request, f"npx skills add {body.source} --skill {shlex.quote(body.skill)}", None, ["registry"])
    else:
        raise HTTPException(400, "Give a pack_id, or source and skill")
    attached = False
    if project:
        attached = _merge_ids(project, "skill_ids", [r["id"] for r in result["results"]])
        await session.commit()
    return {**result, "attached": attached, "project_id": project.id if project else None}


@router.post("/mcp/install")
async def install_mcp(body: HubMcpInstall, request: Request, ctx: OrgContext = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    server = hub.get_mcp(body.server_id)
    if not server:
        raise HTTPException(404, "Unknown server")
    project = await get_project(session, body.project_id, ctx.org_id) if body.project_id else None
    token = body.token.strip()
    if server["auth"] == "bearer" and not token:
        raise HTTPException(400, f"{server['name']} needs a {server.get('token_label', 'token')}.")
    conns = (await session.execute(select(Connection).where(Connection.org_id == ctx.org_id, Connection.connector_key == "mcp"))).scalars().all()
    conn = next((c for c in conns if (c.public_config or {}).get("url") == server["url"]), None)
    if conn:  # already connected: reuse it (and refresh the token if a new one was given)
        if token:
            conn.config_enc = encrypt_json({**decrypt_json(conn.config_enc), "auth_token": token})
            conn.status = "unknown"
    else:
        if len(conns) >= 100:
            raise HTTPException(400, "Connection limit reached")
        conn = Connection(
            org_id=ctx.org_id, connector_key="mcp", name=(body.name.strip() or server["name"])[:120], public_config={"url": server["url"]},
            config_enc=encrypt_json({"auth_token": token} if token else {}), enabled_tools=[], enabled=True, created_by=ctx.user.id,
        )
        session.add(conn)
    await session.flush()
    await audit(session, action="connection.install", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="connection", target_id=conn.id, details={"server": server["id"]}, commit=False)
    try:
        ok, message = await asyncio.wait_for(CONNECTORS["mcp"].test(connection_config(conn)), timeout=30)
    except asyncio.TimeoutError:
        ok, message = False, "The server did not answer within 30 seconds."
    conn.status = "ok" if ok else "error"
    attached = False
    if project:
        attached = _merge_ids(project, "connection_ids", [conn.id])
    await session.commit()
    return {"connection": connection_out(conn), "test": {"ok": ok, "message": message}, "attached": attached, "project_id": project.id if project else None}


@router.post("/knowledge/install", status_code=201)
async def install_knowledge(body: HubKnowledgeInstall, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    item = hub.get_knowledge(body.item_id)
    if not item:
        raise HTTPException(404, "Unknown document")
    project = await get_project(session, body.project_id, ctx.org_id)
    dup = (
        await session.execute(
            select(Document.id).where(Document.org_id == ctx.org_id, Document.owner_type == "project", Document.owner_id == project.id, Document.source_ref == item["url"])
        )
    ).first()
    if dup:
        raise HTTPException(409, f"'{item['name']}' is already in this project's knowledge.")
    doc = await document_from_url(
        DocumentFromUrl(owner_type="project", owner_id=project.id, url=item["url"], title=item["name"], pinned=body.pinned), ctx, session
    )
    return {"id": doc.id, "title": doc.title, "chunk_count": doc.chunk_count}
