from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import OrgContext, get_org_ctx, visible
from ..engine.connectors.registry import CONNECTORS
from ..engine.orchestrator import STYLES
from ..engine.runs import daily_limit, tokens_used_today
from ..engine.tools.builtin import BUILTINS
from ..engine.workflow import NODE_TYPES
from ..models import Agent, Automation, Connection, Document, Memory, Project, Run, Skill, Team, Tool, Workflow
from ..schemas import RunOut

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(project_id: str | None = None, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    async def count(model: Any, *where: Any) -> int:
        return (await session.execute(select(func.count()).select_from(model).where(*where))).scalar_one()

    run_filter = [Run.org_id == ctx.org_id] + ([Run.project_id == project_id] if project_id else [])
    since = datetime.now(timezone.utc) - timedelta(days=13)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (await session.execute(select(Run.created_at, Run.status, Run.total_tokens).where(*run_filter, Run.created_at >= since))).all()
    days: dict[str, dict[str, int]] = defaultdict(lambda: {"succeeded": 0, "failed": 0, "other": 0, "tokens": 0})
    for created, status, tokens in rows:
        d = days[created.date().isoformat()]
        d["succeeded" if status == "succeeded" else "failed" if status == "failed" else "other"] += 1
        d["tokens"] += tokens or 0
    series = []
    for i in range(14):
        day = (since + timedelta(days=i)).date().isoformat()
        series.append({"date": day, **days[day]})
    week = [r for r in rows if r[0] >= datetime.now(timezone.utc) - timedelta(days=7)]
    finished = [r for r in week if r[1] in ("succeeded", "failed")]
    top = (
        await session.execute(
            select(Run.target_type, Run.target_id, Run.target_name, func.count().label("n"))
            .where(*run_filter, Run.created_at >= since)
            .group_by(Run.target_type, Run.target_id, Run.target_name)
            .order_by(func.count().desc())
            .limit(5)
        )
    ).all()
    recent = (await session.execute(select(Run).where(*run_filter).order_by(Run.created_at.desc()).limit(8))).scalars().all()
    return {
        "counts": {
            "agents": await count(Agent, visible(Agent, ctx.org_id)),
            "teams": await count(Team, visible(Team, ctx.org_id)),
            "workflows": await count(Workflow, visible(Workflow, ctx.org_id)),
            "skills": await count(Skill, visible(Skill, ctx.org_id)),
            "tools": await count(Tool, visible(Tool, ctx.org_id)),
            "projects": await count(Project, Project.org_id == ctx.org_id, Project.archived.is_(False)),
            "connections": await count(Connection, Connection.org_id == ctx.org_id),
            "automations_active": await count(Automation, Automation.org_id == ctx.org_id, Automation.enabled.is_(True)),
            "documents": await count(Document, Document.org_id == ctx.org_id),
            "memories": await count(Memory, Memory.org_id == ctx.org_id),
            "running": await count(Run, *run_filter, Run.status.in_(["queued", "running"])),
        },
        "week": {
            "runs": len(week),
            "success_rate": round(100 * sum(1 for r in finished if r[1] == "succeeded") / len(finished), 1) if finished else None,
            "tokens": sum(r[2] or 0 for r in week),
        },
        "tokens_today": await tokens_used_today(session, ctx.org_id),
        "daily_token_limit": daily_limit(ctx.org),
        "series": series,
        "top_targets": [{"target_type": t, "target_id": i, "name": n, "runs": c} for t, i, n, c in top],
        "recent_runs": [RunOut.model_validate(r) for r in recent],
    }


@router.get("/catalog")
async def catalog(ctx: OrgContext = Depends(get_org_ctx)) -> dict[str, Any]:
    return {
        "styles": [{"key": k, "description": v} for k, v in STYLES.items()],
        "node_types": sorted(NODE_TYPES),
        "builtin_tools": [
            {"key": b.key, "name": b.display_name, "description": b.description, "category": b.category, "parameters": b.parameters} for b in BUILTINS.values()
        ],
        "connectors": [c.describe() for c in CONNECTORS.values()],
    }
