"""Plain-English → schedule.

`parse_schedule("every weekday at 9am")` → cron `0 9 * * 1-5`. This deterministic parser is the offline fallback for
the AI scheduler and also *validates* what a model proposes: the model's cron is only trusted if croniter accepts it.

`parse_schedule` handles recurring schedules only; `parse_when` also understands one-time phrases ("tomorrow at 3pm",
"in 2 hours", "on Dec 5 at 10:00", "next friday") and is what the scheduler assistant and the agent tool use. Anything the
parser does not understand returns None instead of guessing, so the user is asked to rephrase rather than getting a wrong
schedule.
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
    trigger_type: str  # "schedule" (cron) | "interval" | "once"
    cron: str = ""
    interval_minutes: int = 0
    run_at: datetime | None = None  # UTC, only for "once"
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


# ------------------------------------------------------------------ one-time schedules
_RECURRING_RE = re.compile(
    r"\b(?:every|each|daily|weekly|monthly|hourly|nightly|weekdays|weekends|once a (?:day|week|month)|"
    r"working days|business days|(?:sun|mon|tues|wednes|thurs|fri|satur)days)\b"
    r"|\bmon(?:day)?\s*(?:-|to|through|thru)\s*fri",
    re.I,
)
_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MONTH_RE = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_IN_RE = re.compile(r"\bin\s+(\d+|an?|one|half an?)\s*(minutes?|mins?|hours?|hrs?|days?|weeks?)\b", re.I)
_REL_DAY_RE = re.compile(r"\b(today|tonight|tomorrow|day after tomorrow)\b", re.I)
_NEXT_DAY_RE = re.compile(rf"\b(?:(next|this|coming)\s+|on\s+)({_DAY_RE})\b", re.I)
_ISO_DATE_RE = re.compile(r"\b(?:on\s+)?(\d{4})-(\d{2})-(\d{2})\b")
_MD_RE = re.compile(rf"\b(?:on\s+)?(?:{_MONTH_RE}\s+(\d{{1,2}})(?:st|nd|rd|th)?|(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH_RE})(?:,?\s+(\d{{4}}))?\b", re.I)


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def parse_once(text: str, tz: str = "UTC", now: datetime | None = None) -> Schedule | None:
    """One-time schedule ("tomorrow at 3pm", "in 2 hours", "on 2026-12-05 at 10:00", "next friday", "at 5pm"), or None."""
    text = (text or "").strip()
    if not text or _RECURRING_RE.search(text):
        return None
    zone = _zone(tz)
    now = (now or datetime.now(timezone.utc)).astimezone(zone)
    low = text.lower()
    spans: list[tuple[int, int]] = []
    notes: list[str] = []

    if m := _IN_RE.search(low):
        raw = m.group(1)
        n = 0.5 if raw.startswith("half") else 1 if raw in ("a", "an", "one") else int(raw)
        unit = m.group(2)[0]
        minutes = n * {"m": 1, "h": 60, "d": 1440, "w": 10080}[unit]
        if minutes < 1 or minutes > MAX_INTERVAL_MINUTES * 12:
            return None
        at = now + timedelta(minutes=minutes)
        return Schedule("once", run_at=at.astimezone(timezone.utc).replace(second=0, microsecond=0), spans=[m.span()])

    clock = _clock(low)
    day: datetime | None = None
    if m := _ISO_DATE_RE.search(low):
        try:
            day = now.replace(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
        except ValueError:
            return None
        spans.append(m.span())
    elif m := _MD_RE.search(low):
        mon = (m.group(1) or m.group(4))[:3]
        dom = int(m.group(2) or m.group(3))
        year = int(m.group(5)) if m.group(5) else now.year
        try:
            day = now.replace(year=year, month=_MONTHS[mon], day=dom)
        except ValueError:
            return None
        if not m.group(5) and day.date() < now.date():
            day = day.replace(year=year + 1)
        spans.append(m.span())
    elif m := _REL_DAY_RE.search(low):
        word = m.group(1)
        day = now + timedelta(days={"today": 0, "tonight": 0, "tomorrow": 1, "day after tomorrow": 2}[word])
        if word == "tonight" and not clock:
            clock = (21, 0, [])
        spans.append(m.span())
    elif m := _NEXT_DAY_RE.search(low):
        first = m.group(2).lower()
        if first in _WORDLIKE and not m.group(0).lower().startswith(("on", "next", "this", "coming")):
            return None
        target = _DAYS[re.match(_DAY_RE, first).group(0)]
        today = (now.weekday() + 1) % 7  # python Monday=0 -> cron Sunday=0
        ahead = (target - today) % 7
        if m.group(1) and m.group(1).lower() == "next" and ahead == 0:
            ahead = 7
        day = now + timedelta(days=ahead)
        spans.append(m.span())

    if not day and not clock:
        return None
    if clock:
        spans += clock[2]
    hour, minute = (clock[0], clock[1]) if clock else (9, 0)
    if not clock:
        notes.append("No time was given, so 09:00 was used.")
    if not day:  # only a time: the next time the clock shows it
        day = now if (now.hour, now.minute) < (hour, minute) else now + timedelta(days=1)
    at = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if at <= now:
        if spans and day.date() == now.date() and not _REL_DAY_RE.search(low) and not _ISO_DATE_RE.search(low):
            at += timedelta(days=7 if _NEXT_DAY_RE.search(low) else 1)
        else:
            return None  # an explicit date/time that is already in the past
    return Schedule("once", run_at=at.astimezone(timezone.utc), spans=spans, notes=notes)


def parse_when(text: str, tz: str = "UTC", now: datetime | None = None) -> Schedule | None:
    """Recurring schedule when the text says so ("every", "daily", "mondays"...), otherwise a one-time schedule.

    "on friday at 5pm" / "next friday" mean one specific day; "every friday" / "on fridays" repeat."""
    if _RECURRING_RE.search(text or ""):
        return parse_schedule(text)
    return parse_once(text, tz, now) or parse_schedule(text)


def only_clock(text: str) -> bool:
    """The text names a time of day but no day/date/offset ("make it 10am instead")."""
    low = (text or "").lower()
    return bool(_clock(low)) and not any(r.search(low) for r in (_IN_RE, _REL_DAY_RE, _NEXT_DAY_RE, _ISO_DATE_RE, _MD_RE))


def retime_cron(cron: str, text: str) -> str | None:
    """Move a daily/weekly/monthly cron to the time of day mentioned in the text, keeping its days."""
    clock = _clock((text or "").lower())
    f = (cron or "").split()
    if not clock or len(f) != 5 or not (f[0].isdigit() and f[1].isdigit()):
        return None
    return " ".join([str(clock[1]), str(clock[0]), *f[2:]])


def is_past_phrase(text: str, tz: str = "UTC", now: datetime | None = None) -> bool:
    """True when the text names a concrete date/time that has already passed (so the user can be told why)."""
    low = (text or "").lower()
    return bool(_ISO_DATE_RE.search(low) or _MD_RE.search(low)) and parse_once(text, tz, now) is None


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


def describe(trigger_type: str, cron: str = "", interval_minutes: int = 0, tz: str = "UTC", run_at: datetime | None = None) -> str:
    suffix = f" ({tz})" if tz and tz != "UTC" else " (UTC)"
    if trigger_type == "once":
        if not run_at:
            return "Once (no time set)"
        return f"Once on {run_at.astimezone(_zone(tz)).strftime('%a %d %b %Y at %H:%M')}{suffix}"
    if trigger_type == "webhook":
        return "When its webhook URL is called"
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


def next_runs(trigger_type: str, cron: str, interval_minutes: int, tz: str, count: int = 3, now: datetime | None = None, run_at: datetime | None = None) -> list[datetime]:
    now = now or datetime.now(timezone.utc)
    if trigger_type == "once":
        return [run_at] if run_at and run_at > now else []
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
