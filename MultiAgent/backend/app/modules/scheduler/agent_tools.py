"""Agent-facing scheduling tool: an agent can turn "every weekday at 9am do X" or "tomorrow at 3pm do Y" into a real schedule."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.engine.tools.base import ToolResult
from app.modules.agents.models import Agent
from app.modules.scheduler import nl_parser
from app.modules.scheduler.models import Automation

if TYPE_CHECKING:
    from app.engine.context import RunContext

MAX_AGENT_AUTOMATIONS_PER_PROJECT = 25
AGENT_AUTOMATION_MARKER = "Scheduled by an agent"


async def schedule_task(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    # Imported lazily: the scheduler service imports the run engine, which imports the tool registry (this module).
    from app.modules.scheduler.service import compute_next_run

    if ctx.trigger in ("schedule", "webhook", "interval"):
        return ToolResult("Scheduled and webhook runs cannot create new schedules (prevents runaway automation).", True)
    if not ctx.user_id or not ctx.current_agent_id:
        return ToolResult("Scheduling needs a signed-in user and an agent context.", True)
    when, task = str(args.get("when") or "").strip(), str(args.get("task") or "").strip()
    if not when or not task:
        return ToolResult("Both `when` (e.g. 'every weekday at 9am') and `task` (what to do each time) are required.", True)
    tz = str(args.get("timezone") or ctx.project.settings.get("timezone") or "UTC")
    try:
        ZoneInfo(tz)
    except Exception:
        return ToolResult(f"Unknown timezone '{tz}'. Use an IANA name such as Asia/Kolkata.", True)
    sched = nl_parser.parse_when(when, tz)
    if not sched:
        return ToolResult(
            "I could not understand that schedule. Use phrases such as 'every weekday at 9am', 'daily at 18:00', 'every 2 hours', "
            "'monthly on the 1st', 'tomorrow at 3pm', 'in 2 hours' or 'on 2026-12-05 at 10:00'.", True,
        )
    async with SessionLocal() as s:
        agent = await s.get(Agent, ctx.current_agent_id)
        if not agent:
            return ToolResult("Agent not found", True)
        total = (await s.execute(select(func.count()).select_from(Automation).where(Automation.org_id == ctx.org.id))).scalar_one()
        mine = (
            await s.execute(
                select(func.count()).select_from(Automation).where(
                    Automation.org_id == ctx.org.id, Automation.project_id == ctx.project.id, Automation.description.like(f"{AGENT_AUTOMATION_MARKER}%")
                )
            )
        ).scalar_one()
        if total >= 200 or mine >= MAX_AGENT_AUTOMATIONS_PER_PROJECT:
            return ToolResult(f"Automation limit reached (agents may create up to {MAX_AGENT_AUTOMATIONS_PER_PROJECT} per project). Remove old ones on the Scheduler page.", True)
        auto = Automation(
            org_id=ctx.org.id, project_id=ctx.project.id, name=(str(args.get("name") or "").strip() or task)[:120],
            description=f"{AGENT_AUTOMATION_MARKER} (run {ctx.run_id}): {task}"[:1900], target_type="agent", target_id=agent.id, input={"task": task[:4000]},
            trigger_type=sched.trigger_type, cron=sched.cron, interval_minutes=sched.interval_minutes, run_at=sched.run_at, timezone=tz, enabled=True,
            created_by=ctx.user_id, source="agent",
        )
        auto.next_run_at = compute_next_run(auto)
        s.add(auto)
        await s.commit()
    nxt = auto.next_run_at.astimezone(ZoneInfo(tz)).strftime("%a %d %b %Y %H:%M") if auto.next_run_at else "n/a"
    note = (" Note: " + " ".join(sched.notes)) if sched.notes else ""
    return ToolResult(
        f"Scheduled '{auto.name}' (schedule {auto.id}): {nl_parser.describe(auto.trigger_type, auto.cron, auto.interval_minutes, tz, auto.run_at)}. "
        f"Next run {nxt} ({tz}). It runs as agent '{agent.name}' and can be paused or edited on the Scheduler page (/scheduler).{note}"
    )


HANDLERS = {"schedule_task": schedule_task}
