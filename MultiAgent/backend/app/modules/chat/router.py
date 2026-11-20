from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import OrgContext, filter_visible_ids, get_org_ctx, get_project, get_visible, require_role
from app.modules.agents.models import Agent
from app.modules.chat.models import Conversation, Message
from app.modules.chat.schemas import ConversationIn, ConversationOut, ConversationUpdate, FeedbackIn, MessageIn, MessageOut
from app.modules.runs import service as run_engine
from app.modules.runs.schemas import RunOut
from app.modules.skills.models import Skill
from app.modules.teams.models import Team
from app.modules.training import learning

router = APIRouter(prefix="/conversations", tags=["chat"])


async def _conv(session: AsyncSession, ctx: OrgContext, conv_id: str) -> Conversation:
    c = await session.get(Conversation, conv_id)
    if not c or c.org_id != ctx.org_id or c.user_id != ctx.user.id:
        raise HTTPException(404, "Conversation not found")
    return c


@router.get("", response_model=list[ConversationOut])
async def list_conversations(project_id: str | None = None, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    stmt = select(Conversation).where(Conversation.org_id == ctx.org_id, Conversation.user_id == ctx.user.id)
    if project_id:
        stmt = stmt.where(Conversation.project_id == project_id)
    return (await session.execute(stmt.order_by(Conversation.updated_at.desc()).limit(200))).scalars().all()


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(body: ConversationIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    await get_project(session, body.project_id, ctx.org_id)
    await get_visible(session, Agent if body.target_type == "agent" else Team, body.target_id, ctx.org_id)
    c = Conversation(org_id=ctx.org_id, project_id=body.project_id, user_id=ctx.user.id, target_type=body.target_type, target_id=body.target_id, title=body.title)
    session.add(c)
    await session.commit()
    return c


@router.get("/{conv_id}")
async def read_conversation(conv_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    c = await _conv(session, ctx, conv_id)
    msgs = (await session.execute(select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at))).scalars().all()
    return {"conversation": ConversationOut.model_validate(c), "messages": [MessageOut.model_validate(m) for m in msgs]}


@router.patch("/{conv_id}", response_model=ConversationOut)
async def update_conversation(conv_id: str, body: ConversationUpdate, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    c = await _conv(session, ctx, conv_id)
    if body.title and body.title.strip():
        c.title = body.title.strip()
    if body.skill_ids is not None:
        c.skill_ids = await filter_visible_ids(session, Skill, list(dict.fromkeys(body.skill_ids)), ctx.org_id)
    await session.commit()
    return c


@router.patch("/{conv_id}/messages/{message_id}", response_model=MessageOut)
async def message_feedback(conv_id: str, message_id: str, body: FeedbackIn, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    c = await _conv(session, ctx, conv_id)
    m = await session.get(Message, message_id)
    if not m or m.conversation_id != c.id or m.role != "assistant":
        raise HTTPException(404, "Message not found")
    meta = dict(m.meta or {})
    if body.feedback:
        meta["feedback"] = {"rating": body.feedback, "note": body.note, "user_id": ctx.user.id}
    else:
        meta.pop("feedback", None)
    m.meta = meta
    await session.commit()
    if body.feedback == "down" and c.target_type == "agent":  # feed the Train tab review queue
        agent = await session.get(Agent, c.target_id)
        if agent:
            try:
                await learning.learn_from_message(session, ctx.org, agent, c.id, m.id, hint=body.note, negative=True, source="feedback")
                await session.commit()
            except Exception:  # feedback must never fail because learning did
                await session.rollback()
    return m


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(conv_id: str, ctx: OrgContext = Depends(get_org_ctx), session: AsyncSession = Depends(get_session)):
    c = await _conv(session, ctx, conv_id)
    await session.execute(delete(Message).where(Message.conversation_id == c.id))
    await session.delete(c)
    await session.commit()


@router.post("/{conv_id}/messages", status_code=201)
async def send_message(conv_id: str, body: MessageIn, ctx: OrgContext = Depends(require_role("member")), session: AsyncSession = Depends(get_session)):
    c = await _conv(session, ctx, conv_id)
    project = await get_project(session, c.project_id, ctx.org_id)
    msg = Message(conversation_id=c.id, role="user", content=body.content)
    session.add(msg)
    if c.title in ("", "New chat"):
        c.title = body.content.strip().splitlines()[0][:60] or "New chat"
    await session.commit()
    run = await run_engine.start_run(
        session, org=ctx.org, project=project, target_type=c.target_type, target_id=c.target_id,
        input={"message": body.content}, trigger="chat", user_id=ctx.user.id, conversation_id=c.id,
    )
    msg.run_id = run.id
    await session.commit()
    return {"message": MessageOut.model_validate(msg), "run": RunOut.model_validate(run)}
