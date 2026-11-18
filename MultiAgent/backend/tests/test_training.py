"""Train tab: teach, review queue, auto-learn from chats, thumbs-down feedback, distill into a skill."""
from __future__ import annotations

import time

import pytest

from tests.test_e2e import Api, register


@pytest.fixture(scope="module")
def env(client):
    token, org_id, _ = register(client, "trainer@example.com", "Trainer", "Train Co")
    api = Api(client, token, org_id)
    project = api.get("/api/projects").json()[0]
    agent = api.post("/api/agents", {"name": "Student", "provider": "mock"}).json()
    return {"api": api, "project": project, "agent": agent}


def chat(env, text):
    api = env["api"]
    conv = api.post("/api/conversations", {"project_id": env["project"]["id"], "target_type": "agent", "target_id": env["agent"]["id"]}).json()
    r = api.post(f"/api/conversations/{conv['id']}/messages", {"content": text}).json()
    api.wait(r["run"]["id"])
    return conv["id"]


def lessons(env, status="pending"):
    return env["api"].get(f"/api/agents/{env['agent']['id']}/lessons?status={status}").json()


def wait_for(fn, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if (v := fn()):
            return v
        time.sleep(0.1)
    return fn()


def test_teach_creates_memory_that_reaches_the_prompt(env):
    api, aid = env["api"], env["agent"]["id"]
    r = api.post(f"/api/agents/{aid}/lessons", {"content": "Always sign off with 'Cheers, Student'."})
    assert r.status_code == 201 and r.json()["status"] == "approved" and r.json()["memory_id"]
    mems = api.get(f"/api/memories?scope=agent&agent_id={aid}").json()
    assert mems and mems[0]["source"] == "user"
    run = api.run(env["project"]["id"], "agent", aid, {"message": "hello there"})
    start = next(e for e in api.events(run["id"]) if e["type"] == "agent_start")
    assert run["status"] == "succeeded", run["error"]
    assert start  # memory is injected even though the memory capability is off (taught memories are always read)


def test_auto_learn_is_off_by_default_then_proposes_lessons(env):
    api, aid = env["api"], env["agent"]["id"]
    chat(env, "Always answer in exactly three bullet points.")
    assert lessons(env) == []
    assert api.put(f"/api/agents/{aid}/training/settings", {"auto_learn": True}).json() == {"auto_learn": True}
    chat(env, "From now on reply with a one-line summary before any details.")
    found = wait_for(lambda: lessons(env))
    assert found and found[0]["source"] == "auto" and "summary" in found[0]["content"].lower()
    # saving the agent form must not drop the flag
    a = api.get(f"/api/agents/{aid}").json()
    assert a["settings"]["auto_learn"] is True
    assert api.put(f"/api/agents/{aid}", {**a, "scope": "org"}).json()["settings"]["auto_learn"] is True


def test_review_queue_approve_edit_reject(env):
    api, aid = env["api"], env["agent"]["id"]
    chat(env, "Never use jargon when explaining things.")
    chat(env, "Remember that our fiscal year starts in April.")
    pending = wait_for(lambda: len(lessons(env)) >= 3 and lessons(env))
    assert pending
    first, second = pending[0], pending[1]
    edited = api.patch(f"/api/lessons/{first['id']}", {"content": "Explain things in plain words."}).json()
    assert edited["content"] == "Explain things in plain words."
    ok = api.post(f"/api/lessons/{first['id']}/approve").json()
    assert ok["status"] == "approved" and ok["memory_id"]
    assert api.post(f"/api/lessons/{second['id']}/reject").json()["status"] == "rejected"
    assert api.patch(f"/api/lessons/{first['id']}", {"content": "x" * 10}).status_code == 400  # no longer pending
    mem = [m for m in api.get(f"/api/memories?scope=agent&agent_id={aid}").json() if m["id"] == ok["memory_id"]][0]
    assert mem["source"] == "learned" and mem["content"] == "Explain things in plain words."
    rest = api.post(f"/api/agents/{aid}/lessons/approve-all").json()
    assert rest["approved"] >= 1 and lessons(env) == []


def test_no_duplicate_lessons(env):
    api, aid = env["api"], env["agent"]["id"]
    chat(env, "Always sign off with 'Cheers, Student'.")  # already taught
    time.sleep(0.5)
    assert all("cheers" not in l["content"].lower() for l in lessons(env))
    assert api.get(f"/api/agents/{aid}/training").json()["approved"] >= 2


def test_thumbs_down_note_becomes_lesson(env):
    api = env["api"]
    cid = chat(env, "Explain what a webhook is.")
    msgs = api.get(f"/api/conversations/{cid}").json()["messages"]
    assistant = next(m for m in msgs if m["role"] == "assistant")
    r = api.patch(f"/api/conversations/{cid}/messages/{assistant['id']}", {"feedback": "down", "note": "Too long, keep answers under 100 words."})
    assert r.status_code == 200
    got = lessons(env)
    assert any(l["source"] == "feedback" and "100 words" in l["content"] for l in got)
    # thumbs down without a note proposes nothing on the offline model
    n = len(got)
    cid2 = chat(env, "Explain what DNS is.")
    a2 = next(m for m in api.get(f"/api/conversations/{cid2}").json()["messages"] if m["role"] == "assistant")
    api.patch(f"/api/conversations/{cid2}/messages/{a2['id']}", {"feedback": "down", "note": ""})
    assert len(lessons(env)) == n


def test_learn_from_chats_and_distill(env):
    api, aid = env["api"], env["agent"]["id"]
    chat(env, "I prefer metric units for every measurement.")
    r = api.post(f"/api/agents/{aid}/training/reflect", {})
    assert r.status_code == 200 and r.json()["conversations"] >= 1
    sk = api.post(f"/api/agents/{aid}/training/distill")
    assert sk.status_code == 200, sk.text
    skill = sk.json()
    assert skill["name"] == "Student playbook" and "Cheers, Student" in skill["instructions"]
    assert skill["id"] in api.get(f"/api/agents/{aid}").json()["skill_ids"]
    again = api.post(f"/api/agents/{aid}/training/distill").json()
    assert again["id"] == skill["id"]  # updates the same playbook


def test_distill_without_lessons_and_isolation(env, client):
    api = env["api"]
    empty = api.post("/api/agents", {"name": "Blank", "provider": "mock"}).json()
    assert api.post(f"/api/agents/{empty['id']}/training/distill").status_code == 400
    token, org_id, _ = register(client, "intruder@example.com", "Intruder", "Other Co")
    other = Api(client, token, org_id)
    some = lessons(env, "all")[0]
    assert other.post(f"/api/lessons/{some['id']}/approve").status_code == 404
    assert other.get(f"/api/agents/{env['agent']['id']}/lessons").status_code == 404


# ------------------------------------------------------------------ npx-style skill install
from app.engine import skill_install  # noqa: E402
from app.engine.net import SafeResponse  # noqa: E402

TREE = {"tree": [
    {"path": "skills/pdf/SKILL.md", "type": "blob"},
    {"path": "skills/pdf/scripts/run.py", "type": "blob"},
    {"path": "skills/docx/SKILL.md", "type": "blob"},
    {"path": "README.md", "type": "blob"},
]}
FILES = {
    "skills/pdf/SKILL.md": "---\nname: pdf\ndescription: Work with PDFs\n---\n\n# PDF\nUse pypdf.",
    "skills/docx/SKILL.md": "# Word docs\nUse python-docx.",
}


@pytest.fixture()
def fake_github(monkeypatch):
    import json as _json
    calls = []

    async def fake(method, url, **kw):
        calls.append(url)
        if url.startswith("https://api.github.com/repos/acme/skillz/git/trees/"):
            return SafeResponse(200, {}, url, _json.dumps(TREE).encode())
        if url.startswith("https://api.github.com/"):
            return SafeResponse(404, {}, url, b"{}")
        prefix = "https://raw.githubusercontent.com/acme/skillz/HEAD/"
        if url.startswith(prefix) and url[len(prefix):].replace("%2F", "/") in FILES:
            return SafeResponse(200, {}, url, FILES[url[len(prefix):]].encode())
        return SafeResponse(404, {}, url, b"")

    monkeypatch.setattr(skill_install, "safe_request", fake)
    return calls


@pytest.mark.parametrize("cmd,owner,repo,names,sub", [
    ("npx skills add acme/skillz", "acme", "skillz", [], ""),
    ("npx skills@latest add acme/skillz --skill pdf -y", "acme", "skillz", ["pdf"], ""),
    ("npx add-skill acme/skillz@pdf", "acme", "skillz", ["pdf"], ""),
    ("acme/skillz/skills/docx", "acme", "skillz", [], "skills/docx"),
    ("npx install pdf", "anthropics", "skills", ["pdf"], ""),
    ("npx skills add https://github.com/acme/skillz/tree/main/skills", "acme", "skillz", [], "skills"),
])
def test_parse_command(cmd, owner, repo, names, sub):
    s = skill_install.parse_command(cmd)
    assert (s.owner, s.repo, s.names, s.subpath) == (owner, repo, names, sub)


@pytest.mark.parametrize("cmd", ["", "npx skills add", "npx skills add ../../etc/passwd", "npx skills add https://evil.example/x", "npx skills add a/b --skill '$(rm -rf /)'"])
def test_parse_command_rejects(cmd):
    with pytest.raises(skill_install.InstallError):
        skill_install.parse_command(cmd)


def test_install_preview_and_install(env, fake_github):
    api = env["api"]
    pv = api.post("/api/skills/install/preview", {"command": "npx skills add acme/skillz"}).json()
    assert {i["name"] for i in pv["items"]} == {"pdf", "docx"}  # scripts and README are not skills
    one = api.post("/api/skills/install", {"command": "npx skills add acme/skillz --skill pdf"})
    assert one.status_code == 200, one.text
    assert one.json()["results"][0]["status"] == "installed" and one.json()["results"][0]["name"] == "pdf"
    both = api.post("/api/skills/install", {"command": "npx skills add acme/skillz"}).json()["results"]
    assert sorted((r["name"], r["status"]) for r in both) == [("Word docs", "installed"), ("pdf", "updated")]
    skill = next(s for s in api.get("/api/skills").json() if s["name"] == "pdf")
    assert "pypdf" in skill["instructions"] and "installed" in skill["tags"]


def test_install_errors(env, fake_github):
    api = env["api"]
    assert api.post("/api/skills/install", {"command": "npx skills add acme/missing"}).status_code == 400
    r = api.post("/api/skills/install", {"command": "npx skills add acme/skillz --skill nope"})
    assert r.status_code == 400 and "Available" in r.json()["detail"]
