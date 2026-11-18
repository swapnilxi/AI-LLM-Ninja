"""Train an agent: teach lessons, review auto-learned lessons, learn from chats, distill a playbook skill."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..deps import OrgContext, audit, get_org_ctx, get_visible, get_writable, require_role
from ..engine import learning
from ..models import Agent, Conversation, Lesson, Memory, Organization
from ..schemas import LessonIn, LessonOut, LessonUpdate, ReflectIn, SkillOut, TrainingSettingsIn

router = APIRouter(tags=["training"])


async def _agent(session: AsyncSession, ctx: OrgContext, agent_id: str) -> Agent:
    return await get_visible(session, Agent, agent_id, ctx.org_id)


async def _lesson(session: AsyncSession, ctx: OrgContext, lesson_id: str) -> Lesson:
    row = await session.get(Lesson, lesson_id)
    if not row or row.org_id != ctx.org_id:
        raise HTTPException(404, "Lesson not found")
    return row


@router.get("/agents/{agent_id}/training")
async def training_overview(agent_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    agent = await _agent(session, ctx, agent_id)
    rows = (await session.execute(select(Lesson.status).where(Lesson.org_id == ctx.org_id, Lesson.agent_id == agent.id))).scalars().all()
    return {
        "auto_learn": bool((agent.settings or {}).get("auto_learn")),
        "can_configure": agent.org_id is not None or ctx.user.is_superadmin,
        "pending": rows.count("pending"),
        "approved": rows.count("approved"),
        "rejected": rows.count("rejected"),
        "memories": await learning.agent_memory_count(session, ctx.org_id, agent.id),
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
    row = Lesson(org_id=ctx.org_id, agent_id=agent.id, status="pending", source="user", title=body.title.strip() or " ".join(body.content.split()[:6]), content=body.content.strip())
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
