from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..deps import OrgContext, audit, get_org_ctx, get_project, get_visible, require_role
from ..engine import schedule_ai
from ..engine.runs import TARGETS
from ..engine.scheduler import compute_next_run, fire, validate_cron
from ..models import Automation
from ..schemas import AutomationIn, AutomationOut, AutomationUpdate, ScheduleDraftIn
from ..security import decrypt, encrypt, generate_webhook_token, sha256_hex
from .common import pick_agent

router = APIRouter(prefix="/automations", tags=["automations"])


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
    if a.trigger_type == "webhook" and not a.webhook_token_enc:
        token = generate_webhook_token()
        a.webhook_token_enc = encrypt(token)
        a.webhook_token_hash = sha256_hex(token)
    a.next_run_at = compute_next_run(a)


async def _get(session: AsyncSession, ctx: OrgContext, auto_id: str) -> Automation:
    a = await session.get(Automation, auto_id)
    if not a or a.org_id != ctx.org_id:
        raise HTTPException(404, "Automation not found")
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
        raise HTTPException(400, "Automation limit reached")
    a = Automation(org_id=ctx.org_id, created_by=ctx.user.id, **body.model_dump())
    await _validate(session, ctx, a)
    session.add(a)
    await audit(session, action="automation.create", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="automation", target_id=a.id, commit=False)
    await session.commit()
    return _out(a)


@router.post("/draft")
async def draft_automation(body: ScheduleDraftIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Scheduler with AI: plain English -> a draft automation (nothing is saved; the UI pre-fills the form from this)."""
    project = await get_project(session, body.project_id, ctx.org_id)
    agent = await pick_agent(session, ctx, project, body.agent_id)
    tz = body.timezone or (project.settings or {}).get("timezone") or "UTC"
    out = await schedule_ai.draft(session, ctx.org, body.text, tz)
    return {**out, "project_id": project.id, "target_type": "agent", "target_id": agent.id, "target_name": agent.name, "input": {"task": out["task"]}}


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
        raise HTTPException(400, "Not a webhook automation")
    token = generate_webhook_token()
    a.webhook_token_enc = encrypt(token)
    a.webhook_token_hash = sha256_hex(token)
    await audit(session, action="automation.rotate_token", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="automation", target_id=a.id, commit=False)
    await session.commit()
    return _out(a)
