"""Train an agent: teach lessons, review auto-learned lessons, learn from chats, distill a playbook skill."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Integer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import OrgContext, audit, get_org_ctx, get_visible, get_writable, require_role
from app.modules.agents.models import Agent
from app.modules.chat.models import Conversation
from app.modules.knowledge.models import Document, Memory
from app.modules.orgs.models import Organization
from app.modules.skills.schemas import SkillOut
from app.modules.training import learning
from app.modules.training.models import Lesson
from app.modules.training.schemas import LessonIn, LessonOut, LessonUpdate, ReflectIn, TrainingSettingsIn

router = APIRouter(tags=["training"])


async def _agent(session: AsyncSession, ctx: OrgContext, agent_id: str) -> Agent:
    return await get_visible(session, Agent, agent_id, ctx.org_id)


async def _lesson(session: AsyncSession, ctx: OrgContext, lesson_id: str) -> Lesson:
    row = await session.get(Lesson, lesson_id)
    if not row or row.org_id != ctx.org_id:
        raise HTTPException(404, "Lesson not found")
    return row


@router.get("/training/agents")
async def training_grid(ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    """Per-agent training stats for every agent visible to this org, in one request (for the Training picker)."""
    stats: dict[str, dict[str, int]] = {}

    def row(agent_id: str) -> dict[str, int]:
        return stats.setdefault(agent_id, {"documents": 0, "chunks": 0, "pending": 0, "approved": 0, "memories": 0})

    docs = await session.execute(
        select(Document.owner_id, func.count(), func.coalesce(func.sum(Document.chunk_count), 0))
        .where(Document.org_id == ctx.org_id, Document.owner_type == "agent")
        .group_by(Document.owner_id)
    )
    for agent_id, n, chunks in docs.all():
        row(agent_id).update(documents=int(n), chunks=int(chunks or 0))
    lessons = await session.execute(
        select(Lesson.agent_id, Lesson.status, func.count())
        .where(Lesson.org_id == ctx.org_id, Lesson.status.in_(["pending", "approved"]))
        .group_by(Lesson.agent_id, Lesson.status)
    )
    for agent_id, status, n in lessons.all():
        row(agent_id)[status] = int(n)
    mems = await session.execute(
        select(Memory.agent_id, func.count()).where(Memory.org_id == ctx.org_id, Memory.scope == "agent", Memory.agent_id.is_not(None)).group_by(Memory.agent_id)
    )
    for agent_id, n in mems.all():
        row(agent_id)["memories"] = int(n)
    return stats


@router.get("/agents/{agent_id}/training")
async def training_overview(agent_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    agent = await _agent(session, ctx, agent_id)
    rows = (await session.execute(select(Lesson.status, Lesson.kind).where(Lesson.org_id == ctx.org_id, Lesson.agent_id == agent.id))).all()
    statuses = [r[0] for r in rows]
    kinds: dict[str, int] = {"rule": 0, "fact": 0, "example": 0, "correction": 0}
    for status, kind in rows:
        if status == "approved":
            kinds[kind or "rule"] = kinds.get(kind or "rule", 0) + 1
    n_docs, n_chunks, n_pinned, n_bytes = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Document.chunk_count), 0),
                func.coalesce(func.sum(func.cast(Document.pinned, Integer)), 0),
                func.coalesce(func.sum(Document.size), 0),
            ).where(Document.org_id == ctx.org_id, Document.owner_type == "agent", Document.owner_id == agent.id)
        )
    ).one()
    return {
        "auto_learn": bool((agent.settings or {}).get("auto_learn")),
        "can_configure": agent.org_id is not None or ctx.user.is_superadmin,
        "pending": statuses.count("pending"),
        "approved": statuses.count("approved"),
        "rejected": statuses.count("rejected"),
        "approved_by_kind": kinds,
        "memories": await learning.agent_memory_count(session, ctx.org_id, agent.id),
        "documents": int(n_docs),
        "chunks": int(n_chunks or 0),
        "pinned_documents": int(n_pinned or 0),
        "document_bytes": int(n_bytes or 0),
    }


@router.put("/agents/{agent_id}/training/settings")
async def training_settings(agent_id: str, body: TrainingSettingsIn, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    agent = await get_writable(session, Agent, agent_id, ctx)
    agent.settings = {**(agent.settings or {}), "auto_learn": body.auto_learn}
    await session.commit()
    return {"auto_learn": body.auto_learn}


@router.get("/agents/{agent_id}/lessons", response_model=list[LessonOut])
async def list_lessons(
    agent_id: str,
    status: str = Query("pending", pattern="^(pending|approved|rejected|all)$"),
    ctx: OrgContext = Depends(get_org_ctx),
    session: AsyncSession = Depends(get_session),
):
    agent = await _agent(session, ctx, agent_id)
    stmt = select(Lesson).where(Lesson.org_id == ctx.org_id, Lesson.agent_id == agent.id)
    if status != "all":
        stmt = stmt.where(Lesson.status == status)
    return (await session.execute(stmt.order_by(Lesson.created_at.desc()).limit(200))).scalars().all()


@router.post("/agents/{agent_id}/lessons", response_model=LessonOut, status_code=201)
async def teach(agent_id: str, body: LessonIn, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Teach the agent directly: the lesson is approved immediately and saved as agent memory."""
    agent = await _agent(session, ctx, agent_id)
    prompt = (body.prompt or "").strip() or None
    default_title = " ".join(((prompt if body.kind == "example" else None) or body.content).split()[:6])[:120]
    row = Lesson(
        org_id=ctx.org_id, agent_id=agent.id, status="pending", source="user", kind=body.kind,
        title=body.title.strip() or default_title, content=body.content.strip(), prompt=prompt,
    )
    session.add(row)
    try:
        await learning.approve(session, row, agent, source="user")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await audit(session, action="agent.teach", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="agent", target_id=agent.id, commit=False)
    await session.commit()
    return row


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
async def edit_lesson(lesson_id: str, body: LessonUpdate, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    row = await _lesson(session, ctx, lesson_id)
    if row.status != "pending":
        raise HTTPException(400, "Only pending lessons can be edited")
    if body.content is not None:
        row.content = body.content.strip()
    if body.title is not None:
        row.title = body.title.strip()
    if body.kind is not None:
        row.kind = body.kind
    if body.prompt is not None:
        row.prompt = body.prompt.strip() or None
    if row.kind == "example" and not row.prompt:
        raise HTTPException(400, "A Q&A example needs a question")
    await session.commit()
    return row


@router.post("/lessons/{lesson_id}/approve", response_model=LessonOut)
async def approve_lesson(lesson_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    row = await _lesson(session, ctx, lesson_id)
    if row.status == "pending":
        agent = await _agent(session, ctx, row.agent_id)
        try:
            await learning.approve(session, row, agent)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        await session.commit()
    return row


@router.post("/lessons/{lesson_id}/reject", response_model=LessonOut)
async def reject_lesson(lesson_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    row = await _lesson(session, ctx, lesson_id)
    if row.status == "pending":
        row.status = "rejected"
        await session.commit()
    return row


@router.post("/agents/{agent_id}/lessons/approve-all")
async def approve_all(agent_id: str, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    agent = await _agent(session, ctx, agent_id)
    rows = (await session.execute(select(Lesson).where(Lesson.org_id == ctx.org_id, Lesson.agent_id == agent.id, Lesson.status == "pending").order_by(Lesson.created_at))).scalars().all()
    done = 0
    for row in rows:
        try:
            await learning.approve(session, row, agent)
            done += 1
        except ValueError:
            break
    await session.commit()
    return {"approved": done}


@router.post("/agents/{agent_id}/training/reflect")
async def learn_from_chats(agent_id: str, body: ReflectIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Mine your own chats with this agent (one conversation, or the 5 most recent) for lessons to review."""
    agent = await _agent(session, ctx, agent_id)
    stmt = select(Conversation).where(Conversation.org_id == ctx.org_id, Conversation.user_id == ctx.user.id, Conversation.target_type == "agent", Conversation.target_id == agent.id)
    if body.conversation_id:
        stmt = stmt.where(Conversation.id == body.conversation_id)
    convs = (await session.execute(stmt.order_by(Conversation.updated_at.desc()).limit(1 if body.conversation_id else 5))).scalars().all()
    if not convs:
        raise HTTPException(404, "No chats with this agent yet - start a conversation first.")
    org = await session.get(Organization, ctx.org_id)
    created: list[Lesson] = []
    for c in convs:
        created += await learning.learn_from_message(session, org, agent, c.id, source="auto")
    await session.commit()
    return {"conversations": len(convs), "proposed": len(created)}


@router.post("/agents/{agent_id}/training/distill", response_model=SkillOut)
async def distill_playbook(agent_id: str, request: Request, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    """Merge everything taught/learned into one '<agent> playbook' skill and attach it to the agent."""
    agent = await get_writable(session, Agent, agent_id, ctx)
    org = await session.get(Organization, ctx.org_id)
    try:
        skill = await learning.distill(session, org, agent, ctx.user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await audit(session, action="agent.distill", org_id=ctx.org_id, user_id=ctx.user.id, request=request, target_type="agent", target_id=agent.id, commit=False)
    await session.commit()
    return skill
