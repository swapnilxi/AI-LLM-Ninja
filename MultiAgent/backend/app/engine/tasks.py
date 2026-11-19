"""To-dos: "text to task" extraction, creation and the prompt that hands a task (with its context) to an agent.

Extraction asks the org's default model for a JSON list of action items. With the offline mock model, or when the
model errors or returns something unparseable, a rule-based extractor (checklists, "next steps" lists, imperative
bullets, "need to / should / remember to" sentences) is used instead, so the feature works without any API key.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Task
from .learning import similar
from .llm.base import LLMError
from .oneshot import complete, parse_json

log = logging.getLogger("agentforge.tasks")

MAX_EXTRACT = 15
MAX_OPEN_PER_PROJECT = 1000
PRIORITIES = ("low", "normal", "high")
STATUSES = ("todo", "doing", "done")

EXTRACT_SYSTEM = """You turn text (usually an AI assistant's reply, meeting notes or an email) into a to-do list.
Extract only concrete action items that someone still has to do. Skip background, opinions, explanations and anything already done.
Rules:
- title: imperative, at most 12 words, e.g. "Send the Q3 report to finance".
- notes: optional extra detail from the text (empty string if none). Never invent facts.
- priority: "high" only if the text signals urgency, "low" only if it is optional, else "normal".
- due: a YYYY-MM-DD date only if the text states or clearly implies one, else "".
Return ONLY a JSON array (no prose, no code fences) with at most 15 items:
[{"title": "...", "notes": "...", "priority": "low|normal|high", "due": "YYYY-MM-DD or empty"}]
Return [] if there are no action items."""

_VERBS = (
    "add|analy[sz]e|apply|ask|audit|back up|book|build|call|change|check|clean|clone|close|collect|compare|configure|confirm|contact|copy|create|define|delete|deploy|"
    "design|document|download|draft|email|enable|ensure|establish|evaluate|export|fetch|find|finish|fix|follow up|gather|generate|get|implement|import|improve|"
    "install|investigate|schedule|join|label|learn|list|log|make|measure|merge|migrate|monitor|move|notify|open|order|organi[sz]e|pay|plan|post|prepare|"
    "publish|read|refactor|remove|rename|reply|report|request|research|reset|resolve|review|revoke|rotate|run|save|send|set up|setup|share|sign|split|start|submit|"
    "summari[sz]e|test|track|train|translate|try|update|upgrade|upload|verify|watch|write"
)
_BULLET = re.compile(r"^\s*(?:[-*•+]|\d{1,2}[.)])\s+(?:\[\s?\]\s*)?(.+?)\s*$")
_CHECKBOX_OPEN = re.compile(r"^\s*[-*+]\s+\[\s?\]\s+(.+?)\s*$")
_CHECKBOX_DONE = re.compile(r"^\s*[-*+]\s+\[[xX]\]\s+")
_LABELLED = re.compile(r"^\s*(?:[-*•]\s*)?(?:todo|to-do|action(?: item)?|task|next step)s?\s*[:\-]\s*(.+?)\s*$", re.I)
_HEADING = re.compile(r"^\s{0,3}(?:#{1,6}\s*|\*\*)?\s*(next steps?|action items?|to-?dos?|tasks?|follow[- ]ups?|recommendations?|steps?|checklist|things to do)\b[^\n]*$", re.I)
_NEED = re.compile(r"\b(?:need to|needs to|have to|has to|should|must|remember to|make sure to|don'?t forget to|don'?t forget about|please)\s+([^.!?\n;]{6,200})", re.I)
_HIGH = re.compile(r"\b(urgent(?:ly)?|asap|critical|immediately|high[- ]priority|blocker|top priority)\b", re.I)
_LOW = re.compile(r"\b(optional|nice to have|when (?:you )?(?:can|possible)|eventually|low[- ]priority|someday)\b", re.I)
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _clean(text: str) -> str:
    text = re.sub(r"[*_`#]+", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\s+", " ", text).strip(" -–—:;,.")


def parse_due(text: str, today: datetime | None = None) -> datetime | None:
    """Due date from an ISO date or a simple phrase (today / tomorrow / by friday / next week)."""
    today = (today or datetime.now(timezone.utc)).replace(hour=17, minute=0, second=0, microsecond=0)
    low = (text or "").lower()
    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low):
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 17, tzinfo=timezone.utc)
        except ValueError:
            return None
    if re.search(r"\b(?:by |due )?today\b", low):
        return today
    if re.search(r"\btomorrow\b", low):
        return today + timedelta(days=1)
    if re.search(r"\bnext week\b", low):
        return today + timedelta(days=7)
    if m := re.search(r"\b(?:by|on|before|due)\s+(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", low):
        delta = (_WEEKDAYS.index(m.group(1)) - today.weekday()) % 7 or 7
        return today + timedelta(days=delta)
    return None


def heuristic_tasks(text: str) -> list[dict[str, Any]]:
    """Offline extraction. Prefers explicit structure (checklists, labelled lines, 'Next steps' lists) over prose cues."""
    lines = (text or "").splitlines()
    explicit: list[str] = []
    in_list = False
    for ln in lines:
        if _CHECKBOX_DONE.match(ln):
            continue
        if _HEADING.match(ln):
            in_list = True
            continue
        if in_list and not ln.strip():
            continue
        m = _CHECKBOX_OPEN.match(ln) or _LABELLED.match(ln)
        if m:
            explicit.append(m.group(1))
            continue
        b = _BULLET.match(ln)
        if b and in_list:
            explicit.append(b.group(1))
            continue
        if in_list and ln.strip() and not b:
            in_list = False  # a prose paragraph ends the list
    found = explicit
    if not found:  # no structure: imperative bullets, then "need to / should" sentences
        for ln in lines:
            b = _BULLET.match(ln)
            if b and re.match(rf"^(?:{_VERBS})\b", _clean(b.group(1)), re.I):
                found.append(b.group(1))
        if not found:
            for m in _NEED.finditer(text or ""):
                found.append(m.group(1))
    out: list[dict[str, Any]] = []
    for raw in found:
        title = _clean(raw)
        if len(title) < 4:
            continue
        title = title[0].upper() + title[1:]
        out.append(
            {
                "title": title[:200],
                "notes": "",
                "priority": "high" if _HIGH.search(raw) else "low" if _LOW.search(raw) else "normal",
                "due": parse_due(raw),
            }
        )
    return dedupe(out)[:MAX_EXTRACT]


def dedupe(items: list[dict[str, Any]], threshold: float = 0.8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items:
        if not any(similar(it["title"], o["title"], threshold) for o in out):
            out.append(it)
    return out


def normalize(item: dict[str, Any]) -> dict[str, Any] | None:
    title = _clean(str(item.get("title") or ""))[:255]
    if len(title) < 3:
        return None
    due = item.get("due")
    if isinstance(due, str):
        due = parse_due(due)
    prio = str(item.get("priority") or "normal").lower()
    return {
        "title": title,
        "notes": str(item.get("notes") or "").strip()[:4000],
        "context": str(item.get("context") or "").strip()[:8000],
        "priority": prio if prio in PRIORITIES else "normal",
        "due": due if isinstance(due, datetime) else None,
    }


async def extract_tasks(session: AsyncSession, org: Any, text: str, hint: str = "") -> tuple[list[dict[str, Any]], str]:
    """Return (items, engine) where engine is 'ai' or 'rules'."""
    text = (text or "").strip()[:20000]
    prompt = f"Text:\n{text}\n" + (f"\nAdditional instruction from the user: {hint[:500]}\n" if hint.strip() else "")
    try:
        raw, provider = await complete(session, org, EXTRACT_SYSTEM, prompt, max_tokens=1200)
    except LLMError as exc:
        log.info("task extraction fell back to rules: %s", exc)
        provider, raw = "mock", ""
    except Exception:  # a model/network failure must never break the feature
        log.exception("task extraction model call failed")
        provider, raw = "mock", ""
    if provider != "mock":
        parsed = parse_json(raw, list)
        if parsed is not None:
            items = [n for n in (normalize(i) for i in parsed if isinstance(i, dict)) if n]
            return dedupe(items)[:MAX_EXTRACT], "ai"
    return [n for n in (normalize(i) for i in heuristic_tasks(text)) if n], "rules"


async def create_tasks(
    session: AsyncSession,
    *,
    org_id: str,
    project_id: str,
    items: list[dict[str, Any]],
    source: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    run_id: str | None = None,
    context: str = "",
    skip_duplicates: bool = True,
) -> tuple[list[Task], list[str]]:
    """Insert tasks. Returns (created, skipped_titles). Near-duplicates of open tasks are skipped."""
    open_rows = (await session.execute(select(Task.title).where(Task.org_id == org_id, Task.project_id == project_id, Task.status != "done"))).scalars().all()
    room = MAX_OPEN_PER_PROJECT - len(open_rows)
    created: list[Task] = []
    skipped: list[str] = []
    known = list(open_rows)
    for raw in items:
        it = normalize(raw)
        if not it:
            continue
        if room <= 0 or (skip_duplicates and any(similar(it["title"], k, 0.8) for k in known)):
            skipped.append(it["title"])
            continue
        ctx = "\n\n".join(x for x in [context.strip(), it["context"]] if x)[:8000]
        row = Task(
            org_id=org_id, project_id=project_id, title=it["title"], notes=it["notes"], context=ctx, priority=it["priority"], due_at=it["due"],
            source=source, conversation_id=conversation_id, message_id=message_id, run_id=run_id, created_by=user_id,
        )
        session.add(row)
        created.append(row)
        known.append(it["title"])
        room -= 1
    await session.flush()
    return created, skipped


async def open_task_count(session: AsyncSession, org_id: str, project_id: str) -> int:
    return (await session.execute(select(func.count()).select_from(Task).where(Task.org_id == org_id, Task.project_id == project_id, Task.status != "done"))).scalar_one()


def run_prompt(task: Task) -> str:
    """What an agent receives when asked to work on a task: the task plus all the context given with it."""
    parts = ["Work on the following task. When you finish, say clearly what you did and what (if anything) is left.", "", f"Task: {task.title}"]
    if task.notes.strip():
        parts += ["", "Details:", task.notes.strip()]
    meta = [f"priority: {task.priority}"] + ([f"due: {task.due_at.date().isoformat()}"] if task.due_at else [])
    parts += ["", "(" + ", ".join(meta) + ")"]
    if task.context.strip():
        parts += ["", "Context provided with this task:", task.context.strip()]
    return "\n".join(parts)
