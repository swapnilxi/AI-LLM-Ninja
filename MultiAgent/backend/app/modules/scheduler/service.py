"""Background scheduler for automations (cron / interval triggers)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import croniter
from fastapi import HTTPException
from sqlalchemy import select, update

from ..config import settings
from ..db import SessionLocal
from ..models import Automation, Organization, Project
from .runs import start_run

log = logging.getLogger("agentforge.scheduler")


def compute_next_run(auto: Automation, after: datetime | None = None) -> datetime | None:
    after = after or datetime.now(timezone.utc)
    if not auto.enabled:
        return None
    if auto.trigger_type == "interval" and auto.interval_minutes and auto.interval_minutes > 0:
        return after + timedelta(minutes=max(1, auto.interval_minutes))
    if auto.trigger_type == "schedule" and auto.cron:
        try:
            tz = ZoneInfo(auto.timezone or "UTC")
        except Exception:
            tz = ZoneInfo("UTC")
        nxt = croniter(auto.cron, after.astimezone(tz)).get_next(datetime)
        return nxt.astimezone(timezone.utc)
    return None


def validate_cron(expr: str) -> bool:
    return croniter.is_valid(expr)


async def fire(auto_id: str, trigger: str = "schedule", extra_input: dict | None = None) -> str | None:
    async with SessionLocal() as s:
        auto = await s.get(Automation, auto_id)
        if not auto:
            return None
        org = await s.get(Organization, auto.org_id)
        project = await s.get(Project, auto.project_id)
        if not org or not project:
            return None
        auto.last_run_at = datetime.now(timezone.utc)
        auto.run_count = (auto.run_count or 0) + 1
        await s.commit()
        try:
            run = await start_run(
                s,
                org=org,
                project=project,
                target_type=auto.target_type,
                target_id=auto.target_id,
                input={**(auto.input or {}), **(extra_input or {})},
                trigger=trigger,
                user_id=auto.created_by,
                automation_id=auto.id,
            )
            return run.id
        except HTTPException as exc:
            auto.last_status = f"skipped: {exc.detail}"[:20]
            await s.commit()
            log.warning("automation %s not started: %s", auto_id, exc.detail)
            return None


async def tick() -> int:
    now = datetime.now(timezone.utc)
    fired = 0
    async with SessionLocal() as s:
        due = (
            (
                await s.execute(
                    select(Automation).where(
                        Automation.enabled.is_(True),
                        Automation.trigger_type.in_(["schedule", "interval"]),
                        Automation.next_run_at.is_not(None),
                        Automation.next_run_at <= now,
                    )
                )
            )
            .scalars()
            .all()
        )
        for auto in due:
            nxt = compute_next_run(auto, now)
            # optimistic claim: only one scheduler instance wins
            res = await s.execute(
                update(Automation)
                .where(Automation.id == auto.id, Automation.next_run_at == auto.next_run_at)
                .values(next_run_at=nxt)
            )
            await s.commit()
            if res.rowcount:
                fired += 1
                asyncio.create_task(fire(auto.id))
    return fired


async def scheduler_loop(stop: asyncio.Event) -> None:
    log.info("scheduler started (every %ss)", settings.scheduler_interval_seconds)
    while not stop.is_set():
        try:
            await tick()
        except Exception:
            log.exception("scheduler tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.scheduler_interval_seconds)
        except asyncio.TimeoutError:
            pass
