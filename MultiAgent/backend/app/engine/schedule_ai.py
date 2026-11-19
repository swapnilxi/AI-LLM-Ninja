"""Scheduler with AI: turn "every weekday at 9am summarise my GitHub PRs" into an automation draft.

The model only *extracts* (task text, schedule phrase, optional cron). The schedule itself is always built or validated by
the deterministic parser in nl_schedule, so a hallucinated cron can never reach the scheduler. Offline (mock model) or on any
model failure, the rule-based parser alone produces the draft.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from . import nl_schedule
from .llm.base import LLMError
from .nl_schedule import Schedule
from .oneshot import complete, parse_json

log = logging.getLogger("agentforge.schedule_ai")

DRAFT_SYSTEM = """You turn a plain-English request into a recurring automation for an AI agent.
Return ONLY a JSON object (no prose, no code fences):
{"name": "<= 6 words", "task": "what the agent should do on EVERY run: imperative, self-contained, WITHOUT the schedule wording", "schedule": "the schedule phrase, e.g. 'every weekday at 9am'", "cron": "equivalent 5-field cron expression"}
Only recurring schedules are supported (no one-time reminders). If the request has no recurring schedule, set "schedule" and "cron" to "".
Today is {today}. The user's timezone is {tz}."""


def _name(task: str) -> str:
    words = task.replace("\n", " ").split()
    return (" ".join(words[:7]) + ("…" if len(words) > 7 else ""))[:120] or "Scheduled task"


def valid_tz(tz: str) -> str:
    try:
        ZoneInfo(tz)
        return tz
    except Exception:
        return "UTC"


async def draft(session: AsyncSession, org: Any, text: str, tz: str) -> dict[str, Any]:
    """Return {name, task, trigger_type, cron, interval_minutes, summary, next_runs, notes, engine}."""
    tz = valid_tz(tz or "UTC")
    text = " ".join(text.split())[:2000]
    engine, ai = "rules", None
    try:
        raw, provider = await complete(
            session, org, DRAFT_SYSTEM.replace("{today}", datetime.now(timezone.utc).strftime("%Y-%m-%d (%A)")).replace("{tz}", tz), text, max_tokens=400
        )
        if provider != "mock":
            ai = parse_json(raw, dict)
    except LLMError as exc:
        log.info("schedule draft fell back to rules: %s", exc)
    except Exception:
        log.exception("schedule draft model call failed")

    sched: Schedule | None = None
    task = name = ""
    if ai:
        engine = "ai"
        task, name = str(ai.get("task") or "").strip(), str(ai.get("name") or "").strip()
        sched = nl_schedule.parse_schedule(str(ai.get("schedule") or "")) or nl_schedule.parse_schedule(text)
        if not sched and nl_schedule.valid_cron(str(ai.get("cron") or "").strip()):  # unusual phrasing: trust the cron only if croniter accepts it
            sched = Schedule("schedule", cron=str(ai["cron"]).strip())
    else:
        sched = nl_schedule.parse_schedule(text)
        if sched:
            task = nl_schedule.strip_spans(text, sched.spans)
    task = (task or text)[:4000]
    notes = list(sched.notes) if sched else []
    if not sched:
        notes.append(
            "I could not find a recurring schedule in that. Try 'every weekday at 9am', 'daily at 18:00', 'every monday at 8:30', "
            "'every 2 hours' or 'monthly on the 1st'. One-time reminders are not supported."
        )
    trigger = sched.trigger_type if sched else "manual"
    cron, interval = (sched.cron, sched.interval_minutes) if sched else ("", 0)
    return {
        "name": (name or _name(task))[:120],
        "task": task,
        "trigger_type": trigger,
        "cron": cron,
        "interval_minutes": interval,
        "timezone": tz,
        "summary": nl_schedule.describe(trigger, cron, interval, tz),
        "next_runs": [d.isoformat() for d in nl_schedule.next_runs(trigger, cron, interval, tz)],
        "notes": notes,
        "engine": engine,
    }
