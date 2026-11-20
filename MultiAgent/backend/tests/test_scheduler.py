"""Scheduler module: one-time schedules, scheduling by chat (offline rules engine), the agenda, and one-time firing."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.scheduler import nl_parser
from tests.test_e2e import Api, register

NOW = datetime(2026, 11, 19, 10, 30, tzinfo=timezone.utc)  # a Thursday


@pytest.fixture(scope="module")
def env(client):
    token, org_id, _ = register(client, "sam.scheduler@example.com", "Sam", "Sam Co")
    api = Api(client, token, org_id)
    project = api.get("/api/projects").json()[0]
    writer = api.post("/api/agents", {"name": "Digest Writer", "provider": "mock", "description": "Writes digests"}).json()
    other = api.post("/api/agents", {"name": "Ops Bot", "provider": "mock"}).json()
    return {"api": api, "project": project, "writer": writer, "other": other, "client": client}


# ===================================================================== parser
@pytest.mark.parametrize(
    "text,expected_local,task",
    [
        ("remind me tomorrow at 9 to call mum", "2026-11-20 09:00", "remind me to call mum"),
        ("in 2 hours check the deploy", "2026-11-19 18:00", "check the deploy"),
        ("on 2026-12-05 at 10:00 send the invoice", "2026-12-05 10:00", "send the invoice"),
        ("Dec 5 at 10am pay rent", "2026-12-05 10:00", "pay rent"),
        ("next friday review PRs", "2026-11-20 09:00", "review PRs"),
        ("on friday at 5pm ship it", "2026-11-20 17:00", "ship it"),
        ("tonight back up the database", "2026-11-19 21:00", "back up the database"),
        ("at 9am send the summary", "2026-11-20 09:00", "send the summary"),  # 09:00 already passed today (16:00 IST)
    ],
)
def test_parse_once(text, expected_local, task):
    s = nl_parser.parse_when(text, "Asia/Kolkata", NOW)
    assert s and s.trigger_type == "once", text
    assert s.run_at.astimezone(nl_parser._zone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M") == expected_local
    assert nl_parser.strip_spans(text, s.spans) == task


@pytest.mark.parametrize("text,cron", [("on fridays at 5pm ship it", "0 17 * * 5"), ("every friday at 5pm ship it", "0 17 * * 5"), ("mon-fri at 8 standup", "0 8 * * 1-5")])
def test_recurring_words_win(text, cron):
    s = nl_parser.parse_when(text, "UTC", NOW)
    assert s and s.trigger_type == "schedule" and s.cron == cron


def test_past_dates_are_refused_not_guessed():
    assert nl_parser.parse_when("on 2025-01-01 at 10:00 do it", "UTC", NOW) is None
    assert nl_parser.is_past_phrase("on 2025-01-01 at 10:00 do it", "UTC", NOW)
    assert nl_parser.parse_when("write a poem about the sun", "UTC", NOW) is None


def test_describe_and_next_runs_once():
    at = NOW + timedelta(days=1)
    assert nl_parser.describe("once", tz="UTC", run_at=at) == "Once on Fri 20 Nov 2026 at 10:30 (UTC)"
    assert nl_parser.next_runs("once", "", 0, "UTC", now=NOW, run_at=at) == [at]
    assert nl_parser.next_runs("once", "", 0, "UTC", now=NOW, run_at=NOW - timedelta(minutes=1)) == []
    assert nl_parser.retime_cron("0 9 * * 1-5", "make it 10:30am instead") == "30 10 * * 1-5"


# ===================================================================== one-time schedules via the API
def test_once_schedule_crud_and_validation(env):
    api, pid, agent = env["api"], env["project"]["id"], env["writer"]
    base = {"project_id": pid, "name": "One-off", "target_type": "agent", "target_id": agent["id"], "trigger_type": "once", "input": {"task": "ping"}}
    assert api.post("/api/schedules", base).status_code == 400  # no run_at
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert api.post("/api/schedules", {**base, "run_at": past}).status_code == 400
    at = datetime.now(timezone.utc) + timedelta(hours=3)
    r = api.post("/api/schedules", {**base, "run_at": at.isoformat(), "source": "chat"})
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["trigger_type"] == "once" and row["source"] == "chat"
    assert abs(datetime.fromisoformat(row["next_run_at"].replace("Z", "+00:00")) - at) < timedelta(seconds=1)
    # it shows on the agenda exactly once
    agenda = api.get(f"/api/schedules/upcoming?project_id={pid}&days=1").json()
    assert [a["automation_id"] for a in agenda].count(row["id"]) == 1
    api.delete(f"/api/schedules/{row['id']}")


def test_upcoming_expands_recurring_schedules(env):
    api, pid, agent = env["api"], env["project"]["id"], env["writer"]
    row = api.post(
        "/api/schedules",
        {"project_id": pid, "name": "Hourly check", "target_type": "agent", "target_id": agent["id"], "trigger_type": "interval", "interval_minutes": 60, "input": {"task": "check"}},
    ).json()
    agenda = [a for a in api.get(f"/api/schedules/upcoming?project_id={pid}&days=1").json() if a["automation_id"] == row["id"]]
    assert 23 <= len(agenda) <= 24
    assert agenda == sorted(agenda, key=lambda a: a["at"])
    api.patch(f"/api/schedules/{row['id']}", {"enabled": False})
    assert not [a for a in api.get(f"/api/schedules/upcoming?project_id={pid}").json() if a["automation_id"] == row["id"]]
    api.delete(f"/api/schedules/{row['id']}")


def test_once_schedule_fires_once(env):
    api, client, pid, agent = env["api"], env["client"], env["project"]["id"], env["writer"]
    row = api.post(
        "/api/schedules",
        {"project_id": pid, "name": "Fire once", "target_type": "agent", "target_id": agent["id"], "trigger_type": "once",
         "run_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), "input": {"task": "say hi"}},
    ).json()

    from app.core.db import SessionLocal
    from app.modules.scheduler.models import Automation
    from app.modules.scheduler.service import tick

    async def make_due():
        async with SessionLocal() as s:
            a = await s.get(Automation, row["id"])
            a.run_at = a.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=5)
            await s.commit()

    client.portal.call(make_due)
    assert client.portal.call(tick) >= 1
    time.sleep(1.0)
    after = api.get(f"/api/schedules/{row['id']}").json()
    assert after["next_run_at"] is None and after["run_count"] == 1
    assert client.portal.call(tick) == 0  # never again
    runs = api.get(f"/api/runs?automation_id={row['id']}").json()
    assert runs["total"] == 1
    # editing a schedule that already ran keeps working (its past time is allowed), rescheduling into the past is not
    assert api.patch(f"/api/schedules/{row['id']}", {"name": "Fired"}).status_code == 200
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    again = api.patch(f"/api/schedules/{row['id']}", {"run_at": future}).json()
    assert again["next_run_at"]


# ===================================================================== schedule by chatting (rules engine, mock model)
def chat(api, pid, messages, draft=None, tz="UTC"):
    r = api.post("/api/schedules/assistant", {"project_id": pid, "messages": [{"role": "user" if i % 2 == 0 else "assistant", "content": m} for i, m in enumerate(messages)], "draft": draft, "timezone": tz})
    assert r.status_code == 200, r.text
    return r.json()


def test_chat_one_message_complete_then_confirm(env):
    api, pid, writer = env["api"], env["project"]["id"], env["writer"]
    t1 = chat(api, pid, ["every weekday at 9am ask Digest Writer to summarize my GitHub PRs"])
    assert t1["engine"] == "rules" and t1["ready"] and not t1["missing"]
    d = t1["draft"]
    assert d["cron"] == "0 9 * * 1-5" and d["task"] == "summarize my GitHub PRs" and d["target_id"] == writer["id"]
    assert "yes" in t1["reply"].lower() and d["summary"] in t1["reply"]
    t2 = chat(api, pid, ["every weekday at 9am ask Digest Writer to summarize my GitHub PRs", t1["reply"], "yes, create it"], draft=d)
    assert t2["action"] == "create" and t2["draft"]["cron"] == "0 9 * * 1-5"
    # the draft is directly creatable
    body = {k: t2["draft"][k] for k in ("project_id", "name", "target_type", "target_id", "input", "trigger_type", "cron", "interval_minutes", "timezone")}
    created = api.post("/api/schedules", {**body, "source": "chat"})
    assert created.status_code == 201, created.text
    api.delete(f"/api/schedules/{created.json()['id']}")


def test_chat_multi_turn_asks_for_missing_pieces(env):
    api, pid = env["api"], env["project"]["id"]
    t1 = chat(api, pid, ["back up the analytics database"])
    assert not t1["ready"] and t1["missing"] == ["when"] and "when should it run" in t1["reply"].lower()
    t2 = chat(api, pid, ["back up the analytics database", t1["reply"], "whenever"], draft=t1["draft"])
    assert not t2["ready"] and t2["draft"]["task"] == "back up the analytics database"  # task kept, time not guessed
    t3 = chat(api, pid, ["back up the analytics database", t1["reply"], "whenever", t2["reply"], "tomorrow at 6pm"], draft=t2["draft"], tz="Asia/Kolkata")
    assert t3["ready"] and t3["draft"]["trigger_type"] == "once" and t3["draft"]["run_at"]
    assert t3["draft"]["task"] == "back up the analytics database"
    # switch agent and time, keep the rest
    t4 = chat(api, pid, ["...", "...", "use Ops Bot instead"], draft=t3["draft"])
    assert t4["draft"]["target_id"] == env["other"]["id"] and t4["draft"]["task"] == "back up the analytics database"
    # cancel clears
    t5 = chat(api, pid, ["cancel"], draft=t4["draft"])
    assert t5["draft"] is None and not t5["ready"]


def test_chat_retime_keeps_recurrence_and_rejects_bad_draft(env):
    api, pid = env["api"], env["project"]["id"]
    t1 = chat(api, pid, ["every monday at 8am send the weekly report"])
    t2 = chat(api, pid, ["every monday at 8am send the weekly report", t1["reply"], "make it 10:30am instead"], draft=t1["draft"])
    assert t2["draft"]["cron"] == "30 10 * * 1" and t2["draft"]["task"] == "send the weekly report"
    # a tampered draft (bogus cron, unknown agent) is re-validated server-side
    forged = {**t2["draft"], "cron": "not a cron", "target_id": "agt_nope"}
    t3 = chat(api, pid, ["..."], draft=forged)
    assert t3["draft"]["trigger_type"] == "manual" and t3["draft"]["target_id"] != "agt_nope"
    assert "yes" not in t3["reply"].lower().split()  # not offered for creation without a valid time


def test_chat_past_time_explains(env):
    api, pid = env["api"], env["project"]["id"]
    t = chat(api, pid, ["on 2020-01-01 at 10:00 send the report"])
    assert not t["ready"] and "already passed" in t["reply"]
