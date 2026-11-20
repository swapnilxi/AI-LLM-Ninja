"""Scheduler API: schedules (cron / interval / one-time / webhook / manual), the scheduling assistant and the agenda."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import pick_agent
from app.core.config import settings
from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_org_ctx, get_project, get_visible, require_role, visible
from app.core.security import decrypt, encrypt, generate_webhook_token, sha256_hex
from app.modules.agents.models import Agent
from app.modules.runs.service import TARGETS
from app.modules.scheduler import assistant as schedule_ai
from app.modules.scheduler.models import Automation
from app.modules.scheduler.schemas import AutomationIn, AutomationOut, AutomationUpdate, ScheduleChatIn, ScheduleDraftIn, UpcomingRun
from app.modules.scheduler.service import compute_next_run, fire, occurrences, validate_cron

router = APIRouter(prefix="/schedules", tags=["scheduler"])


def _out(a: Automation, show_url: bool = True) -> AutomationOut:
    out = AutomationOut.model_validate(a)
    if a.trigger_type == "webhook" and a.webhook_token_enc and show_url:
        out.webhook_url = f"{settings.public_base_url.rstrip('/')}/api/hooks/{decrypt(a.webhook_token_enc)}"
    return out


async def _validate(session: AsyncSession, ctx: OrgContext, a: Automation) -> None:
    await get_visible(session, TARGETS[a.target_type], a.target_id, ctx.org_id)
    if a.trigger_type == "schedule":
        if not a.cron or not validate_cron(a.cron):
            raise HTTPException(400, "Invalid cron expression (e.g. '0 9 * * 1-5')")
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(a.timezone or "UTC")
        except Exception as exc:
            raise HTTPException(400, "Unknown timezone") from exc
    if a.trigger_type == "interval" and (a.interval_minutes or 0) < 5:
        raise HTTPException(400, "Interval must be at least 5 minutes")
    if a.trigger_type == "once":
        if not a.run_at:
            raise HTTPException(400, "Pick a date and time for a one-time schedule")
        if a.run_at.tzinfo is None:
            a.run_at = a.run_at.replace(tzinfo=timezone.utc)
        # a schedule that already ran keeps its (past) time; a new or rescheduled one must be in the future
        if a.run_at <= datetime.now(timezone.utc) and (a.last_run_at is None or a.last_run_at < a.run_at):
            raise HTTPException(400, "The run time must be in the future")
    if a.trigger_type == "webhook" and not a.webhook_token_enc:
        token = generate_webhook_token()
        a.webhook_token_enc = encrypt(token)
        a.webhook_token_hash = sha256_hex(token)
    a.next_run_at = compute_next_run(a)


async def _get(session: AsyncSession, ctx: OrgContext, auto_id: str) -> Automation:
    a = await session.get(Automation, auto_id)
    if not a or a.org_id != ctx.org_id:
        raise HTTPException(404, "Schedule not found")
    return a


@router.get("", response_model=list[AutomationOut])
async def list_automations(project_id: str | None = None, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    stmt = select(Automation).where(Automation.org_id == ctx.org_id)
    if project_id:
        stmt = stmt.where(Automation.project_id == project_id)
    rows = (await session.execute(stmt.order_by(Automation.created_at.desc()))).scalars().all()
    return [_out(a, ctx.has("member")) for a in rows]


@router.post("", response_model=AutomationOut, status_code=201)
async def create_automation(body: AutomationIn, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    await get_project(session, body.project_id, ctx.org_id)
    count = (await session.execute(select(func.count()).select_from(Automation).where(Automation.org_id == ctx.org_id))).scalar_one()
    if count >= 200:
        raise HTTPException(400, "Schedule limit reached")
    a = Automation(org_id=ctx.org_id, created_by=ctx.user.id, **body.model_dump())
    await _validate(session, ctx, a)
    session.add(a)
    await audit(session, action="automation.create", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="automation", target_id=a.id, commit=False)
    await session.commit()
    return _out(a)


@router.post("/draft")
async def draft_automation(body: ScheduleDraftIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Plain English -> a draft schedule in one shot (nothing is saved; the form page pre-fills from this)."""
    project = await get_project(session, body.project_id, ctx.org_id)
    agent = await pick_agent(session, ctx, project, body.agent_id)
    tz = body.timezone or (project.settings or {}).get("timezone") or "UTC"
    out = await schedule_ai.draft(session, ctx.org, body.text, tz)
    return {**out, "project_id": project.id, "target_type": "agent", "target_id": agent.id, "target_name": agent.name, "input": {"task": out["task"]}}


@router.post("/assistant")
async def schedule_assistant(body: ScheduleChatIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Schedule by chatting: one assistant turn. The client keeps the conversation + draft; nothing is saved here."""
    project = await get_project(session, body.project_id, ctx.org_id)
    default = await pick_agent(session, ctx, project, None)
    rows = (await session.execute(select(Agent).where(visible(Agent, ctx.org_id)).order_by(Agent.org_id.is_(None), Agent.name).limit(100))).scalars().all()
    agents = [schedule_ai.AgentRef(a.id, a.name, a.description or "") for a in rows]
    tz = body.timezone or (project.settings or {}).get("timezone") or "UTC"
    out = await schedule_ai.converse(
        session, ctx.org, messages=[m.model_dump() for m in body.messages], draft_in=body.draft,
        agents=agents, default_agent=schedule_ai.AgentRef(default.id, default.name, default.description or ""), tz=tz,
    )
    if out["draft"]:
        out["draft"] = {**out["draft"], "project_id": project.id, "input": {"task": out["draft"]["task"]}}
    return out


@router.get("/upcoming", response_model=list[UpcomingRun])
async def upcoming_runs(
    project_id: str | None = None,
    days: int = Query(7, ge=1, le=62),
    limit: int = Query(100, ge=1, le=500),
    ctx: OrgContext = Depends(get_org_ctx),
    session: AsyncSession = Depends(get_session),
):
    """Agenda: every run the enabled schedules will start in the next `days` days, soonest first."""
    stmt = select(Automation).where(Automation.org_id == ctx.org_id, Automation.enabled.is_(True), Automation.next_run_at.is_not(None))
    if project_id:
        stmt = stmt.where(Automation.project_id == project_id)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    items: list[UpcomingRun] = []
    for a in (await session.execute(stmt)).scalars().all():
        for at in occurrences(a, now, end, limit):
            items.append(UpcomingRun(automation_id=a.id, name=a.name, at=at, trigger_type=a.trigger_type, target_type=a.target_type, target_id=a.target_id))
    return sorted(items, key=lambda i: i.at)[:limit]


@router.get("/{auto_id}", response_model=AutomationOut)
async def read_automation(auto_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    return _out(await _get(session, ctx, auto_id), ctx.has("member"))


@router.patch("/{auto_id}", response_model=AutomationOut)
async def update_automation(auto_id: str, body: AutomationUpdate, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    a = await _get(session, ctx, auto_id)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(a, k, v)
    await _validate(session, ctx, a)
    await session.commit()
    return _out(a)


@router.delete("/{auto_id}", status_code=204)
async def delete_automation(auto_id: str, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    a = await _get(session, ctx, auto_id)
    await session.delete(a)
    await audit(session, action="automation.delete", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="automation", target_id=auto_id)


@router.post("/{auto_id}/run")
async def run_now(auto_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    await _get(session, ctx, auto_id)
    run_id = await fire(auto_id, trigger="manual")
    if not run_id:
        raise HTTPException(429, "Run could not be started (limits reached)")
    return {"run_id": run_id}


@router.post("/{auto_id}/rotate-token", response_model=AutomationOut)
async def rotate_token(auto_id: str, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    a = await _get(session, ctx, auto_id)
    if a.trigger_type != "webhook":
        raise HTTPException(400, "Not a webhook schedule")
    token = generate_webhook_token()
    a.webhook_token_enc = encrypt(token)
    a.webhook_token_hash = sha256_hex(token)
    await audit(session, action="automation.rotate_token", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="automation", target_id=a.id, commit=False)
    await session.commit()
    return _out(a)
