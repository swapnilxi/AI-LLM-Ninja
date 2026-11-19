"""Discover hub, find/use skills, project-level skills & connectors, to-dos (text to task) and the AI scheduler."""
from __future__ import annotations

import json

import pytest

from app.engine import hub, nl_schedule, schedule_ai, skill_install, skill_search
from app.engine.net import SafeResponse
from tests.test_e2e import Api, register


@pytest.fixture(scope="module")
def env(client):
    token, org_id, _ = register(client, "erin.hub@example.com", "Erin", "Erin Co")
    api = Api(client, token, org_id)
    project = api.get("/api/projects").json()[0]
    agents = {a["name"]: a for a in api.get("/api/agents").json()}
    tools = {t["name"]: t for t in api.get("/api/tools").json()}
    plain = api.post("/api/agents", {"name": "Plain agent", "provider": "mock"}).json()
    return {"api": api, "project": project, "agents": agents, "tools": tools, "plain": plain, "client": client}


def run_tools(api, env, message):
    run = api.run(env["project"]["id"], "agent", env["plain"]["id"], {"message": message})
    assert run["status"] == "succeeded", run["error"]
    ev = api.events(run["id"])
    return run, next(e for e in ev if e["type"] == "agent_start")["data"], ev


def call_tool(api, env, name, args):
    r = api.post(f"/api/tools/{env['tools'][name]['id']}/test", {"project_id": env["project"]["id"], "arguments": args})
    assert r.status_code == 200, r.text
    return r.json()


# ===================================================================== natural-language schedules
@pytest.mark.parametrize(
    "text,trigger,cron,interval,task",
    [
        ("Every weekday at 9am summarize my GitHub PRs", "schedule", "0 9 * * 1-5", 0, "summarize my GitHub PRs"),
        ("every monday and friday at 5:30pm send the weekly report", "schedule", "30 17 * * 1,5", 0, "send the weekly report"),
        ("daily at 18:00 check the error logs", "schedule", "0 18 * * *", 0, "check the error logs"),
        ("every 30 minutes poll the status page", "interval", "", 30, "poll the status page"),
        ("hourly check inventory", "interval", "", 60, "check inventory"),
        ("monthly on the 15th at 10am send invoices", "schedule", "0 10 15 * *", 0, "send invoices"),
        ("every weekend at 10 post a recap", "schedule", "0 10 * * 0,6", 0, "post a recap"),
        ("every morning brief me on the news", "schedule", "0 9 * * *", 0, "brief me on the news"),
        ("every 3 days clean up drafts", "interval", "", 4320, "clean up drafts"),
    ],
)
def test_parse_schedule(text, trigger, cron, interval, task):
    s = nl_schedule.parse_schedule(text)
    assert s and s.trigger_type == trigger and s.cron == cron and s.interval_minutes == interval
    assert nl_schedule.strip_spans(text, s.spans) == task
    assert trigger == "interval" or nl_schedule.valid_cron(s.cron)


@pytest.mark.parametrize("text", ["I sat down and wrote a summary", "write a poem about the sun", "summarize this article", "remind me tomorrow at 9", ""])
def test_parse_schedule_does_not_guess(text):
    assert nl_schedule.parse_schedule(text) is None


def test_interval_minimum_is_clamped_with_note():
    s = nl_schedule.parse_schedule("every minute ping the server")
    assert s.interval_minutes == nl_schedule.MIN_INTERVAL_MINUTES and s.notes


def test_describe_and_next_runs():
    assert nl_schedule.describe("schedule", "0 9 * * 1-5", 0, "Asia/Kolkata") == "Every weekday at 09:00 (Asia/Kolkata)"
    assert nl_schedule.describe("interval", "", 120) == "Every 2 hours"
    runs = nl_schedule.next_runs("schedule", "0 9 * * 1-5", 0, "UTC")
    assert len(runs) == 3 and all(r.weekday() < 5 and r.hour == 9 for r in runs)


def test_draft_endpoint_rules(env):
    api, project = env["api"], env["project"]
    r = api.post("/api/automations/draft", {"project_id": project["id"], "text": "every weekday at 9am summarize my GitHub PRs", "timezone": "Asia/Kolkata"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["engine"] == "rules" and d["trigger_type"] == "schedule" and d["cron"] == "0 9 * * 1-5"
    assert d["task"] == "summarize my GitHub PRs" and d["timezone"] == "Asia/Kolkata" and len(d["next_runs"]) == 3
    assert d["summary"] == "Every weekday at 09:00 (Asia/Kolkata)" and d["target_type"] == "agent" and d["input"] == {"task": d["task"]}
    # the draft is a preview only: it can be saved through the normal automation endpoint
    created = api.post("/api/automations", {k: d[k] for k in ("project_id", "name", "target_type", "target_id", "input", "trigger_type", "cron", "timezone")})
    assert created.status_code == 201, created.text
    assert created.json()["next_run_at"]
    # bad timezone falls back to UTC, no schedule => manual with guidance (never a guessed schedule)
    d2 = api.post("/api/automations/draft", {"project_id": project["id"], "text": "summarize this article", "timezone": "Mars/Base"}).json()
    assert d2["timezone"] == "UTC" and d2["trigger_type"] == "manual" and d2["notes"] and d2["next_runs"] == []


def test_draft_ai_path_validates_model_output(env, monkeypatch):
    api, project = env["api"], env["project"]

    def fake(reply):
        async def complete(session, org, system, prompt, max_tokens=900):
            return reply, "anthropic"
        return complete

    good = json.dumps({"name": "PR digest", "task": "Summarize open pull requests", "schedule": "every weekday at 9am", "cron": "0 9 * * 1-5"})
    monkeypatch.setattr(schedule_ai, "complete", fake("Here you go:\n```json\n" + good + "\n```"))
    d = api.post("/api/automations/draft", {"project_id": project["id"], "text": "pr digest please"}).json()
    assert d["engine"] == "ai" and d["name"] == "PR digest" and d["cron"] == "0 9 * * 1-5"

    # a model-invented cron is only trusted when it parses; garbage never reaches the scheduler
    bad = json.dumps({"name": "X", "task": "Do X", "schedule": "when the stars align", "cron": "99 99 * * *"})
    monkeypatch.setattr(schedule_ai, "complete", fake(bad))
    d = api.post("/api/automations/draft", {"project_id": project["id"], "text": "do X when the stars align"}).json()
    assert d["trigger_type"] == "manual" and d["cron"] == ""
    unusual = json.dumps({"name": "X", "task": "Do X", "schedule": "twice a month", "cron": "0 8 1,15 * *"})
    monkeypatch.setattr(schedule_ai, "complete", fake(unusual))
    d = api.post("/api/automations/draft", {"project_id": project["id"], "text": "do X twice a month"}).json()
    assert d["trigger_type"] == "schedule" and d["cron"] == "0 8 1,15 * *"
    # unparseable reply => rules fallback still works
    monkeypatch.setattr(schedule_ai, "complete", fake("sorry, no JSON"))
    d = api.post("/api/automations/draft", {"project_id": project["id"], "text": "daily at 7:15 send standup notes"}).json()
    assert d["engine"] == "rules" and d["cron"] == "15 7 * * *"


# ===================================================================== to-dos
CHAT_TEXT = """Here is the plan for the launch:

## Next steps
- Draft the announcement email by friday
- [ ] Update the pricing page (urgent)
- [x] Book the venue
1. Ask legal to review the terms
2. Nice to have: translate the blog post

The launch looks promising overall."""


def test_task_crud_and_isolation(env, client):
    api, project = env["api"], env["project"]
    t = api.post("/api/tasks", {"project_id": project["id"], "title": "Write release notes", "priority": "high"})
    assert t.status_code == 201, t.text
    t = t.json()
    assert t["status"] == "todo" and t["source"] == "manual"
    done = api.patch(f"/api/tasks/{t['id']}", {"status": "done"}).json()
    assert done["status"] == "done" and done["completed_at"]
    reopened = api.patch(f"/api/tasks/{t['id']}", {"status": "todo", "due_at": "2030-01-02T10:00:00Z"}).json()
    assert reopened["completed_at"] is None and reopened["due_at"].startswith("2030-01-02")
    assert api.patch(f"/api/tasks/{t['id']}", {"due_at": None}).json()["due_at"] is None  # null clears the date
    assert {x["id"] for x in api.get(f"/api/tasks?project_id={project['id']}&status=open").json()} >= {t["id"]}
    assert api.post("/api/tasks", {"project_id": project["id"], "title": ""}).status_code == 422
    # another organization can neither see nor change it
    token, org_id, _ = register(client, "mallory.hub@example.com", "Mallory", "Evil Co")
    other = Api(client, token, org_id)
    assert other.get(f"/api/tasks/{t['id']}").status_code == 404
    assert other.patch(f"/api/tasks/{t['id']}", {"status": "done"}).status_code == 404
    assert other.post("/api/tasks", {"project_id": project["id"], "title": "x"}).status_code == 404
    assert other.delete(f"/api/tasks/{t['id']}").status_code == 404
    assert api.delete(f"/api/tasks/{t['id']}").status_code == 204


def test_text_to_task_preview_and_save(env):
    api, project = env["api"], env["project"]
    pv = api.post("/api/tasks/extract", {"project_id": project["id"], "text": CHAT_TEXT, "context": "Launch is on 1 March."}).json()
    assert pv["engine"] == "rules"
    titles = [i["title"] for i in pv["items"]]
    assert titles == ["Draft the announcement email by friday", "Update the pricing page (urgent)", "Ask legal to review the terms", "Nice to have: translate the blog post"]
    assert "Book the venue" not in " ".join(titles)  # ticked items are already done
    prio = {i["title"]: i["priority"] for i in pv["items"]}
    assert prio["Update the pricing page (urgent)"] == "high" and prio["Nice to have: translate the blog post"] == "low"
    assert pv["items"][0]["due_at"]  # "by friday"
    assert "Launch is on 1 March." in pv["context"] and "Next steps" in pv["context"]
    assert not api.get(f"/api/tasks?project_id={project['id']}&status=open").json() or all(t["title"] not in titles for t in api.get(f"/api/tasks?project_id={project['id']}").json())

    saved = api.post("/api/tasks/bulk", {"project_id": project["id"], "items": [{"title": i["title"], "notes": i["notes"], "priority": i["priority"], "due_at": i["due_at"]} for i in pv["items"][:2]], "context": pv["context"]})
    assert saved.status_code == 201, saved.text
    made = saved.json()["created"]
    assert len(made) == 2 and made[0]["context"].startswith("Launch is on 1 March.") and made[0]["source"] == "text"
    # saving the same items again skips near-duplicates
    again = api.post("/api/tasks/bulk", {"project_id": project["id"], "items": [{"title": "Draft the announcement email by Friday"}]}).json()
    assert again["created"] == [] and len(again["skipped"]) == 1
    # save=true creates straight away
    direct = api.post("/api/tasks/extract", {"project_id": project["id"], "text": "- Email the vendor about the invoice", "save": True}).json()
    assert len(direct["created"]) == 1 and direct["created"][0]["title"] == "Email the vendor about the invoice"
    assert api.post("/api/tasks/extract", {"project_id": project["id"], "text": "   "}).status_code == 400


def test_chat_reply_to_tasks_and_run_with_context(env):
    api, project, agent = env["api"], env["project"], env["plain"]
    conv = api.post("/api/conversations", {"project_id": project["id"], "target_type": "agent", "target_id": agent["id"]}).json()
    sent = api.post(f"/api/conversations/{conv['id']}/messages", {"content": "Plan our launch"}).json()
    api.wait(sent["run"]["id"])
    msgs = api.get(f"/api/conversations/{conv['id']}").json()["messages"]
    reply = next(m for m in msgs if m["role"] == "assistant")
    # convert this chat reply: the message text is used when no text is given
    r = api.post("/api/tasks/extract", {"project_id": project["id"], "conversation_id": conv["id"], "message_id": reply["id"], "context": "Owner: Erin", "save": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Owner: Erin" in body["context"] and "From a chat reply" in body["context"]
    # a message from someone else's conversation is refused
    assert api.post("/api/tasks/extract", {"project_id": project["id"], "conversation_id": "cnv_nope", "message_id": reply["id"]}).status_code == 404

    t = api.post("/api/tasks", {"project_id": project["id"], "title": "Prepare launch checklist", "notes": "Cover email, pricing, legal", "context": "Launch is on 1 March. Audience: EU retailers."}).json()
    started = api.post(f"/api/tasks/{t['id']}/run", {"agent_id": agent["id"]})
    assert started.status_code == 200, started.text
    run = api.wait(started.json()["run_id"])
    assert run["status"] == "succeeded"
    task_text = next(e for e in api.events(run["id"]) if e["type"] == "agent_start")["data"]["task"]
    assert "Prepare launch checklist" in task_text and "Cover email, pricing, legal" in task_text
    assert "Context provided with this task" in task_text and "Audience: EU retailers." in task_text  # the context giver
    after = api.get(f"/api/tasks/{t['id']}").json()
    assert after["status"] == "doing" and after["run_id"] == run["id"]
    assert api.post(f"/api/tasks/{t['id']}/run", {"agent_id": "agt_missing"}).status_code == 404


# ===================================================================== agent tools at project level
def test_task_tools_are_project_level_and_default_on(env):
    api = env["api"]
    _, start, _ = run_tools(api, env, "hello there")
    tools = set(start["tools"])
    assert {"create_tasks", "list_tasks", "update_task", "find_skills", "use_skill"} <= tools
    assert "schedule_task" not in tools  # scheduling creates automations, so it is opt-in
    pid = env["project"]["id"]
    assert api.patch(f"/api/projects/{pid}", {"settings": {"tasks_enabled": False, "skill_discovery_enabled": False, "scheduling_enabled": True}}).status_code == 200
    _, start, _ = run_tools(api, env, "hello again")
    tools = set(start["tools"])
    assert "schedule_task" in tools and not ({"create_tasks", "list_tasks", "update_task", "find_skills", "use_skill"} & tools)
    api.patch(f"/api/projects/{pid}", {"settings": {"tasks_enabled": True, "skill_discovery_enabled": True, "scheduling_enabled": False}})


def test_agent_creates_lists_updates_tasks(env):
    api = env["api"]
    out = call_tool(api, env, "create_tasks", {"tasks": [{"title": "Send the Q3 report to finance", "priority": "high", "due": "2030-05-01", "context": "Finance closes books on the 3rd."}, {"title": "Book a venue"}], "context": "From the planning chat"})
    assert out["ok"] and "Created 2 task(s)" in out["output"]
    listed = call_tool(api, env, "list_tasks", {"status": "open"})["output"]
    assert "Send the Q3 report to finance" in listed and "high" in listed and "due 2030-05-01" in listed
    task_id = listed.split("(")[1].split(")")[0]
    done = call_tool(api, env, "update_task", {"task_id": task_id, "status": "done"})
    assert done["ok"] and "done" in done["output"]
    stored = {t["title"]: t for t in api.get("/api/tasks").json()}
    assert stored["Send the Q3 report to finance"]["context"].startswith("From the planning chat") and stored["Send the Q3 report to finance"]["source"] == "agent"
    assert not call_tool(api, env, "update_task", {"task_id": "tsk_nope", "status": "done"})["ok"]
    assert not call_tool(api, env, "create_tasks", {"tasks": []})["ok"]


def test_agent_can_schedule_from_chat_when_enabled(env):
    api, pid = env["api"], env["project"]["id"]
    api.patch(f"/api/projects/{pid}", {"settings": {"scheduling_enabled": True}})
    run, start, ev = run_tools(api, env, "schedule_task every weekday at 9am send the standup summary")
    assert "schedule_task" in start["tools"]
    result = next(e for e in ev if e["type"] == "tool_result" and e["data"]["name"] == "schedule_task")["data"]
    assert not result["is_error"], result["output"]
    assert "Every weekday at 09:00" in result["output"] and "Automations page" in result["output"]
    autos = [a for a in api.get(f"/api/automations?project_id={pid}").json() if a["description"].startswith("Scheduled by an agent")]
    assert autos and autos[0]["cron"] == "0 9 * * 1-5" and autos[0]["target_id"] == env["plain"]["id"] and autos[0]["next_run_at"]
    # unparseable or one-off schedules are refused with guidance, not guessed
    run, _, ev = run_tools(api, env, "schedule_task remind me tomorrow at 9 to call mum")
    bad = next(e for e in ev if e["type"] == "tool_result" and e["data"]["name"] == "schedule_task")["data"]
    assert bad["is_error"] and "could not understand" in bad["output"]
    api.patch(f"/api/projects/{pid}", {"settings": {"scheduling_enabled": False}})


# ===================================================================== skills: find, use, project level
GH = {
    "anthropics/skills": {"skills/frontend-design/SKILL.md": "---\nname: frontend-design\ndescription: >\n  Distinctive UI design.\n  Avoid templated defaults.\n---\n# Frontend design\nPick a bold aesthetic."},
    "vercel-labs/agent-skills": {
        "skills/react-best-practices/SKILL.md": "---\nname: react-best-practices\ndescription: React performance rules\n---\n# React\nAvoid waterfalls.",
        "skills/web-design-guidelines/SKILL.md": "---\nname: web-design-guidelines\ndescription: Review UI against guidelines\n---\n# Web design\nCheck focus states.",
        "skills/composition-patterns/SKILL.md": "---\nname: composition-patterns\ndescription: Component composition\n---\n# Composition\nPrefer composition.",
    },
    "acme/skillz": {"skills/pdf/SKILL.md": "---\nname: pdf\ndescription: Work with PDFs\n---\nUse pypdf.", "skills/docx/SKILL.md": "# Word\nUse python-docx."},
}
REGISTRY = {"skills": [
    {"id": "vercel-labs/agent-skills/react-best-practices", "source": "vercel-labs/agent-skills", "skillId": "react-best-practices", "name": "react-best-practices", "installs": 250000},
    {"id": "vercel-labs/agent-skills/vercel-react-best-practices", "source": "vercel-labs/agent-skills", "skillId": "vercel-react-best-practices", "name": "vercel-react-best-practices", "installs": 900000},
    {"id": "evil/../x", "source": "evil/../x", "skillId": "y", "name": "y", "installs": 9},  # malformed sources are never surfaced
]}


@pytest.fixture()
def fake_net(monkeypatch):
    async def fake(method, url, **kw):
        if url.startswith("https://skills.sh/api/search"):
            return SafeResponse(200, {}, url, json.dumps(REGISTRY).encode())
        if url.startswith("https://api.github.com/repos/"):
            repo = "/".join(url.split("/")[4:6])
            files = GH.get(repo)
            if not files:
                return SafeResponse(404, {}, url, b"{}")
            return SafeResponse(200, {}, url, json.dumps({"tree": [{"path": p, "type": "blob"} for p in files]}).encode())
        if url.startswith("https://raw.githubusercontent.com/"):
            parts = url.split("/")
            repo, path = "/".join(parts[3:5]), "/".join(parts[6:]).replace("%2F", "/")
            if path in GH.get(repo, {}):
                return SafeResponse(200, {}, url, GH[repo][path].encode())
        return SafeResponse(404, {}, url, b"")

    calls: list[tuple[str, dict]] = []
    inner = fake

    async def recording(method, url, **kw):
        calls.append((url, kw.get("headers") or {}))
        return await inner(method, url, **kw)

    skill_search._search_cache.clear()
    skill_search._path_cache.clear()
    monkeypatch.setattr(skill_install, "safe_request", recording)
    monkeypatch.setattr(skill_search, "safe_request", recording)
    return calls


def test_front_matter_block_scalars():
    name, desc, body = skill_install.parse_skill_md(GH["anthropics/skills"]["skills/frontend-design/SKILL.md"])
    assert (name, desc) == ("frontend-design", "Distinctive UI design. Avoid templated defaults.") and body.startswith("# Frontend design")


def test_seeded_find_skills_playbook(env):
    sk = next(s for s in env["api"].get("/api/skills").json() if s["name"] == "Find Skills")
    assert sk["command"] == "find-skills" and {env["tools"]["find_skills"]["id"], env["tools"]["use_skill"]["id"]} == set(sk["tool_ids"])
    assert "use_skill" in sk["instructions"]


def test_find_skills_searches_installed_catalog_and_registry(env, fake_net):
    out = call_tool(env["api"], env, "find_skills", {"query": "react performance"})
    assert out["ok"], out
    text = out["output"]
    assert "skills.sh registry" in text and "vercel-labs/agent-skills@react-best-practices" in text and "250K installs" in text
    assert "evil" not in text
    assert "Curated catalog" in text and "Web Design & React (Vercel)" in text
    inst = call_tool(env["api"], env, "find_skills", {"query": "research web"})["output"]
    assert "Already installed" in inst and "Web Research" in inst
    assert not call_tool(env["api"], env, "find_skills", {"query": "x"})["ok"]


def test_use_skill_installed_and_external(env, fake_net):
    api = env["api"]
    inst = call_tool(api, env, "use_skill", {"skill": "Web Research"})
    assert inst["ok"] and "# Skill: Web Research" in inst["output"] and "THIRD-PARTY" not in inst["output"]
    ext = call_tool(api, env, "use_skill", {"skill": "vercel-labs/agent-skills@react-best-practices"})
    assert ext["ok"] and "Avoid waterfalls." in ext["output"] and "THIRD-PARTY SKILL" in ext["output"]  # clearly marked as third-party text
    assert call_tool(api, env, "use_skill", {"skill": "vercel-labs/agent-skills/react-best-practices"})["ok"]  # registry id form
    assert not call_tool(api, env, "use_skill", {"skill": "vercel-labs/agent-skills@nope"})["ok"]
    assert not call_tool(api, env, "use_skill", {"skill": "no such installed skill"})["ok"]
    assert not call_tool(api, env, "use_skill", {"skill": "../../etc@passwd"})["ok"]
    # nothing was installed by using a skill
    assert not any(s["name"] == "react-best-practices" for s in api.get("/api/skills").json())


def test_use_skill_respects_project_network_policy(env, fake_net):
    api, pid = env["api"], env["project"]["id"]
    api.patch(f"/api/projects/{pid}", {"settings": {"web_access": False}})
    off = call_tool(api, env, "use_skill", {"skill": "vercel-labs/agent-skills@react-best-practices"})
    assert not off["ok"] and "Web access is disabled" in off["output"]
    assert "not searched" in call_tool(api, env, "find_skills", {"query": "react performance"})["output"]
    api.patch(f"/api/projects/{pid}", {"settings": {"web_access": True}})


def test_hub_catalog_shape(env):
    d = env["api"].get(f"/api/hub?project_id={env['project']['id']}").json()
    assert {p["id"] for p in d["skills"]} >= {"find-skills", "anthropic-frontend-design", "vercel-web-design", "diagram-design", "karpathy-guidelines", "cloudflare-zero-trust", "cyber-defense", "browser-use-guide", "agentmemory", "openviking"}
    assert {m["id"] for m in d["mcp"]} >= {"browser-use-cloud", "github-mcp", "context7", "deepwiki"}
    assert any(k["id"] == "awesome-harness-engineering" for k in d["knowledge"])
    cyber = next(p for p in d["skills"] if p["id"] == "cyber-defense")
    assert cyber["trust"] == "community" and "not published by Anthropic" in cyber["caveat"]
    assert all("command" in p for p in d["skills"] if p["id"] != "find-skills") and all(m["url"].startswith("https://") for m in d["mcp"])


def test_install_pack_at_project_level_and_agents_use_it(env, fake_net):
    api, pid = env["api"], env["project"]["id"]
    r = api.post("/api/hub/skills/install", {"pack_id": "anthropic-frontend-design", "project_id": pid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attached"] and body["results"][0]["name"] == "frontend-design" and body["results"][0]["status"] == "installed"
    sid = body["results"][0]["id"]
    assert sid in api.get(f"/api/projects/{pid}").json()["settings"]["skill_ids"]
    skill = next(s for s in api.get("/api/skills").json() if s["id"] == sid)
    assert skill["description"] == "Distinctive UI design. Avoid templated defaults." and "pack:anthropic-frontend-design" in skill["tags"]
    # an agent with NO skills of its own now gets the project's skill
    run, start, _ = run_tools(api, env, "Design a landing page")
    assert "frontend-design" in start["skills"] and "frontend-design" in run["output"]
    d = api.get(f"/api/hub?project_id={pid}").json()
    pack = next(p for p in d["skills"] if p["id"] == "anthropic-frontend-design")
    assert pack["installed"] and pack["attached"] and pack["skill_ids"] == [sid] and pack["instruction_chars"] > 0
    # reinstalling updates instead of duplicating
    again = api.post("/api/hub/skills/install", {"pack_id": "anthropic-frontend-design"}).json()
    assert again["results"][0]["status"] == "updated" and again["attached"] is False and again["project_id"] is None
    assert api.post("/api/hub/skills/install", {"pack_id": "nope"}).status_code == 404
    assert api.post("/api/hub/skills/install", {}).status_code == 400
    # detach: the agent no longer gets it
    api.patch(f"/api/projects/{pid}", {"settings": {"skill_ids": []}})
    _, start, _ = run_tools(api, env, "Design a landing page")
    assert "frontend-design" not in start["skills"]


def test_install_find_skills_playbook_to_project(env):
    api, pid = env["api"], env["project"]["id"]
    r = api.post("/api/hub/skills/install", {"pack_id": "find-skills", "project_id": pid}).json()
    assert r["attached"] and r["results"][0]["name"] == "Find Skills"
    _, start, _ = run_tools(api, env, "hello")
    assert "Find Skills" in start["skills"] and {"find_skills", "use_skill"} <= set(start["tools"])
    api.patch(f"/api/projects/{pid}", {"settings": {"skill_ids": []}})


def test_install_registry_skill_and_search(env, fake_net):
    api, pid = env["api"], env["project"]["id"]
    s = api.get("/api/hub/skills/search?q=react").json()
    assert s["error"] is None and [r["ref"] for r in s["results"]] == ["vercel-labs/agent-skills@react-best-practices", "vercel-labs/agent-skills@vercel-react-best-practices"]
    r = api.post("/api/hub/skills/install", {"source": "vercel-labs/agent-skills", "skill": "react-best-practices", "project_id": pid})
    assert r.status_code == 200 and r.json()["results"][0]["name"] == "react-best-practices"
    flags = {x["ref"]: x["installed"] for x in api.get("/api/hub/skills/search?q=react").json()["results"]}
    assert flags == {"vercel-labs/agent-skills@react-best-practices": True, "vercel-labs/agent-skills@vercel-react-best-practices": False}  # per skill, not per repo
    assert api.post("/api/hub/skills/install", {"source": "../x", "skill": "y"}).status_code == 400
    assert api.post("/api/hub/skills/install", {"source": "vercel-labs/agent-skills", "skill": "nope"}).status_code == 400
    api.patch(f"/api/projects/{pid}", {"settings": {"skill_ids": []}})


def test_cross_tenant_skill_ids_are_dropped_from_projects(env, client):
    token, org_id, _ = register(client, "trent.hub@example.com", "Trent", "Trent Co")
    other = Api(client, token, org_id)
    foreign = other.post("/api/skills", {"name": "Secret playbook", "instructions": "top secret"}).json()
    r = env["api"].patch(f"/api/projects/{env['project']['id']}", {"settings": {"skill_ids": [foreign["id"]]}})
    assert r.status_code == 200 and r.json()["settings"]["skill_ids"] == []


def test_large_project_skill_sets_are_loaded_on_demand(env):
    api, pid = env["api"], env["project"]["id"]
    ids = [api.post("/api/skills", {"name": f"Big skill {i}", "instructions": "x" * 8000}).json()["id"] for i in range(5)]
    api.patch(f"/api/projects/{pid}", {"settings": {"skill_ids": ids}})
    run, start, _ = run_tools(api, env, "hello")
    assert len(start["skills"]) == 5
    loaded = [n for n in start["skills"] if f"### Skill: {n}" in run["output"] or f"{n}" in run["output"]]
    # the mock answer lists skills found as full sections: the budget (30k chars) fits 3 of 5, the rest are listed only
    assert "Big skill 0" in run["output"] and "Big skill 4" not in run["output"] and 0 < len(loaded)
    api.patch(f"/api/projects/{pid}", {"settings": {"skill_ids": []}})


# ===================================================================== MCP + knowledge install (project level)
@pytest.fixture()
def fake_mcp(monkeypatch):
    from app.engine.connectors.mcp_connector import MCP

    seen = []

    async def tester(cfg):
        seen.append(cfg)
        return True, "Connected - 3 tool(s): a, b, c"

    monkeypatch.setattr(MCP, "tester", tester)
    return seen


def test_install_mcp_server_and_attach_to_project(env, fake_mcp):
    api, pid = env["api"], env["project"]["id"]
    assert api.post("/api/hub/mcp/install", {"server_id": "github-mcp"}).status_code == 400  # needs a token
    assert api.post("/api/hub/mcp/install", {"server_id": "nope"}).status_code == 404
    r = api.post("/api/hub/mcp/install", {"server_id": "github-mcp", "token": "ghp_secret_123", "project_id": pid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["test"]["ok"] and body["attached"] and body["connection"]["status"] == "ok"
    assert "ghp_secret_123" not in json.dumps(body)  # tokens are never returned
    assert body["connection"]["config"]["url"] == "https://api.githubcopilot.com/mcp/"
    assert fake_mcp[-1]["auth_token"] == "ghp_secret_123"
    cid = body["connection"]["id"]
    assert cid in api.get(f"/api/projects/{pid}").json()["settings"]["connection_ids"]
    # no-auth servers install without a token; reinstalling reuses the connection
    d1 = api.post("/api/hub/mcp/install", {"server_id": "deepwiki"}).json()
    d2 = api.post("/api/hub/mcp/install", {"server_id": "deepwiki"}).json()
    assert d1["connection"]["id"] == d2["connection"]["id"]
    hubd = api.get(f"/api/hub?project_id={pid}").json()
    gh = next(m for m in hubd["mcp"] if m["id"] == "github-mcp")
    assert gh["connection_id"] == cid and gh["attached"] is True and gh["status"] == "ok"
    assert next(m for m in hubd["mcp"] if m["id"] == "deepwiki")["attached"] is False


def test_install_mcp_requires_admin(env, client, fake_mcp):
    api = env["api"]
    token, _, _ = register(client, "viv.hub@example.com", "Viv", "Viv Co")
    # a member of another org cannot use this org's id
    other = Api(client, token, env["api"].org_id)
    assert other.post("/api/hub/mcp/install", {"server_id": "deepwiki"}).status_code in (401, 403, 404)
    assert api.post("/api/hub/mcp/install", {"server_id": "deepwiki"}).status_code == 200


def test_install_failed_test_still_saves_connection_with_error_status(env, monkeypatch):
    from app.engine.connectors.mcp_connector import MCP

    async def tester(cfg):
        return False, "MCP connection failed: 401"

    monkeypatch.setattr(MCP, "tester", tester)
    r = env["api"].post("/api/hub/mcp/install", {"server_id": "stripe", "token": "sk_bad"}).json()
    assert r["test"]["ok"] is False and r["connection"]["status"] == "error" and "sk_bad" not in json.dumps(r)


def test_install_knowledge_doc(env, monkeypatch):
    from app.api import knowledge as knowledge_api

    async def fake(method, url, **kw):
        return SafeResponse(200, {"content-type": "text/plain"}, url, b"# Awesome Harness Engineering\n\n- Tool A: evals\n- Tool B: sandboxes\n")

    monkeypatch.setattr(knowledge_api, "safe_request", fake)
    api, pid = env["api"], env["project"]["id"]
    r = api.post("/api/hub/knowledge/install", {"item_id": "awesome-harness-engineering", "project_id": pid})
    assert r.status_code == 201, r.text
    assert api.post("/api/hub/knowledge/install", {"item_id": "awesome-harness-engineering", "project_id": pid}).status_code == 409
    docs = api.get(f"/api/documents?owner_type=project&owner_id={pid}").json()
    assert any(d["title"].startswith("Awesome Harness Engineering") for d in docs)
    assert next(k for k in api.get(f"/api/hub?project_id={pid}").json()["knowledge"] if k["id"] == "awesome-harness-engineering")["installed"] is True
    assert api.post("/api/hub/knowledge/install", {"item_id": "nope", "project_id": pid}).status_code == 404


def test_catalog_entries_are_well_formed():
    for p in hub.SKILL_PACKS:
        assert p["trust"] in ("official", "community", "built-in") and p["repo_url"].startswith("https://github.com/")
        if "command" in p:
            src = skill_install.parse_command(p["command"])  # every shipped command must parse
            assert src.label in p["repo_url"]
    assert len({p["id"] for p in hub.SKILL_PACKS}) == len(hub.SKILL_PACKS)
    for m in hub.MCP_SERVERS:
        assert m["auth"] in ("none", "optional", "bearer") and (m["auth"] == "none" or m.get("token_label"))


# ===================================================================== regressions found by checking against the live services
def test_pack_install_uses_known_paths_without_the_rate_limited_github_api(env, fake_net):
    r = env["api"].post("/api/hub/skills/install", {"pack_id": "vercel-web-design"})
    assert r.status_code == 200, r.text
    assert sorted(x["name"] for x in r.json()["results"]) == ["composition-patterns", "react-best-practices", "web-design-guidelines"]
    assert not any(url.startswith("https://api.github.com/") for url, _ in fake_net)  # raw downloads only


def test_registry_skill_id_may_differ_from_folder_name(env, fake_net):
    api = env["api"]
    # the registry's id is "vercel-react-best-practices" but the folder is "react-best-practices"
    out = call_tool(api, env, "use_skill", {"skill": "vercel-labs/agent-skills@vercel-react-best-practices"})
    assert out["ok"] and "Avoid waterfalls." in out["output"]
    r = api.post("/api/hub/skills/install", {"source": "vercel-labs/agent-skills", "skill": "vercel-react-best-practices"})
    assert r.status_code == 200, r.text
    assert r.json()["results"][0]["path"] == "skills/react-best-practices/SKILL.md"


def test_fuzzy_matching_refuses_ambiguity():
    found = [{"name": "frontend-design", "path": "a"}, {"name": "web-design", "path": "b"}, {"name": "react", "path": "c"}]
    assert skill_install.fuzzy_candidates("vercel-react", found) == [found[2]]
    assert len(skill_install.fuzzy_candidates("design", found)) == 2  # ambiguous: callers must not guess


@pytest.mark.parametrize("path", ["../other/SKILL.md", "/etc/SKILL.md", "skills/x/README.md", "a/../../b/SKILL.md"])
def test_direct_paths_are_validated(path):
    with pytest.raises(skill_install.InstallError):
        skill_install.items_from_paths(skill_install.parse_command("npx skills add acme/skillz"), [path])


def test_github_token_is_only_sent_to_the_api_host(env, fake_net, monkeypatch):
    monkeypatch.setattr(skill_install.settings, "github_token", "ghp_server_token")
    r = env["api"].post("/api/skills/install", {"command": "npx skills add acme/skillz --skill pdf"})
    assert r.status_code == 200, r.text
    api_calls = [h for url, h in fake_net if url.startswith("https://api.github.com/")]
    raw_calls = [h for url, h in fake_net if url.startswith("https://raw.githubusercontent.com/")]
    assert api_calls and all(h.get("authorization") == "Bearer ghp_server_token" for h in api_calls)
    assert raw_calls and all("authorization" not in h for h in raw_calls)
