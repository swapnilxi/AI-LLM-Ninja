"""Export / import library items as a portable JSON bundle (between orgs or installations).

Bundles reference items by their original id ("ref"); built-in tools are referenced as
"builtin:<key>". Connections (credentials) are never exported.
"""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import OrgContext, audit, require_role, visible
from ..engine.commands import COMMAND_NAME_RE, RESERVED
from ..engine.workflow import validate_graph
from ..models import Agent, Skill, Team, Tool, Workflow
from pydantic import ValidationError

from ..schemas import AgentIn, ExportIn, ImportIn, SkillIn, TeamIn, ToolIn, WorkflowIn
from .library import prep_agent, prep_skill, prep_team, prep_tool, prep_workflow

router = APIRouter(prefix="/library", tags=["import-export"])

FORMAT, VERSION = "agentforge.bundle", 1
MAX_ITEMS = 300
FIELDS = {
    "tools": ["name", "display_name", "description", "kind", "category", "parameters", "config", "enabled"],
    "skills": ["name", "description", "instructions", "tool_ids", "tags", "command", "argument_hint", "command_template"],
    "agents": ["name", "description", "avatar", "color", "provider", "model", "system_prompt", "temperature", "max_tokens", "max_steps", "effort", "tool_ids", "skill_ids", "settings", "tags"],
    "teams": ["name", "description", "style", "members", "manager_agent_id", "config"],
    "workflows": ["name", "description", "graph", "input_fields"],
}
MODELS = {"tools": Tool, "skills": Skill, "agents": Agent, "teams": Team, "workflows": Workflow}
SCHEMAS = {"tools": ToolIn, "skills": SkillIn, "agents": AgentIn, "teams": TeamIn, "workflows": WorkflowIn}


async def _load(session: AsyncSession, model: Any, ids: set[str], org_id: str) -> list[Any]:
    if not ids:
        return []
    return list((await session.execute(select(model).where(model.id.in_(ids), visible(model, org_id)))).scalars().all())


@router.post("/export")
async def export_bundle(body: ExportIn, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    want = {
        "workflows": set(body.workflow_ids), "teams": set(body.team_ids), "agents": set(body.agent_ids),
        "skills": set(body.skill_ids), "tools": set(body.tool_ids),
    }
    rows: dict[str, dict[str, Any]] = {k: {} for k in want}
    # resolve dependencies top-down until stable
    for _ in range(4):
        for kind in ("workflows", "teams", "agents", "skills", "tools"):
            for obj in await _load(session, MODELS[kind], want[kind] - set(rows[kind]), ctx.org_id):
                rows[kind][obj.id] = obj
        if not body.include_dependencies:
            break
        before = sum(len(v) for v in want.values())
        for wf in rows["workflows"].values():
            for n in (wf.graph or {}).get("nodes", []):
                d = n.get("data") or {}
                if d.get("agent_id"):
                    want["agents"].add(d["agent_id"])
                if d.get("team_id"):
                    want["teams"].add(d["team_id"])
                if d.get("tool_id"):
                    want["tools"].add(d["tool_id"])
        for t in rows["teams"].values():
            want["agents"].update(m.get("agent_id") for m in t.members or [] if m.get("agent_id"))
            want["agents"].update(x for x in [t.manager_agent_id, (t.config or {}).get("aggregator_agent_id"), (t.config or {}).get("router_agent_id")] if x)
        for a in rows["agents"].values():
            want["skills"].update(a.skill_ids or [])
            want["tools"].update(a.tool_ids or [])
        for sk in rows["skills"].values():
            want["tools"].update(sk.tool_ids or [])
        if sum(len(v) for v in want.values()) == before:
            break

    builtin_ref = {t.id: f"builtin:{t.builtin_key}" for t in rows["tools"].values() if t.kind == "builtin"}
    builtin_ref.update(
        {tid: f"builtin:{key}" for tid, key in (await session.execute(select(Tool.id, Tool.builtin_key).where(Tool.kind == "builtin"))).all()}
    )
    ref = lambda i: builtin_ref.get(i, i)  # noqa: E731

    items: dict[str, list[dict[str, Any]]] = {k: [] for k in FIELDS}
    for kind, objs in rows.items():
        for obj in objs.values():
            if kind == "tools" and obj.kind == "builtin":
                continue
            item = {"ref": obj.id, **{f: getattr(obj, f) for f in FIELDS[kind]}}
            if "tool_ids" in item:
                item["tool_ids"] = [ref(i) for i in item["tool_ids"] or []]
            items[kind].append(item)
    total = sum(len(v) for v in items.values())
    if total == 0:
        raise HTTPException(400, "Nothing to export")
    await audit(session, action="library.export", org_id=ctx.org_id, user_id=ctx.user.id, request=request, details={k: len(v) for k, v in items.items()})
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": ctx.org.name,
        "notes": ["App connections and secrets are not exported; re-attach connectors after import."],
        "items": items,
    }


@router.post("/import")
async def import_bundle(body: ImportIn, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    b = body.bundle
    if b.get("format") != FORMAT or int(b.get("version", 0)) > VERSION:
        raise HTTPException(400, "Not an AgentForge bundle (or from a newer version)")
    items = b.get("items") or {}
    if not isinstance(items, dict) or sum(len(items.get(k) or []) for k in FIELDS) > MAX_ITEMS:
        raise HTTPException(400, f"Bundle must contain at most {MAX_ITEMS} items")

    builtin = {f"builtin:{k}": i for k, i in (await session.execute(select(Tool.builtin_key, Tool.id).where(Tool.kind == "builtin"))).all()}
    ref_map: dict[str, str] = dict(builtin)
    m = lambda r: ref_map.get(r) if isinstance(r, str) else None  # noqa: E731
    created: list[dict[str, str]] = []

    async def unique_name(model: Any, name: str) -> str:
        existing = set((await session.execute(select(model.name).where(visible(model, ctx.org_id)))).scalars().all())
        if name not in existing:
            return name
        if model is Tool:
            i = 2
            while f"{name}_{i}"[:64] in existing:
                i += 1
            return f"{name}_{i}"[:64]
        return f"{name} (imported)"[:120]

    async def create(kind: str, raw: dict[str, Any], prep: Any) -> None:
        model = MODELS[kind]
        data = {f: raw.get(f) for f in FIELDS[kind] if raw.get(f) is not None}
        data["name"] = await unique_name(model, str(data.get("name") or kind[:-1]))
        try:  # same validation and limits as the regular API
            data = SCHEMAS[kind](**data).model_dump()
        except ValidationError as exc:
            err = exc.errors()[0]
            raise HTTPException(400, f"{kind[:-1]} '{data['name']}': {'.'.join(str(x) for x in err['loc'])} {err['msg']}") from exc
        data.pop("scope", None)
        data = await prep(session, ctx, data, ctx.org_id)
        obj = model(org_id=ctx.org_id, created_by=ctx.user.id, **data)
        session.add(obj)
        await session.flush()
        if raw.get("ref"):
            ref_map[str(raw["ref"])] = obj.id
        created.append({"type": kind[:-1], "id": obj.id, "name": obj.name})

    try:
        for raw in items.get("tools") or []:
            if raw.get("kind") not in ("http", "agent"):
                continue
            if raw.get("kind") == "agent":  # agent tools are linked after agents exist
                continue
            await create("tools", raw, prep_tool)
        for raw in items.get("skills") or []:
            raw = {**raw, "tool_ids": [x for x in (m(i) for i in raw.get("tool_ids") or []) if x]}
            cmd = (raw.get("command") or "").lower() or None
            if cmd and (not COMMAND_NAME_RE.match(cmd) or cmd in RESERVED or (await session.execute(select(Skill.id).where(Skill.command == cmd, visible(Skill, ctx.org_id)))).first()):
                cmd = None
            raw["command"] = cmd
            await create("skills", raw, prep_skill)
        for raw in items.get("agents") or []:
            raw = {
                **raw,
                "tool_ids": [x for x in (m(i) for i in raw.get("tool_ids") or []) if x],
                "skill_ids": [x for x in (m(i) for i in raw.get("skill_ids") or []) if x],
            }
            await create("agents", raw, prep_agent)
        for raw in items.get("tools") or []:
            if raw.get("kind") == "agent" and m((raw.get("config") or {}).get("agent_id")):
                await create("tools", {**raw, "config": {**raw["config"], "agent_id": m(raw["config"]["agent_id"])}}, prep_tool)
        for raw in items.get("teams") or []:
            cfg = dict(raw.get("config") or {})
            for k in ("aggregator_agent_id", "router_agent_id"):
                if cfg.get(k):
                    cfg[k] = m(cfg[k])
                    if not cfg[k]:
                        cfg.pop(k)
            members = [{**mem, "agent_id": m(mem.get("agent_id"))} for mem in raw.get("members") or [] if m(mem.get("agent_id"))]
            await create("teams", {**raw, "members": members, "manager_agent_id": m(raw.get("manager_agent_id")), "config": cfg}, prep_team)
        for raw in items.get("workflows") or []:
            graph = dict(raw.get("graph") or {})
            nodes = []
            for n in graph.get("nodes") or []:
                d = dict(n.get("data") or {})
                for k in ("agent_id", "team_id", "tool_id"):
                    if d.get(k):
                        d[k] = m(d[k]) or ""
                nodes.append({**n, "data": d})
            graph["nodes"] = nodes
            await create("workflows", {**raw, "graph": graph}, prep_workflow)
    except HTTPException as exc:
        await session.rollback()
        raise HTTPException(400, f"Import failed: {exc.detail}") from exc

    warnings = [f"Workflow '{c['name']}': {'; '.join(validate_graph((await session.get(Workflow, c['id'])).graph))}" for c in created if c["type"] == "workflow" and validate_graph((await session.get(Workflow, c["id"])).graph)]
    await audit(session, action="library.import", org_id=ctx.org_id, user_id=ctx.user.id, request=request, details={"created": len(created)}, commit=False)
    await session.commit()
    counts: dict[str, int] = {}
    for c in created:
        counts[c["type"]] = counts.get(c["type"], 0) + 1
    return {"created": counts, "items": created, "warnings": warnings}
