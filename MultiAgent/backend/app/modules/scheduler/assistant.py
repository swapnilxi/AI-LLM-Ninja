"""Scheduling assistant: plain English (one shot, or a conversation) -> a schedule draft.

The model only *extracts* (task text, schedule phrase, agent). The schedule itself is always built or validated by the
deterministic parser in nl_parser, so a hallucinated cron or date can never reach the scheduler. Offline (mock model) or
on any model failure, a rule-based engine produces the same result shape.

Nothing here saves anything: the UI shows the draft and creates the schedule through the normal endpoint.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.llm.base import LLMError
from app.engine.oneshot import complete, parse_json
from app.modules.scheduler import nl_parser
from app.modules.scheduler.nl_parser import Schedule

log = logging.getLogger("agentforge.schedule_ai")

EXAMPLES = "'every weekday at 9am', 'daily at 18:00', 'every 2 hours', 'monthly on the 1st', 'tomorrow at 3pm', 'in 2 hours' or 'on 2026-12-05 at 10:00'"

DRAFT_SYSTEM = """You turn a plain-English request into a schedule for an AI agent.
Return ONLY a JSON object (no prose, no code fences):
{"name": "<= 6 words", "task": "what the agent should do on EVERY run: imperative, self-contained, WITHOUT the schedule wording", "schedule": "the schedule phrase, e.g. 'every weekday at 9am' or 'tomorrow at 3pm'", "cron": "equivalent 5-field cron expression for recurring schedules, else empty"}
If the request has no schedule, set "schedule" and "cron" to "".
Today is {today}. The user's timezone is {tz}."""

CHAT_SYSTEM = """You are the scheduling assistant inside AgentForge. You help the user set up a schedule that runs one of their AI agents.
A schedule needs:
1. task - what the agent should do on each run: imperative and self-contained, without the timing words
2. when - recurring ('every weekday at 9am', 'every 2 hours', 'monthly on the 1st') or one-time ('tomorrow at 3pm', 'in 2 hours', 'on 2026-12-05 at 10:00')
3. agent - which agent runs it (default: {default_agent})

Agents (id | name | description):
{agents}

Current draft (JSON, may be empty): {draft}
Today is {today}; the user's timezone is {tz}.

Read the conversation and return ONLY a JSON object:
{{"task": "new task text, or empty to keep the draft's", "when": "schedule phrase, or empty to keep the draft's", "agent_id": "an id from the list, or empty to keep", "name": "<= 6 words, or empty", "intent": "update|confirm|cancel|question", "reply": "one or two short sentences: ask for what is missing or answer the question"}}
Use intent "confirm" only when the user clearly agrees to create a draft that already has a task and a time."""

_CONFIRM_RE = re.compile(r"^\s*(?:yes|yep|yeah|yup|sure|ok(?:ay)?|confirm(?:ed)?|create(?: it)?|do it|go ahead|looks good|sounds good|perfect|great|save(?: it)?|ship it)\b", re.I)
_CANCEL_RE = re.compile(r"^\s*(?:cancel|never ?mind|start over|reset|forget it|scrap that)\b", re.I)
_CHANGE_RE = re.compile(r"^\s*(?:actually|instead|change (?:the )?task to|change it to|make it|task\s*[:=-])\s*", re.I)
_FILLER_RE = re.compile(
    r"^\s*(?:(?:please|pls|hey|hi|can you|could you|would you|i want(?: you)? to|i'd like(?: you)? to|i need(?: you)? to|"
    r"(?:set up|create|add|make)\s+(?:a\s+)?(?:new\s+)?(?:schedule|scheduled task|job|automation|reminder)\s*(?:to|that|for)?|"
    r"schedule(?:\s+(?:a|an))?(?:\s+(?:task|job|run))?\s*(?:to|that|for)?)\s+)+",
    re.I,
)


def _name(task: str) -> str:
    words = task.replace("\n", " ").split()
    return (" ".join(words[:7]) + ("…" if len(words) > 7 else ""))[:120] or "Scheduled task"


def valid_tz(tz: str) -> str:
    try:
        ZoneInfo(tz)
        return tz
    except Exception:
        return "UTC"


def _today(tz: str) -> str:
    return datetime.now(timezone.utc).astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d (%A) %H:%M")


def schedule_fields(sched: Schedule | None, tz: str) -> dict[str, Any]:
    """The schedule part of a draft, always derived from a parsed (validated) Schedule."""
    trigger = sched.trigger_type if sched else "manual"
    cron, interval, run_at = (sched.cron, sched.interval_minutes, sched.run_at) if sched else ("", 0, None)
    return {
        "trigger_type": trigger,
        "cron": cron,
        "interval_minutes": interval,
        "run_at": run_at.isoformat() if run_at else None,
        "timezone": tz,
        "summary": nl_parser.describe(trigger, cron, interval, tz, run_at),
        "next_runs": [d.isoformat() for d in nl_parser.next_runs(trigger, cron, interval, tz, run_at=run_at)],
    }


def _no_schedule_note(text: str, tz: str) -> str:
    if nl_parser.is_past_phrase(text, tz):
        return "That date and time has already passed. Pick a time in the future."
    return f"I could not find a time in that. Try {EXAMPLES}."


async def _model_json(session: AsyncSession, org: Any, system: str, user: str, max_tokens: int) -> dict | None:
    """Ask the configured model for a JSON object. None when offline (mock), on failure or on unparsable output."""
    try:
        raw, provider = await complete(session, org, system, user, max_tokens=max_tokens)
        if provider != "mock":
            return parse_json(raw, dict)
    except LLMError as exc:
        log.info("scheduling assistant fell back to rules: %s", exc)
    except Exception:
        log.exception("scheduling assistant model call failed")
    return None


# ====================================================================== one shot: text -> draft
async def draft(session: AsyncSession, org: Any, text: str, tz: str) -> dict[str, Any]:
    """Return {name, task, trigger_type, cron, interval_minutes, run_at, timezone, summary, next_runs, notes, engine}."""
    tz = valid_tz(tz or "UTC")
    text = " ".join(text.split())[:2000]
    ai = await _model_json(session, org, DRAFT_SYSTEM.replace("{today}", _today(tz)).replace("{tz}", tz), text, 400)

    sched: Schedule | None = None
    task = name = ""
    engine = "rules"
    if ai:
        engine = "ai"
        task, name = str(ai.get("task") or "").strip(), str(ai.get("name") or "").strip()
        sched = nl_parser.parse_when(str(ai.get("schedule") or ""), tz) or nl_parser.parse_when(text, tz)
        if not sched and nl_parser.valid_cron(str(ai.get("cron") or "").strip()):  # unusual phrasing: trust the cron only if croniter accepts it
            sched = Schedule("schedule", cron=str(ai["cron"]).strip())
    else:
        sched = nl_parser.parse_when(text, tz)
        if sched:
            task = nl_parser.strip_spans(text, sched.spans)
    task = (task or text)[:4000]
    notes = list(sched.notes) if sched else [_no_schedule_note(text, tz)]
    return {"name": (name or _name(task))[:120], "task": task, **schedule_fields(sched, tz), "notes": notes, "engine": engine}


# ====================================================================== conversation
@dataclass
class AgentRef:
    id: str
    name: str
    description: str = ""


def _clean_draft(raw: dict[str, Any] | None, agents: list[AgentRef], default: AgentRef, tz: str) -> dict[str, Any]:
    """Re-validate the draft the client sent back (it is untrusted): keep only known fields with valid values."""
    raw = raw or {}
    by_id = {a.id: a for a in agents}
    agent = by_id.get(str(raw.get("target_id") or "")) or default
    sched: Schedule | None = None
    trig = raw.get("trigger_type")
    if trig == "schedule" and nl_parser.valid_cron(str(raw.get("cron") or "")):
        sched = Schedule("schedule", cron=str(raw["cron"]))
    elif trig == "interval" and isinstance(raw.get("interval_minutes"), int) and nl_parser.MIN_INTERVAL_MINUTES <= raw["interval_minutes"] <= nl_parser.MAX_INTERVAL_MINUTES:
        sched = Schedule("interval", interval_minutes=raw["interval_minutes"])
    elif trig == "once" and raw.get("run_at"):
        try:
            at = datetime.fromisoformat(str(raw["run_at"]).replace("Z", "+00:00"))
            at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
            if at > datetime.now(timezone.utc):
                sched = Schedule("once", run_at=at.astimezone(timezone.utc))
        except ValueError:
            pass
    return {"task": str(raw.get("task") or "").strip()[:4000], "name": str(raw.get("name") or "").strip()[:120], "agent": agent, "sched": sched}


def _mentioned_agent(text: str, agents: list[AgentRef]) -> tuple[AgentRef | None, str]:
    """An agent named in the text, and the text with that mention (plus 'ask X to' / 'with X') removed."""
    for a in sorted(agents, key=lambda x: -len(x.name)):
        name = re.escape(a.name.strip())
        if not name:
            continue
        pat = rf"(?:\b(?:ask|have|let|get|tell|with|using|use|by|via|as)\s+)?(?:the\s+)?(?:agent\s+)?\b{name}\b(?:\s+agent)?(?:\s+to\b)?"
        if m := re.search(pat, text, re.I):
            rest = (text[: m.start()] + " " + text[m.end() :]).strip()
            return a, re.sub(r"\s+", " ", rest).strip(" ,.;:-")
    return None, text


def _rules_extract(msg: str, state: dict[str, Any], agents: list[AgentRef], tz: str) -> dict[str, Any]:
    """Rule-based equivalent of the model's extraction for one user message."""
    out: dict[str, Any] = {"task": "", "when": "", "agent_id": "", "name": "", "intent": "update", "reply": ""}
    words = msg.split()
    complete_draft = bool(state["task"] and state["sched"])
    if _CANCEL_RE.match(msg):
        out["intent"] = "cancel"
        return out
    if complete_draft and _CONFIRM_RE.match(msg) and len(words) <= 6:
        out["intent"] = "confirm"
        return out

    agent, rest = _mentioned_agent(msg, agents)
    if agent:
        out["agent_id"] = agent.id
    sched = nl_parser.parse_when(rest, tz)
    retimed = None
    if sched and sched.trigger_type == "once" and state["sched"] and state["sched"].trigger_type == "schedule" and nl_parser.only_clock(rest):
        retimed = nl_parser.retime_cron(state["sched"].cron, rest)  # "make it 10am instead" keeps the recurrence
    if sched:
        out["when"] = rest if not retimed else ""
        out["_retimed_cron"] = retimed
        rest = nl_parser.strip_spans(rest, sched.spans)
    elif nl_parser.is_past_phrase(rest, tz):
        out["when"] = rest  # explained in the reply; the task is not overwritten with the date text
        rest = ""
    rest = _CHANGE_RE.sub("", _FILLER_RE.sub("", rest)).strip(" ,.;:-")
    rest = re.sub(r"^(?:to|that|for)\s+", "", rest, flags=re.I)
    rest = re.sub(r"\b(?:instead|please|pls|then|actually|now|too|also)\b", " ", rest, flags=re.I)
    rest = re.sub(r"\s+", " ", rest).strip(" ,.;:-")
    meaningful = len(rest.split()) >= 2
    if meaningful:
        changing = bool(_CHANGE_RE.match(msg))
        if sched or not state["task"] or changing or (complete_draft and not agent):
            out["task"] = rest
        elif not state["sched"]:
            out["when"] = msg  # they were answering "when?" but the parser did not understand it
    if not (out["task"] or out["when"] or out["agent_id"] or out.get("_retimed_cron")):
        out["intent"] = "question"
    return out


def _reply_for(state: dict[str, Any], default: AgentRef, notes: list[str]) -> tuple[str, list[str]]:
    missing = [k for k, ok in (("task", bool(state["task"])), ("when", bool(state["sched"]))) if not ok]
    agent = state["agent"]
    note = (" " + " ".join(notes)) if notes else ""
    if not missing:
        f = schedule_fields(state["sched"], state["tz"])
        nxt = f["next_runs"][0] if f["next_runs"] else None
        when = datetime.fromisoformat(nxt).astimezone(ZoneInfo(state["tz"])).strftime("%a %d %b, %H:%M") if nxt else "n/a"
        return (
            f"Here is the plan: **{state['name'] or _name(state['task'])}**. {agent.name} will {state['task'][0].lower() + state['task'][1:]}. "
            f"{f['summary']}, next run {when}.{note} Say **yes** to create it, or tell me what to change.",
            missing,
        )
    if missing == ["when"]:
        return f"Got it: {agent.name} will {state['task'][0].lower() + state['task'][1:]}. When should it run? For example {EXAMPLES}.{note}", missing
    if missing == ["task"]:
        f = schedule_fields(state["sched"], state["tz"])
        return f"{f['summary']}. What should {agent.name} do each time?{note}", missing
    return f"What would you like to schedule? Tell me the task and when, e.g. 'every weekday at 9am summarise my GitHub PRs'. It runs as {default.name} unless you name another agent.{note}", missing


async def converse(
    session: AsyncSession, org: Any, *, messages: list[dict[str, str]], draft_in: dict[str, Any] | None, agents: list[AgentRef], default_agent: AgentRef, tz: str,
) -> dict[str, Any]:
    """One assistant turn. Returns {reply, draft, ready, missing, action, engine}."""
    tz = valid_tz(tz or "UTC")
    state = {**_clean_draft(draft_in, agents, default_agent, tz), "tz": tz}
    msg = " ".join(str(messages[-1].get("content") or "").split())[:2000] if messages else ""
    engine = "rules"
    notes: list[str] = []

    snapshot = {"task": state["task"], "name": state["name"], "agent_id": state["agent"].id, **(schedule_fields(state["sched"], tz) if state["sched"] else {})}
    agent_lines = "\n".join(f"{a.id} | {a.name} | {a.description[:120]}" for a in agents[:50]) or f"{default_agent.id} | {default_agent.name} |"
    system = CHAT_SYSTEM.format(default_agent=default_agent.name, agents=agent_lines, draft=json.dumps(snapshot), today=_today(tz), tz=tz)
    convo = "\n".join(f"{m.get('role', 'user').upper()}: {str(m.get('content') or '')[:1500]}" for m in messages[-12:])
    ai = await _model_json(session, org, system, convo, 500)
    if ai and str(ai.get("intent") or "") in ("update", "confirm", "cancel", "question"):
        engine = "ai"
        ex = {k: str(ai.get(k) or "").strip() for k in ("task", "when", "agent_id", "name", "intent", "reply")}
        if ex["intent"] == "confirm" and not (state["task"] and state["sched"]):
            ex["intent"] = "update"
    else:
        ex = _rules_extract(msg, state, agents, tz)

    if ex["intent"] == "cancel":
        return {"reply": "Okay, I cleared that. What would you like to schedule?", "draft": None, "ready": False, "missing": ["task", "when"], "action": None, "engine": engine}

    by_id = {a.id: a for a in agents}
    if ex.get("agent_id") in by_id:
        state["agent"] = by_id[ex["agent_id"]]
    if ex.get("task"):
        state["task"] = ex["task"][:4000]
        if not ex.get("name"):
            state["name"] = ""
    if ex.get("name"):
        state["name"] = ex["name"][:120]
    if ex.get("_retimed_cron"):
        state["sched"] = Schedule("schedule", cron=ex["_retimed_cron"])
    elif ex.get("when"):
        sched = nl_parser.parse_when(ex["when"], tz)
        if sched:
            state["sched"] = sched
            notes += sched.notes
        else:
            notes.append(_no_schedule_note(ex["when"], tz))

    ready = bool(state["task"] and state["sched"])
    action = "create" if ex["intent"] == "confirm" and ready else None
    if action:
        reply, missing = "Creating your schedule now.", []
    else:
        reply, missing = _reply_for(state, default_agent, notes)
        if engine == "ai" and ex["intent"] == "question" and ex.get("reply"):
            reply = ex["reply"]
        elif engine == "ai" and missing and ex.get("reply") and not notes:
            reply = ex["reply"]

    out_draft = None
    if state["task"] or state["sched"]:
        out_draft = {
            "name": state["name"] or (_name(state["task"]) if state["task"] else ""),
            "task": state["task"],
            **schedule_fields(state["sched"], tz),
            "notes": notes,
            "target_type": "agent",
            "target_id": state["agent"].id,
            "target_name": state["agent"].name,
        }
    return {"reply": reply, "draft": out_draft, "ready": ready, "missing": missing, "action": action, "engine": engine}
