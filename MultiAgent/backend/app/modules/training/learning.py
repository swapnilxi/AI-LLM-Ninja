"""Agent training: turn conversations and feedback into reviewable lessons, and lessons into memory/skills.

Flow:  chat / thumbs-down / "learn from chats"  ->  reflect()  ->  pending Lesson rows
       user approves a lesson                  ->  agent Memory (injected into every prompt)
       distill()                               ->  one "playbook" Skill built from the agent's lessons
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.engine.llm.base import LLMError, ModelSettings
from app.engine.llm.registry import get_provider, resolve_model
from app.modules.agents.models import Agent
from app.modules.chat.models import Message
from app.modules.knowledge.models import Memory
from app.modules.knowledge.service import tokenize
from app.modules.orgs.models import Organization
from app.modules.runs.models import Run
from app.modules.skills.models import Skill
from app.modules.training.models import Lesson

log = logging.getLogger("agentforge.learning")

MAX_PENDING = 50
MAX_MEMORIES = 500
_bg: set[asyncio.Task] = set()

REFLECT_SYSTEM = """You review one exchange between a user and an AI agent and extract durable lessons the agent should remember.
A good lesson is:
- reusable in future conversations (a user preference, a correction, a house rule, a domain fact, a format or tone requirement)
- phrased as one short imperative or fact, e.g. "Always answer in bullet points with a one-line summary first."
- never a one-off detail, never a secret, password or API key.
Return ONLY a JSON array (no prose, no code fences) with at most 3 items: [{"title": "<=6 words", "lesson": "<one sentence>", "why": "<short evidence from the exchange>"}].
Return [] if there is nothing worth remembering."""

_RULE_RE = re.compile(
    r"(?:^|[.!?\n]\s*)((?:please\s+)?(?:always|never|remember(?: that)?|from now on|don'?t ever|make sure (?:you|to)|i prefer|i like|i want you to|going forward)\b[^.!?\n]{6,300})",
    re.I,
)


def _norm(text: str) -> set[str]:
    return set(tokenize(text))


def similar(a: str, b: str, threshold: float = 0.7) -> bool:
    ta, tb = _norm(a), _norm(b)
    if not ta or not tb:
        return a.strip().lower() == b.strip().lower()
    return len(ta & tb) / len(ta | tb) >= threshold


def heuristic_lessons(user_message: str) -> list[dict[str, str]]:
    """Offline fallback (mock model): explicit 'always/never/remember…' statements by the user."""
    out = []
    for m in _RULE_RE.finditer(user_message or ""):
        text = m.group(1).strip().rstrip(",;")
        out.append({"title": " ".join(text.split()[:6]), "lesson": text[0].upper() + text[1:], "why": "You stated this rule in chat."})
    return out[:3]


def parse_lessons(raw: str) -> list[dict[str, str]]:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
    m = re.search(r"\[.*\]", raw, flags=re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("lesson") or "").strip()
        if len(text) < 8:
            continue
        out.append({"title": str(item.get("title") or "")[:120], "lesson": text[:2000], "why": str(item.get("why") or "")[:500]})
    return out[:3]


async def _complete(session: AsyncSession, org: Any, agent: Agent, system: str, prompt: str, max_tokens: int) -> tuple[str, str]:
    """One-shot completion with the agent's own model. Returns (text, provider)."""
    provider_key, model = await resolve_model(session, org, agent.provider, agent.model)
    provider = await get_provider(session, org, provider_key)
    resp = await provider.complete(
        system=system, messages=[{"role": "user", "content": prompt}], tools=[], settings=ModelSettings(model=model, max_tokens=max_tokens)
    )
    return resp.text, provider_key


async def reflect(
    session: AsyncSession, org: Organization, agent: Agent, user_message: str, assistant_message: str, *, history: str = "", hint: str = "", negative: bool = False
) -> list[dict[str, str]]:
    prompt = (
        (f"Earlier in the conversation:\n{history[:3000]}\n\n" if history else "")
        + f"User:\n{user_message[:4000]}\n\nAgent:\n{assistant_message[:4000]}\n"
        + (f"\nThe user gave this feedback on the agent's answer: {hint[:1000]}\n" if hint else "")
        + ("\nThe user rated this answer as bad. Work out what the agent should do differently next time.\n" if negative else "")
    )
    try:
        text, provider_key = await _complete(session, org, agent, REFLECT_SYSTEM, prompt, 700)
    except LLMError as exc:
        log.info("reflection skipped: %s", exc)
        return []
    if provider_key == "mock":
        return heuristic_lessons(f"{user_message}\n{hint}")
    return parse_lessons(text)


async def agent_memory_count(session: AsyncSession, org_id: str, agent_id: str) -> int:
    return (await session.execute(select(func.count()).select_from(Memory).where(Memory.org_id == org_id, Memory.agent_id == agent_id, Memory.scope == "agent"))).scalar_one()


async def _known_texts(session: AsyncSession, org_id: str, agent_id: str) -> list[str]:
    mems = (await session.execute(select(Memory.content).where(Memory.org_id == org_id, Memory.agent_id == agent_id, Memory.scope == "agent"))).scalars().all()
    pend = (await session.execute(select(Lesson.content).where(Lesson.org_id == org_id, Lesson.agent_id == agent_id, Lesson.status == "pending"))).scalars().all()
    return [*mems, *pend]


async def propose(
    session: AsyncSession, org_id: str, agent_id: str, items: list[dict[str, str]], *, source: str,
    conversation_id: str | None = None, message_id: str | None = None, run_id: str | None = None,
) -> list[Lesson]:
    """Store reflection output as pending lessons, skipping near-duplicates and respecting the queue cap."""
    known = await _known_texts(session, org_id, agent_id)
    pending = sum(1 for _ in (await session.execute(select(Lesson.id).where(Lesson.org_id == org_id, Lesson.agent_id == agent_id, Lesson.status == "pending"))).all())
    created: list[Lesson] = []
    for it in items:
        text = it["lesson"].strip()
        if pending + len(created) >= MAX_PENDING or any(similar(text, k) for k in known):
            continue
        row = Lesson(
            org_id=org_id, agent_id=agent_id, status="pending", source=source, kind="rule", title=it.get("title", "")[:120], content=text,
            rationale=it.get("why", ""), conversation_id=conversation_id, message_id=message_id, run_id=run_id,
        )
        session.add(row)
        known.append(text)
        created.append(row)
    if created:
        await session.flush()
    return created


KIND_LABELS = {"rule": "Rule", "fact": "Fact", "example": "Example", "correction": "Correction"}


def memory_text(lesson: Lesson) -> str:
    """How a lesson reads inside the agent's memory (and therefore its prompt)."""
    kind = lesson.kind or "rule"
    content = (lesson.content or "").strip()
    prompt = (lesson.prompt or "").strip()
    if kind == "example" and prompt:
        return f'Example of an ideal answer. When asked something like: "{prompt}"\nAnswer like this: {content}'
    if kind == "correction":
        return f'Correction: do not repeat this mistake: "{prompt}". Instead: {content}' if prompt else f"Correction: {content}"
    if kind == "fact":
        return f"Fact: {content}"
    return content


def memory_tags(lesson: Lesson) -> list[str]:
    return [f"kind:{lesson.kind or 'rule'}"]


async def approve(session: AsyncSession, lesson: Lesson, agent: Agent, *, source: str = "learned") -> Memory:
    """Turn a lesson into an agent memory (taught/learned memories are always injected, see runner)."""
    if await agent_memory_count(session, lesson.org_id, agent.id) >= MAX_MEMORIES:
        raise ValueError(f"Memory limit reached ({MAX_MEMORIES}). Delete old memories or distill them into a skill first.")
    mem = Memory(
        org_id=lesson.org_id, scope="agent", agent_id=agent.id, key=lesson.title, content=memory_text(lesson), tags=memory_tags(lesson),
        source=source, run_id=lesson.run_id,
    )
    session.add(mem)
    await session.flush()
    lesson.status, lesson.memory_id = "approved", mem.id
    return mem


# ------------------------------------------------------------------ chat hooks
async def _last_exchange(session: AsyncSession, conversation_id: str, upto_message_id: str | None = None) -> tuple[str, str, str, str | None]:
    """(user_text, assistant_text, earlier_history, assistant_message_id) for the latest (or given) assistant answer."""
    msgs = (await session.execute(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at))).scalars().all()
    idx = next((i for i in range(len(msgs) - 1, -1, -1) if msgs[i].role == "assistant" and (upto_message_id is None or msgs[i].id == upto_message_id)), None)
    if idx is None:
        return "", "", "", None
    user = next((m for m in reversed(msgs[:idx]) if m.role == "user"), None)
    earlier = msgs[max(0, idx - 7) : max(0, idx - 1)]
    hist = "\n".join(f"{m.role}: {m.content[:500]}" for m in earlier)
    return (user.content if user else ""), msgs[idx].content, hist, msgs[idx].id


async def learn_from_message(session: AsyncSession, org: Organization, agent: Agent, conversation_id: str, message_id: str | None = None, *, hint: str = "", negative: bool = False, source: str = "auto") -> list[Lesson]:
    user_text, answer, hist, mid = await _last_exchange(session, conversation_id, message_id)
    if not user_text or not answer:
        return []
    items = await reflect(session, org, agent, user_text, answer, history=hist, hint=hint, negative=negative)
    if not items and hint.strip():  # feedback with a note: keep the note itself as the lesson
        items = [{"title": " ".join(hint.split()[:6]), "lesson": hint.strip(), "why": "Your feedback on an answer."}]
    return await propose(session, org.id, agent.id, items, source=source, conversation_id=conversation_id, message_id=mid)


async def _auto_learn(run_id: str) -> None:
    try:
        async with SessionLocal() as s:
            run = await s.get(Run, run_id)
            if not run or run.status != "succeeded" or not run.conversation_id or run.target_type != "agent":
                return
            agent = await s.get(Agent, run.target_id)
            org = await s.get(Organization, run.org_id)
            if not agent or not org or not (agent.settings or {}).get("auto_learn"):
                return
            made = await learn_from_message(s, org, agent, run.conversation_id, source="auto")
            await s.commit()
            if made:
                log.info("auto-learn: %d lesson(s) proposed for agent %s", len(made), agent.id)
    except Exception:  # never let learning break a run
        log.exception("auto-learn failed for run %s", run_id)


def schedule_auto_learn(run_id: str) -> None:
    task = asyncio.create_task(_auto_learn(run_id))
    _bg.add(task)
    task.add_done_callback(_bg.discard)


# ------------------------------------------------------------------ skill distillation
DISTILL_SYSTEM = """You write skills for an AI agent. A skill is a markdown instruction pack the agent always follows.
Given a list of lessons taught to the agent, merge duplicates, resolve conflicts in favour of the newest, group them under short headings, and write clear imperative instructions.
Return ONLY the markdown body of the skill (no title line, no code fences)."""


def fallback_playbook(lessons: list[str]) -> str:
    return "## Rules to follow\n" + "\n".join(f"- {t.strip()}" for t in lessons)


async def distill(session: AsyncSession, org: Organization, agent: Agent, user_id: str | None) -> Skill:
    mems = (
        await session.execute(
            select(Memory).where(Memory.org_id == org.id, Memory.agent_id == agent.id, Memory.scope == "agent", Memory.source.in_(["user", "learned"])).order_by(Memory.created_at)
        )
    ).scalars().all()
    if not mems:
        raise ValueError("Nothing to distill yet - teach the agent or approve some lessons first.")
    lessons = [f"{(m.key + ': ') if m.key else ''}{m.content}" for m in mems][-200:]
    body = ""
    try:
        text, provider_key = await _complete(session, org, agent, DISTILL_SYSTEM, "Lessons (oldest first):\n" + "\n".join(f"- {t}" for t in lessons), 2500)
        body = "" if provider_key == "mock" else text.strip()
    except LLMError:
        body = ""
    instructions = body or fallback_playbook(lessons)
    name = f"{agent.name} playbook"[:120]
    skill = (await session.execute(select(Skill).where(Skill.org_id == org.id, Skill.name == name))).scalars().first()
    description = f"Lessons learned by {agent.name} ({len(lessons)} distilled)."
    if skill:
        skill.instructions, skill.description = instructions[:50000], description
    else:
        skill = Skill(org_id=org.id, name=name, description=description, instructions=instructions[:50000], tags=["trained"], created_by=user_id)
        session.add(skill)
        await session.flush()
    if skill.id not in (agent.skill_ids or []):
        agent.skill_ids = [*(agent.skill_ids or []), skill.id]
    return skill
