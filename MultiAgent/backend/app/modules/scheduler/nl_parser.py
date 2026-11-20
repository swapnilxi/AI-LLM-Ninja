"""Plain-English → schedule.

`parse_schedule("every weekday at 9am")` → cron `0 9 * * 1-5`. This deterministic parser is the offline fallback for
the AI scheduler and also *validates* what a model proposes: the model's cron is only trusted if croniter accepts it.

Only recurring schedules are supported (the automation model has no one-shot trigger). Anything the parser does not
understand returns None instead of guessing, so the user is asked to rephrase rather than getting a wrong schedule.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import croniter

MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 60 * 24 * 31

_DAYS = {
    "sunday": 0, "sun": 0, "monday": 1, "mon": 1, "tuesday": 2, "tue": 2, "tues": 2, "wednesday": 3, "wed": 3,
    "thursday": 4, "thu": 4, "thur": 4, "thurs": 4, "friday": 5, "fri": 5, "saturday": 6, "sat": 6,
}
_WORDLIKE = {"sun", "sat", "wed", "mon"}  # abbreviations that are also ordinary words
_DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
_DAY_RE = r"(?:sunday|monday|tuesday|wednesday|thursday|friday|saturday|sun|mon|tues?|wed|thu(?:rs?)?|fri|sat)"
_DAY_LIST_RE = re.compile(rf"\b{_DAY_RE}s?\b(?:\s*(?:,|and|&|/)\s*{_DAY_RE}s?\b)*", re.I)
_PARTS = {"morning": (9, 0), "noon": (12, 0), "midday": (12, 0), "afternoon": (14, 0), "evening": (18, 0), "night": (21, 0), "midnight": (0, 0)}
_UNIT_MIN = {"m": 1, "min": 1, "mins": 1, "minute": 1, "minutes": 1, "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60, "d": 1440, "day": 1440, "days": 1440}

_INTERVAL_RE = re.compile(r"\bevery\s+(\d+|other)?\s*(minutes?|mins?|hours?|hrs?|days?)\b|\b(hourly)\b", re.I)
_TIME_RE = re.compile(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)(?!\w)|\bat\s+(\d{1,2})(?::(\d{2}))?\b(?!\s*(?:am|pm))", re.I)
_TIME_WORD_RE = re.compile(r"\b(?:at\s+|every\s+|each\s+|in the\s+)?(morning|noon|midday|afternoon|evening|night|midnight)\b", re.I)
_MONTHLY_RE = re.compile(r"\b(?:every|each)\s+month\b|\bmonthly\b|\bonce a month\b", re.I)
_MONTHDAY_RE = re.compile(r"\b(?:on\s+)?(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b(?:\s+(?:day\s+)?of\s+(?:the\s+|every\s+|each\s+)?month)?", re.I)


@dataclass
class Schedule:
    trigger_type: str  # "schedule" (cron) | "interval"
    cron: str = ""
    interval_minutes: int = 0
    spans: list[tuple[int, int]] = field(default_factory=list)  # where the schedule phrase sits in the input text
    notes: list[str] = field(default_factory=list)


def _clock(text: str) -> tuple[int, int, list[tuple[int, int]]] | None:
    """Time of day mentioned in the text (24h), or None."""
    m = _TIME_RE.search(text)
    if m:
        if m.group(3):  # 9am / 9:30 pm
            h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower().replace(".", "")
            if not (1 <= h <= 12) or mi > 59:
                return None
            h = (h % 12) + (12 if ap == "pm" else 0)
        else:  # at 18:30 / at 9
            h, mi = int(m.group(4)), int(m.group(5) or 0)
            if h > 23 or mi > 59:
                return None
        return h, mi, [m.span()]
    w = _TIME_WORD_RE.search(text)
    if w:
        h, mi = _PARTS[w.group(1).lower()]
        return h, mi, [w.span()]
    return None


def _days(text: str) -> tuple[str, list[tuple[int, int]]] | None:
    """Day-of-week field mentioned in the text, or None."""
    low = text.lower()
    if m := re.search(r"\b(?:every\s+|on\s+|each\s+)?week\s?days?\b|\bmon(?:day)?\s*(?:-|to|through|thru)\s*fri(?:day)?\b|\bworking days\b|\bbusiness days\b", low):
        return "1-5", [m.span()]
    if m := re.search(r"\b(?:every\s+|on\s+|each\s+)?week\s?ends?\b", low):
        return "0,6", [m.span()]
    for m in _DAY_LIST_RE.finditer(low):
        start = m.start()
        lead = re.search(r"(?:every|on|each)\s+$", low[:start])
        first = re.match(_DAY_RE, m.group(0), flags=re.I).group(0).lower()
        if first in _WORDLIKE and not lead:  # "I sat down", "the sun is up" - only a day when introduced by every/on/each
            continue
        nums = sorted({_DAYS[d.lower()] for d in re.findall(_DAY_RE, m.group(0), flags=re.I)})
        if lead:
            start = lead.start()
        return ",".join(str(n) for n in nums), [(start, m.end())]
    return None


def parse_schedule(text: str) -> Schedule | None:
    text = (text or "").strip()
    if not text:
        return None
    low = text.lower()

    # ---- fixed intervals: "every 30 minutes", "every 2 hours", "hourly", "every 3 days"
    m = _INTERVAL_RE.search(low)
    if m and not (m.group(2) and m.group(2).lower().startswith("day") and not m.group(1)):  # bare "every day" is a daily time schedule
        notes: list[str] = []
        if m.group(3):
            n, unit = 1, 60
        else:
            n = 2 if (m.group(1) or "").lower() == "other" else int(m.group(1) or 1)
            unit = _UNIT_MIN[m.group(2).lower()]
        minutes = n * unit
        if minutes < MIN_INTERVAL_MINUTES:
            notes.append(f"The minimum interval is {MIN_INTERVAL_MINUTES} minutes, so that is what was used.")
            minutes = MIN_INTERVAL_MINUTES
        if minutes > MAX_INTERVAL_MINUTES:
            return None
        if unit == 1440 and _clock(low):
            notes.append("Time of day is ignored for 'every N days' - it runs N days after the last run.")
        return Schedule("interval", interval_minutes=minutes, spans=[m.span()], notes=notes)

    clock = _clock(low)
    days = _days(low)
    spans: list[tuple[int, int]] = []
    hour, minute = (clock[0], clock[1]) if clock else (9, 0)
    if clock:
        spans += clock[2]
    notes = [] if clock else ["No time was given, so 09:00 was used."]

    # ---- monthly: "monthly on the 15th", "on the 1st of every month"
    mm = _MONTHDAY_RE.search(low)
    mo = _MONTHLY_RE.search(low)  # "twice a month" is deliberately not matched: unsupported phrasings return None
    if mm and (mo or re.search(r"\bon the\b", low[: mm.end()])) and 1 <= int(mm.group(1)) <= 31:
        spans.append(mm.span())
        if mo:
            spans.append(mo.span())
        return Schedule("schedule", cron=f"{minute} {hour} {int(mm.group(1))} * *", spans=spans, notes=notes)
    if mo:  # "monthly" / "every month" with no day
        spans.append(mo.span())
        notes.append("No day of the month was given, so the 1st was used.")
        return Schedule("schedule", cron=f"{minute} {hour} 1 * *", spans=spans, notes=notes)

    # ---- weekly / specific days
    if days:
        spans += days[1]  # "weekly" is left in the task text: "send the weekly report" keeps its meaning
        return Schedule("schedule", cron=f"{minute} {hour} * * {days[0]}", spans=spans, notes=notes)
    if wk := re.search(r"\bweekly\b|\bevery\s+week\b|\beach\s+week\b|\bonce a week\b", low):
        spans.append(wk.span())
        notes.append("No day was given, so Monday was used.")
        return Schedule("schedule", cron=f"{minute} {hour} * * 1", spans=spans, notes=notes)

    # ---- daily
    if d := re.search(r"\bdaily\b|\bevery\s?day\b|\beach day\b|\bonce a day\b|\bevery\s+(?:morning|afternoon|evening|night)\b|\bnightly\b", low):
        spans.append(d.span())
        if "nightly" in d.group(0) and not clock:
            hour, minute = 21, 0
            notes = []
        return Schedule("schedule", cron=f"{minute} {hour} * * *", spans=spans, notes=notes)

    return None


# ------------------------------------------------------------------ helpers shared with the API and the agent tool
def strip_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Remove the schedule phrase from the text, leaving the task description."""
    keep, last = [], 0
    for a, b in sorted(spans):
        if a < last:
            continue
        keep.append(text[last:a])
        last = b
    keep.append(text[last:])
    out = re.sub(r"\s+", " ", "".join(keep)).strip(" ,.;:-")
    out = re.sub(r"^(?:and|then|please|to)\s+", "", out, flags=re.I).strip(" ,.;:-")
    out = re.sub(r"\s+(?:and|then|on|at|every|each|in the)$", "", out, flags=re.I).strip(" ,.;:-")
    return out


def valid_cron(expr: str) -> bool:
    return bool(expr) and len(expr.split()) == 5 and croniter.is_valid(expr)


def describe(trigger_type: str, cron: str = "", interval_minutes: int = 0, tz: str = "UTC") -> str:
    suffix = f" ({tz})" if tz and tz != "UTC" else " (UTC)"
    if trigger_type == "interval" and interval_minutes:
        if interval_minutes % 1440 == 0:
            n = interval_minutes // 1440
            return "Every day" if n == 1 else f"Every {n} days"
        if interval_minutes % 60 == 0:
            n = interval_minutes // 60
            return "Every hour" if n == 1 else f"Every {n} hours"
        return f"Every {interval_minutes} minutes"
    if trigger_type == "schedule" and cron:
        f = cron.split()
        if len(f) == 5 and f[0].isdigit() and f[1].isdigit() and f[3] == "*":
            at = f"{int(f[1]):02d}:{int(f[0]):02d}"
            dom, dow = f[2], f[4]
            if dom == "*" and dow == "*":
                return f"Every day at {at}{suffix}"
            if dom == "*" and dow == "1-5":
                return f"Every weekday at {at}{suffix}"
            if dom == "*" and dow == "0,6":
                return f"Every weekend at {at}{suffix}"
            if dom == "*" and re.fullmatch(r"[0-6](,[0-6])*", dow):
                return f"Every {', '.join(_DAY_NAMES[int(d)] for d in dow.split(','))} at {at}{suffix}"
            if dom.isdigit() and dow == "*":
                return f"Monthly on day {dom} at {at}{suffix}"
        return f"Cron {cron}{suffix}"
    return "Manual (runs only when started)"


def next_runs(trigger_type: str, cron: str, interval_minutes: int, tz: str, count: int = 3, now: datetime | None = None) -> list[datetime]:
    now = now or datetime.now(timezone.utc)
    if trigger_type == "interval" and interval_minutes > 0:
        return [now + timedelta(minutes=interval_minutes * (i + 1)) for i in range(count)]
    if trigger_type == "schedule" and valid_cron(cron):
        try:
            zone = ZoneInfo(tz or "UTC")
        except Exception:
            zone = ZoneInfo("UTC")
        it = croniter(cron, now.astimezone(zone))
        return [it.get_next(datetime).astimezone(timezone.utc) for _ in range(count)]
    return []
