"""Skill commands, templates, conversation skills, feedback, re-run, export/import, auto-migration."""
from __future__ import annotations

import pytest

from tests.test_e2e import Api, register


@pytest.fixture(scope="module")
def env(client):
    token, org_id, _ = register(client, "dave@example.com", "Dave", "Dave Co")
    api = Api(client, token, org_id)
    project = api.get("/api/projects").json()[0]
    skills = {s["name"]: s for s in api.get("/api/skills").json()}
    agents = {a["name"]: a for a in api.get("/api/agents").json()}
    teams = {t["name"]: t for t in api.get("/api/teams").json()}
    return {"api": api, "project": project, "skills": skills, "agents": agents, "teams": teams, "client": client}


def agent_task(api, run_id):
    return next(e for e in api.events(run_id) if e["type"] == "agent_start")["data"]["task"]


def test_seeded_skill_commands(env):
    cmds = {c["command"]: c for c in env["api"].get("/api/skills/commands").json()}
    assert {"research", "write", "calc", "docs", "review", "remember"} <= set(cmds)
    assert cmds["research"]["name"] == "Web Research" and cmds["research"]["argument_hint"]


def test_slash_command_applies_skill(env):
    api, project = env["api"], env["project"]
    plain = api.post("/api/agents", {"name": "Plain", "provider": "mock"}).json()
    run = api.run(project["id"], "agent", plain["id"], {"message": "/research latest news on solid state batteries"})
    assert run["status"] == "succeeded", run["error"]
    events = api.events(run["id"])
    cmd = next(e for e in events if e["type"] == "skill_command")
    assert cmd["data"]["command"] == "research" and cmd["data"]["skill"] == "Web Research"
    start = next(e for e in events if e["type"] == "agent_start")
    assert "Web Research" in start["data"]["skills"] and "web_search" in start["data"]["tools"]
    assert start["data"]["task"] == "latest news on solid state batteries"
    assert any(e["type"] == "tool_call" and e["data"]["name"] == "web_search" for e in events)
    # unknown commands are left untouched
    run = api.run(project["id"], "agent", plain["id"], {"message": "/nope hello"})
    assert agent_task(api, run["id"]) == "/nope hello"


def test_command_template_and_validation(env):
    api, project = env["api"], env["project"]
    sk = api.post("/api/skills", {"name": "Shouter", "command": "/Shout", "argument_hint": "<text>", "command_template": "Say this loudly for {{ project.name }}: {{ args }}"})
    assert sk.status_code == 201, sk.text
    assert sk.json()["command"] == "shout"
    assert api.post("/api/skills", {"name": "Dup", "command": "shout"}).status_code == 409
    assert api.post("/api/skills", {"name": "Dup2", "command": "research"}).status_code == 409  # clashes with a global skill
    assert api.post("/api/skills", {"name": "Bad", "command": "help"}).status_code == 400
    assert api.post("/api/skills", {"name": "Bad", "command": "no spaces!"}).status_code == 400
    # updating a skill keeps its own command
    s = sk.json()
    assert api.put(f"/api/skills/{s['id']}", {**{k: s[k] for k in ("name", "description", "instructions", "tool_ids", "tags", "command", "argument_hint", "command_template")}}).status_code == 200
    dup = api.post(f"/api/skills/{s['id']}/duplicate").json()
    assert dup["command"] is None
    writer = env["agents"]["Writer"]
    run = api.run(project["id"], "agent", writer["id"], {"message": "/shout hello world"})
    assert agent_task(api, run["id"]) == f"Say this loudly for {project['name']}: hello world"
    # commands also work for teams (every member gets the skill)
    team = env["teams"]["Research → Write → Review"]
    run = api.run(project["id"], "team", team["id"], {"task": "/shout ship it"})
    starts = [e for e in api.events(run["id"]) if e["type"] == "agent_start"]
    assert all("Shouter" in e["data"]["skills"] for e in starts) and len(starts) == 3


def test_skill_templates(env):
    api = env["api"]
    templates = api.get("/api/skills/templates").json()
    assert len(templates) >= 10 and all(t["command"] for t in templates)
    s1 = api.post("/api/skills/templates/summarize").json()
    assert s1["command"] == "summarize" and s1["command_template"] and "template" in s1["tags"]
    s2 = api.post("/api/skills/templates/summarize").json()
    assert s2["command"] is None  # command already taken
    brief = api.post("/api/skills/templates/research-brief").json()
    tools = {t["id"]: t["name"] for t in api.get("/api/tools").json()}
    assert {"web_search", "browse_webpage"} <= {tools[i] for i in brief["tool_ids"]}
    assert api.post("/api/skills/templates/does-not-exist").status_code == 404


def test_conversation_skills_and_feedback(env):
    api, project = env["api"], env["project"]
    conv = api.post("/api/conversations", {"project_id": project["id"], "target_type": "agent", "target_id": env["agents"]["Writer"]["id"]}).json()
    upd = api.patch(f"/api/conversations/{conv['id']}", {"skill_ids": [env["skills"]["Data & Math Accuracy"]["id"], "skl_doesnotexist"]})
    assert upd.status_code == 200 and upd.json()["skill_ids"] == [env["skills"]["Data & Math Accuracy"]["id"]]
    r = api.post(f"/api/conversations/{conv['id']}/messages", {"content": "What is 6 * 7?"}).json()
    run = api.wait(r["run"]["id"])
    assert "= 42" in run["output"]
    data = api.get(f"/api/conversations/{conv['id']}").json()
    assistant = data["messages"][-1]
    fb = api.patch(f"/api/conversations/{conv['id']}/messages/{assistant['id']}", {"feedback": "up", "note": "great"})
    assert fb.status_code == 200 and fb.json()["meta"]["feedback"]["rating"] == "up"
    user_msg = data["messages"][0]
    assert api.patch(f"/api/conversations/{conv['id']}/messages/{user_msg['id']}", {"feedback": "up"}).status_code == 404
    cleared = api.patch(f"/api/conversations/{conv['id']}/messages/{assistant['id']}", {"feedback": None}).json()
    assert "feedback" not in cleared["meta"]


def test_rerun(env):
    api, project = env["api"], env["project"]
    run = api.run(project["id"], "agent", env["agents"]["Analyst"]["id"], {"task": "What is 3 * 3?"})
    again = api.post(f"/api/runs/{run['id']}/rerun")
    assert again.status_code == 201
    new = api.wait(again.json()["id"])
    assert new["id"] != run["id"] and new["input"] == run["input"] and new["status"] == "succeeded"


def test_export_import_between_tenants(env, client):
    api = env["api"]
    team = env["teams"]["Managed Research Team"]
    bundle = api.post("/api/library/export", {"team_ids": [team["id"]], "include_dependencies": True})
    assert bundle.status_code == 200, bundle.text
    b = bundle.json()
    assert b["format"] == "agentforge.bundle" and len(b["items"]["teams"]) == 1
    assert len(b["items"]["agents"]) == 4 and b["items"]["skills"]
    assert b["items"]["tools"] == []  # built-ins are referenced, not copied
    assert any(str(t).startswith("builtin:") for a in b["items"]["agents"] for t in a["tool_ids"])

    token, org_id, _ = register(client, "erin@example.com", "Erin", "Erin Ltd")
    erin = Api(client, token, org_id)
    res = erin.post("/api/library/import", {"bundle": b})
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["created"]["team"] == 1 and out["created"]["agent"] == 4
    imported_team = next(i for i in out["items"] if i["type"] == "team")
    t = erin.get(f"/api/teams/{imported_team['id']}").json()
    assert t["org_id"] == org_id and t["name"].endswith("(imported)")
    my_agents = {a["id"] for a in erin.get("/api/agents", params={"scope": "org"}).json()}
    assert {m["agent_id"] for m in t["members"]} <= my_agents and t["manager_agent_id"] in my_agents
    # imported skills that clash with global commands lose the command instead of failing
    imported_skills = [s for s in erin.get("/api/skills", params={"scope": "org"}).json()]
    assert imported_skills and all(s["command"] is None for s in imported_skills)
    run = erin.run(erin.get("/api/projects").json()[0]["id"], "team", t["id"], {"task": "Research wind energy"})
    assert run["status"] == "succeeded", run["error"]
    # bad bundles are rejected
    assert erin.post("/api/library/import", {"bundle": {"format": "other"}}).status_code == 400
    evil = {"format": "agentforge.bundle", "version": 1, "items": {"skills": [{"ref": "x", "name": "y" * 500}]}}
    assert erin.post("/api/library/import", {"bundle": evil}).status_code == 400


def test_auto_migration_adds_columns(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from app.db import Base, _add_missing_columns

    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE skills (id VARCHAR(32) PRIMARY KEY, org_id VARCHAR(32), name VARCHAR(120), description TEXT, instructions TEXT, tool_ids JSON, tags JSON, created_by VARCHAR(32), created_at DATETIME, updated_at DATETIME)"))
        conn.execute(text("INSERT INTO skills (id, name) VALUES ('skl_1', 'old')"))
        Base.metadata.create_all(conn)
        _add_missing_columns(conn)
        cols = {c["name"] for c in inspect(conn).get_columns("skills")}
        assert {"command", "argument_hint", "command_template"} <= cols
        row = conn.execute(text("SELECT argument_hint, command FROM skills WHERE id='skl_1'")).one()
        assert row[0] == "" and row[1] is None
