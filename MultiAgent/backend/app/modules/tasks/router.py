"""To-dos: CRUD, "text to task" extraction (from pasted text or a chat reply) and running a task with an agent."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import pick_agent
from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_org_ctx, get_project, require_role
from app.modules.chat.models import Conversation, Message
from app.modules.runs import service as run_engine
from app.modules.tasks import service as task_engine
from app.modules.tasks.models import Task
from app.modules.tasks.schemas import TaskBulkIn, TaskExtractIn, TaskIn, TaskOut, TaskRunIn, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])
SOURCE_EXCERPT = 1500


async def _get(session: AsyncSession, ctx: OrgContext, task_id: str) -> Task:
    t = await session.get(Task, task_id)
    if not t or t.org_id != ctx.org_id:
        raise HTTPException(404, "Task not found")
    return t


async def _chat_source(session: AsyncSession, ctx: OrgContext, project_id: str, conversation_id: str | None, message_id: str | None) -> Message | None:
    """The chat message a task came from. The conversation must belong to the caller and to this project."""
    if not conversation_id or not message_id:
        return None
    conv = await session.get(Conversation, conversation_id)
    if not conv or conv.org_id != ctx.org_id or conv.user_id != ctx.user.id or conv.project_id != project_id:
        raise HTTPException(404, "Conversation not found")
    msg = await session.get(Message, message_id)
    if not msg or msg.conversation_id != conv.id:
        raise HTTPException(404, "Message not found")
    return msg


def _shared_context(user_context: str, source_text: str, from_chat: bool) -> str:
    parts = []
    if user_context.strip():
        parts.append(user_context.strip())
    if source_text.strip():
        label = "From a chat reply" if from_chat else "From the source text"
        excerpt = source_text.strip()[:SOURCE_EXCERPT] + ("…" if len(source_text.strip()) > SOURCE_EXCERPT else "")
        parts.append(f"{label}:\n{excerpt}")
    return "\n\n".join(parts)[:8000]


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    project_id: str | None = None, status: str | None = None, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)
):
    stmt = select(Task).where(Task.org_id == ctx.org_id)
    if project_id:
        stmt = stmt.where(Task.project_id == project_id)
    if status == "open":
        stmt = stmt.where(Task.status != "done")
    elif status in task_engine.STATUSES:
        stmt = stmt.where(Task.status == status)
    return (await session.execute(stmt.order_by(Task.created_at.desc()).limit(500))).scalars().all()


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(body: TaskIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    await get_project(session, body.project_id, ctx.org_id)
    if await task_engine.open_task_count(session, ctx.org_id, body.project_id) >= task_engine.MAX_OPEN_PER_PROJECT:
        raise HTTPException(400, "Too many open tasks in this project - complete or delete some first")
    t = Task(org_id=ctx.org_id, created_by=ctx.user.id, source="manual", **body.model_dump())
    if t.status == "done":
        t.completed_at = datetime.now(timezone.utc)
    session.add(t)
    await session.commit()
    return t


@router.post("/extract")
async def extract(body: TaskExtractIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Text to task. Without `save`, returns a preview to review/edit; with `save`, creates the tasks directly."""
    await get_project(session, body.project_id, ctx.org_id)
    msg = await _chat_source(session, ctx, body.project_id, body.conversation_id, body.message_id)
    text = body.text.strip() or (msg.content if msg else "")
    if not text:
        raise HTTPException(400, "Provide some text, or a chat message to convert")
    items, engine = await task_engine.extract_tasks(session, ctx.org, text, body.hint)
    shared = _shared_context(body.context, text, from_chat=msg is not None)
    out: dict[str, Any] = {
        "engine": engine,
        "context": shared,
        "items": [{"title": i["title"], "notes": i["notes"], "priority": i["priority"], "due_at": i["due"].isoformat() if i["due"] else None} for i in items],
    }
    if body.save and items:
        created, skipped = await task_engine.create_tasks(
            session, org_id=ctx.org_id, project_id=body.project_id, items=items, source="chat" if msg else "text", user_id=ctx.user.id,
            conversation_id=body.conversation_id if msg else None, message_id=body.message_id if msg else None, context=shared,
        )
        await session.commit()
        out["created"] = [TaskOut.model_validate(t) for t in created]
        out["skipped"] = skipped
    return out


@router.post("/bulk", status_code=201)
async def bulk_create(body: TaskBulkIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Save the (reviewed) items of an extraction preview."""
    await get_project(session, body.project_id, ctx.org_id)
    msg = await _chat_source(session, ctx, body.project_id, body.conversation_id, body.message_id)
    items = [{"title": i.title, "notes": i.notes, "priority": i.priority, "due": i.due_at} for i in body.items]
    created, skipped = await task_engine.create_tasks(
        session, org_id=ctx.org_id, project_id=body.project_id, items=items, source="chat" if msg else body.source, user_id=ctx.user.id,
        conversation_id=body.conversation_id if msg else None, message_id=body.message_id if msg else None, context=body.context,
    )
    await session.commit()
    return {"created": [TaskOut.model_validate(t) for t in created], "skipped": skipped}


@router.get("/{task_id}", response_model=TaskOut)
async def read_task(task_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    return await _get(session, ctx, task_id)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(task_id: str, body: TaskUpdate, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    t = await _get(session, ctx, task_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is None and k not in ("due_at",):
            continue
        setattr(t, k, v)
    if "status" in body.model_fields_set and body.status:
        t.completed_at = datetime.now(timezone.utc) if body.status == "done" else None
    await session.commit()
    return t


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    await session.delete(await _get(session, ctx, task_id))
    await session.commit()


@router.post("/{task_id}/run")
async def run_task(task_id: str, body: TaskRunIn, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Hand the task, with all its context, to an agent."""
    t = await _get(session, ctx, task_id)
    project = await get_project(session, t.project_id, ctx.org_id)
    agent = await pick_agent(session, ctx, project, body.agent_id)
    run = await run_engine.start_run(
        session, org=ctx.org, project=project, target_type="agent", target_id=agent.id,
        input={"task": task_engine.run_prompt(t), "task_id": t.id}, trigger="manual", user_id=ctx.user.id,
    )
    t.run_id = run.id
    if t.status == "todo":
        t.status = "doing"
    await audit(session, action="task.run", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="task", target_id=t.id, commit=False)
    await session.commit()
    return {"run_id": run.id, "agent_id": agent.id, "agent_name": agent.name}
