from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal, get_session
from ..deps import OrgContext, get_org_ctx, get_project, require_role
from ..engine import runs as run_engine
from ..engine.events import TERMINAL, bus
from ..models import Automation, Run, RunEvent
from ..ratelimit import client_ip, enforce
from ..schemas import RunCreate, RunEventOut, RunOut
from ..security import sha256_hex

router = APIRouter(prefix="/runs", tags=["runs"])
hooks_router = APIRouter(prefix="/hooks", tags=["webhooks"])


async def _run(session: AsyncSession, ctx: OrgContext, run_id: str) -> Run:
    run = await session.get(Run, run_id)
    if not run or run.org_id != ctx.org_id:
        raise HTTPException(404, "Run not found")
    return run


@router.get("")
async def list_runs(
    project_id: str | None = None,
    status: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    trigger: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    ctx: OrgContext = Depends(get_org_ctx),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    filt = [Run.org_id == ctx.org_id]
    for col, val in ((Run.project_id, project_id), (Run.status, status), (Run.target_type, target_type), (Run.target_id, target_id), (Run.trigger, trigger)):
        if val:
            filt.append(col == val)
    total = (await session.execute(select(func.count()).select_from(Run).where(*filt))).scalar_one()
    rows = (await session.execute(select(Run).where(*filt).order_by(Run.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return {"total": total, "items": [RunOut.model_validate(r) for r in rows]}


@router.post("", response_model=RunOut, status_code=201)
async def create_run(body: RunCreate, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    project = await get_project(session, body.project_id, ctx.org_id)
    run = await run_engine.start_run(
        session, org=ctx.org, project=project, target_type=body.target_type, target_id=body.target_id,
        input=body.input, trigger="api" if ctx.api_key else "manual", user_id=ctx.user.id,
    )
    if body.wait:
        await run_engine.wait_for_run(run.id, body.wait_timeout)
        await session.refresh(run)
    return run


@router.get("/{run_id}", response_model=RunOut)
async def read_run(run_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    return await _run(session, ctx, run_id)


@router.get("/{run_id}/events", response_model=list[RunEventOut])
async def run_events(run_id: str, after: int = 0, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    await _run(session, ctx, run_id)
    stmt = select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.seq > after).order_by(RunEvent.seq).limit(2000)
    return (await session.execute(stmt)).scalars().all()


@router.post("/{run_id}/rerun", response_model=RunOut, status_code=201)
async def rerun(run_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Start a fresh run with the same target, project and input."""
    old = await _run(session, ctx, run_id)
    project = await get_project(session, old.project_id, ctx.org_id)
    return await run_engine.start_run(
        session, org=ctx.org, project=project, target_type=old.target_type, target_id=old.target_id,
        input=dict(old.input or {}), trigger="manual", user_id=ctx.user.id,
    )


@router.post("/{run_id}/cancel")
async def cancel(run_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    run = await _run(session, ctx, run_id)
    if run.status not in ("queued", "running"):
        return {"ok": False, "status": run.status}
    ok = await run_engine.cancel_run(run_id)
    return {"ok": ok}


def _sse(event: dict[str, Any]) -> str:
    seq = event.get("seq")
    head = f"id: {seq}\n" if seq else ""
    return f"{head}data: {json.dumps(event, default=str)}\n\n"


@router.get("/{run_id}/stream")
async def stream(run_id: str, request: Request, after: int = 0, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    """Server-sent events: replays persisted events, then streams live (incl. token deltas)."""
    run = await _run(session, ctx, run_id)
    last_id = request.headers.get("last-event-id")
    if last_id and last_id.isdigit():
        after = max(after, int(last_id))
    finished = run.status not in ("queued", "running")
    queue = None if finished else bus.subscribe(run_id)

    async def gen():
        last_seq = after
        try:
            async with SessionLocal() as s:
                rows = (await s.execute(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.seq > after).order_by(RunEvent.seq))).scalars().all()
            for r in rows:
                last_seq = r.seq
                yield _sse({"seq": r.seq, "type": r.type, "agent": r.agent, "node_id": r.node_id, "data": r.data, "created_at": r.created_at})
                if r.type == TERMINAL:
                    return
            if queue is None:
                yield _sse({"type": TERMINAL, "data": {"status": run.status}})
                return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if ev.get("seq") and ev["seq"] <= last_seq:
                    continue
                if ev.get("seq"):
                    last_seq = ev["seq"]
                yield _sse(ev)
                if ev["type"] == TERMINAL:
                    return
        finally:
            if queue is not None:
                bus.unsubscribe(run_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ------------------------------------------------------------------ public webhooks
@hooks_router.post("/{token}")
async def webhook_trigger(token: str, request: Request, wait: bool = False):
    ip = client_ip(request)
    await enforce(f"hookip:{ip}", settings.rate_limit_webhook_per_minute * 2)
    if not token.startswith("whk_") or len(token) > 100:
        raise HTTPException(404, "Not found")
    await enforce(f"hook:{sha256_hex(token)[:16]}", settings.rate_limit_webhook_per_minute)
    try:
        raw = await request.body()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Body must be JSON") from exc
    if not isinstance(payload, dict):
        payload = {"payload": payload}
    async with SessionLocal() as s:
        auto = (await s.execute(select(Automation).where(Automation.webhook_token_hash == sha256_hex(token)))).scalar_one_or_none()
        if not auto or auto.trigger_type != "webhook" or not auto.enabled:
            raise HTTPException(404, "Not found")
        auto_id = auto.id
    from ..engine.scheduler import fire

    run_id = await fire(auto_id, trigger="webhook", extra_input=payload)
    if not run_id:
        raise HTTPException(429, "Run could not be started (limits reached)")
    out: dict[str, Any] = {"run_id": run_id, "status": "queued"}
    if wait:
        await run_engine.wait_for_run(run_id, 60)
        async with SessionLocal() as s:
            run = await s.get(Run, run_id)
            out = {"run_id": run_id, "status": run.status, "output": run.output, "error": run.error}
    return out
