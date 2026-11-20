"""Agent-facing to-do tools (project-level capabilities, see tools/registry.py).

create_tasks / list_tasks / update_task  - the "text to task" tools: an agent can turn a chat reply into tracked to-dos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.db import SessionLocal
from app.engine.tools.base import ToolResult
from app.modules.tasks import service as task_engine
from app.modules.tasks.models import Task

if TYPE_CHECKING:
    from app.engine.context import RunContext



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


HANDLERS = {"create_tasks": create_tasks, "list_tasks": list_tasks, "update_task": update_task}
