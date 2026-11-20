"""Skills API (library resource)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import clean_refs
from app.core.crud import LIMIT_PER_ORG, crud_router
from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_org_ctx, require_role, visible
from app.modules.skills import install as skill_install
from app.modules.skills.commands import COMMAND_NAME_RE, RESERVED
from app.modules.skills.install import parse_skill_md
from app.modules.skills.models import Skill
from app.modules.skills.schemas import SkillImport, SkillIn, SkillInstall, SkillOut
from app.modules.skills.templates import BY_KEY as TEMPLATE_BY_KEY
from app.modules.skills.templates import TEMPLATES
from app.modules.tools.models import Tool


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


async def install_from_command(
    session: AsyncSession, ctx: OrgContext, request: Request, command: str, paths: list[str] | None = None, extra_tags: list[str] | None = None
) -> dict[str, Any]:
    """Install the skills named by an `npx skills add ...` command (instructions only, nothing is executed).

    Re-installing a skill updates it. Raises HTTPException(400) for user-facing problems. Shared with the Discover hub.
    """
    try:
        src = skill_install.parse_command(command)
        items = skill_install.items_from_paths(src, paths) if paths else await skill_install.list_skills(src)
        seen: set[str] = set()  # repos sometimes ship the same skill in several folders; keep the first
        items = [i for i in items if not (i["name"].lower() in seen or seen.add(i["name"].lower()))]
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
        tags = ["installed", f"src:{src.label}"[:40], *(extra_tags or [])]
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


@skills_router.post("/install")
async def install_skills(body: SkillInstall, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Install the skills named by an `npx skills add ...` command. Re-installing a skill updates it."""
    return await install_from_command(session, ctx, request, body.command, body.paths)

ROUTERS = [skills_extra_router, skills_router]
