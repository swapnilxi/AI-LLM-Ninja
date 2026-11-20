"""Agent-facing to-do and scheduling tools (project-level capabilities, see tools/registry.py).

create_tasks / list_tasks / update_task  - the "text to task" tools: an agent can turn a chat reply into tracked to-dos.
schedule_task                           - "scheduler with AI": turn "every weekday at 9am do X" into a real automation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from ...db import SessionLocal
from ...models import Agent, Automation, Task
from .. import nl_schedule, tasks as task_engine
from .base import ToolResult

if TYPE_CHECKING:
    from ..context import RunContext

MAX_AGENT_AUTOMATIONS_PER_PROJECT = 25
AGENT_AUTOMATION_MARKER = "Scheduled by an agent"


def _fmt(t: Task) -> str:
    bits = [t.status, t.priority] + ([f"due {t.due_at.date().isoformat()}"] if t.due_at else [])
    return f"- ({t.id}) {t.title} [{', '.join(bits)}]"


async def create_tasks(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    items = args.get("tasks")
    if isinstance(items, str):
        items = [{"title": items}]
    if not isinstance(items, list) or not items:
        return ToolResult("tasks must be a non-empty array of {title, notes?, priority?, due?, context?}", True)
    items = [i if isinstance(i, dict) else {"title": str(i)} for i in items[: task_engine.MAX_EXTRACT * 2]]
    async with SessionLocal() as s:
        created, skipped = await task_engine.create_tasks(
            s, org_id=ctx.org.id, project_id=ctx.project.id, items=items, source="agent", user_id=ctx.user_id, run_id=ctx.run_id,
            context=str(args.get("context") or ""),
        )
        await s.commit()
    if not created and not skipped:
        return ToolResult("No valid tasks were provided (each needs a title).", True)
    lines = [f"Created {len(created)} task(s) in project '{ctx.project.name}':", *(_fmt(t) for t in created)]
    if skipped:
        lines.append(f"Skipped {len(skipped)} duplicate/over-limit: " + "; ".join(skipped[:5]))
    return ToolResult("\n".join(lines), data=[t.id for t in created])


async def list_tasks(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    status = str(args.get("status") or "open")
    limit = max(1, min(int(args.get("limit") or 25), 100))
    stmt = select(Task).where(Task.org_id == ctx.org.id, Task.project_id == ctx.project.id)
    if status in task_engine.STATUSES:
        stmt = stmt.where(Task.status == status)
    elif status == "open":
        stmt = stmt.where(Task.status != "done")
    async with SessionLocal() as s:
        rows = (await s.execute(stmt.order_by(Task.created_at.desc()).limit(limit))).scalars().all()
    if not rows:
        return ToolResult(f"No {status} tasks in this project.")
    return ToolResult("\n".join(_fmt(t) for t in rows))


async def update_task(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    async with SessionLocal() as s:
        t = await s.get(Task, str(args.get("task_id", "")))
        if not t or t.org_id != ctx.org.id or t.project_id != ctx.project.id:
            return ToolResult("Task not found in this project", True)
        if (st := args.get("status")) is not None:
            if st not in task_engine.STATUSES:
                return ToolResult(f"status must be one of {list(task_engine.STATUSES)}", True)
            t.status = st
            t.completed_at = datetime.now(timezone.utc) if st == "done" else None
        if args.get("title"):
            t.title = str(args["title"]).strip()[:255]
        if args.get("notes") is not None:
            t.notes = str(args["notes"])[:4000]
        if args.get("priority") in task_engine.PRIORITIES:
            t.priority = args["priority"]
        if args.get("due") is not None:
            t.due_at = task_engine.parse_due(str(args["due"]))
        await s.commit()
        return ToolResult(f"Updated task {_fmt(t)}")


async def schedule_task(args: dict[str, Any], ctx: "RunContext") -> ToolResult:
    # Imported lazily: the scheduler imports the run engine, which imports the tool registry (this module).
    from ..scheduler import compute_next_run

    if ctx.trigger in ("schedule", "webhook", "interval"):
        return ToolResult("Scheduled and webhook runs cannot create new schedules (prevents runaway automation).", True)
    if not ctx.user_id or not ctx.current_agent_id:
        return ToolResult("Scheduling needs a signed-in user and an agent context.", True)
    when, task = str(args.get("when") or "").strip(), str(args.get("task") or "").strip()
    if not when or not task:
        return ToolResult("Both `when` (e.g. 'every weekday at 9am') and `task` (what to do each time) are required.", True)
    sched = nl_schedule.parse_schedule(when)
    if not sched:
        return ToolResult(
            "I could not understand that schedule. Use recurring phrases such as 'every weekday at 9am', 'daily at 18:00', "
            "'every monday at 8:30', 'every 2 hours' or 'monthly on the 1st'. One-time reminders are not supported.", True,
        )
    tz = str(args.get("timezone") or ctx.project.settings.get("timezone") or "UTC")
    try:
        ZoneInfo(tz)
    except Exception:
        return ToolResult(f"Unknown timezone '{tz}'. Use an IANA name such as Asia/Kolkata.", True)
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
            return ToolResult(f"Automation limit reached (agents may create up to {MAX_AGENT_AUTOMATIONS_PER_PROJECT} per project). Remove old ones on the Automations page.", True)
        auto = Automation(
            org_id=ctx.org.id, project_id=ctx.project.id, name=(str(args.get("name") or "").strip() or task)[:120],
            description=f"{AGENT_AUTOMATION_MARKER} (run {ctx.run_id}): {task}"[:1900], target_type="agent", target_id=agent.id, input={"task": task[:4000]},
            trigger_type=sched.trigger_type, cron=sched.cron, interval_minutes=sched.interval_minutes, timezone=tz, enabled=True, created_by=ctx.user_id,
        )
        auto.next_run_at = compute_next_run(auto)
        s.add(auto)
        await s.commit()
    nxt = auto.next_run_at.astimezone(ZoneInfo(tz)).strftime("%a %d %b %Y %H:%M") if auto.next_run_at else "n/a"
    note = (" Note: " + " ".join(sched.notes)) if sched.notes else ""
    return ToolResult(
        f"Scheduled '{auto.name}' (automation {auto.id}): {nl_schedule.describe(auto.trigger_type, auto.cron, auto.interval_minutes, tz)}. "
        f"Next run {nxt} ({tz}). It runs as agent '{agent.name}' and can be paused or edited on the Automations page.{note}"
    )


HANDLERS = {"create_tasks": create_tasks, "list_tasks": list_tasks, "update_task": update_task, "schedule_task": schedule_task}
