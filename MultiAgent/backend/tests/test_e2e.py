"""End-to-end tests against the real app with the offline mock model."""
from __future__ import annotations

import json
import time

import pytest

PW = "Sup3r-secret!"


def register(client, email, name="Test User", org=None):
    r = client.post("/api/auth/register", json={"email": email, "name": name, "password": PW, "org_name": org})
    assert r.status_code == 201, r.text
    data = r.json()
    return data["access_token"], data["orgs"][0]["id"], data


class Api:
    def __init__(self, client, token, org_id):
        self.c, self.h = client, {"Authorization": f"Bearer {token}", "X-Org-Id": org_id}
        self.org_id = org_id

    def get(self, url, **kw):
        return self.c.get(url, headers=self.h, **kw)

    def post(self, url, json=None, **kw):
        return self.c.post(url, headers=self.h, json=json, **kw)

    def put(self, url, json=None):
        return self.c.put(url, headers=self.h, json=json)

    def patch(self, url, json=None):
        return self.c.patch(url, headers=self.h, json=json)

    def delete(self, url):
        return self.c.delete(url, headers=self.h)

    def wait(self, run_id, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            run = self.get(f"/api/runs/{run_id}").json()
            if run["status"] not in ("queued", "running"):
                return run
            time.sleep(0.1)
        raise AssertionError(f"run {run_id} did not finish")

    def run(self, project_id, target_type, target_id, inp):
        r = self.post("/api/runs", {"project_id": project_id, "target_type": target_type, "target_id": target_id, "input": inp})
        assert r.status_code == 201, r.text
        return self.wait(r.json()["id"])

    def events(self, run_id):
        return self.get(f"/api/runs/{run_id}/events").json()


@pytest.fixture(scope="module")
def ctx(client):
    token, org_id, data = register(client, "alice@example.com", "Alice", "Acme Corp")
    assert data["user"]["is_superadmin"] is True
    api = Api(client, token, org_id)
    project = api.get("/api/projects").json()[0]
    lib = {
        "agents": {a["name"]: a for a in api.get("/api/agents").json()},
        "skills": {s["name"]: s for s in api.get("/api/skills").json()},
        "tools": {t["name"]: t for t in api.get("/api/tools").json()},
        "teams": {t["name"]: t for t in api.get("/api/teams").json()},
        "workflows": {w["name"]: w for w in api.get("/api/workflows").json()},
    }
    return {"api": api, "project": project, "lib": lib, "token": token}


def test_health_and_security_headers(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert "x-request-id" in r.headers


def test_seeded_global_library(ctx):
    lib = ctx["lib"]
    for name in ("Researcher", "Writer", "Critic", "Analyst", "Project Assistant", "Manager"):
        assert lib["agents"][name]["org_id"] is None
    assert {"web_search", "browse_webpage", "calculator", "knowledge_search", "memory"} <= set(lib["tools"])
    assert len(lib["teams"]) == 5 and len(lib["workflows"]) == 2


def test_global_items_read_only_and_duplicate(ctx):
    api = ctx["api"]
    researcher = ctx["lib"]["agents"]["Researcher"]
    body = {**{k: researcher[k] for k in ("name", "description", "provider", "model", "system_prompt", "tool_ids", "skill_ids")}}
    # superadmin may edit global, a regular member may not (checked later); duplicate works for anyone
    dup = api.post(f"/api/agents/{researcher['id']}/duplicate")
    assert dup.status_code == 201 and dup.json()["org_id"] == api.org_id
    assert body["name"] == "Researcher"


def test_agent_web_search_end_to_end(ctx):
    api, project, lib = ctx["api"], ctx["project"], ctx["lib"]
    agent = api.post(
        "/api/agents",
        {
            "name": "Web Scout",
            "provider": "mock",
            "model": "mock-smart",
            "skill_ids": [lib["skills"]["Web Research"]["id"]],
            "settings": {"browser_enabled": True},
        },
    ).json()
    run = api.run(project["id"], "agent", agent["id"], {"message": "Search the latest news about FastAPI"})
    assert run["status"] == "succeeded", run
    assert "web_search" in run["output"] and "FastAPI release notes" in run["output"]
    types = [e["type"] for e in api.events(run["id"])]
    assert types[0] == "run_start" and types[-1] == "run_end"
    assert "tool_call" in types and "tool_result" in types and "llm_response" in types
    tool_result = next(e for e in api.events(run["id"]) if e["type"] == "tool_result")
    assert "UNTRUSTED EXTERNAL CONTENT" in tool_result["data"]["output"]
    assert run["usage"]["tool_calls"] >= 1 and run["total_tokens"] > 0


def test_context_injection_org_project_skills(ctx):
    api, project, lib = ctx["api"], ctx["project"], ctx["lib"]
    assert api.patch("/api/org", {"context": "Always be polite. Company: Acme."}).status_code == 200
    api.patch(f"/api/projects/{project['id']}", {"context": "We build rockets.", "variables": {"region": "EU"}})
    writer = lib["agents"]["Writer"]
    run = api.run(project["id"], "agent", writer["id"], {"message": "Introduce yourself"})
    assert run["status"] == "succeeded"
    assert "Acme Corp" in run["output"] and project["name"] in run["output"] and "Clear Business Writing" in run["output"]


def test_knowledge_documents_agent_and_project(ctx):
    api, project = ctx["api"], ctx["project"]
    agent = api.post("/api/agents", {"name": "Policy Bot", "provider": "mock", "settings": {"knowledge_enabled": True}}).json()
    d1 = api.post("/api/documents", {"owner_type": "agent", "owner_id": agent["id"], "title": "Refund policy", "content": "Customers may request a refund within 30 days of purchase."})
    assert d1.status_code == 201
    files = {"file": ("handbook.md", b"# Handbook\n\nOffice hours are 9 to 5. Remote work is allowed on Fridays.", "text/markdown")}
    up = api.c.post("/api/documents/upload", headers=api.h, files=files, data={"owner_type": "project", "owner_id": project["id"], "pinned": "true"})
    assert up.status_code == 201, up.text
    assert up.json()["chunk_count"] >= 1
    run = api.run(project["id"], "agent", agent["id"], {"message": "According to the documents, what is the refund policy?"})
    assert run["status"] == "succeeded"
    assert "knowledge_search" in run["output"] and "30 days" in run["output"]
    assert "1 pinned document(s)" in run["output"]
    hits = api.get("/api/documents/search", params={"q": "remote work fridays", "project_id": project["id"]}).json()
    assert hits and hits[0]["title"] == "handbook.md"
    bad = api.c.post("/api/documents/upload", headers=api.h, files={"file": ("evil.exe", b"MZ...", "application/octet-stream")}, data={"owner_type": "project", "owner_id": project["id"]})
    assert bad.status_code == 400


def test_memory_tool_and_management(ctx):
    api, project = ctx["api"], ctx["project"]
    agent = api.post("/api/agents", {"name": "Memo", "provider": "mock", "settings": {"memory_enabled": True}}).json()
    run = api.run(project["id"], "agent", agent["id"], {"message": "Remember that the launch date is March 3"})
    assert run["status"] == "succeeded"
    mems = api.get("/api/memories", params={"project_id": project["id"]}).json()
    assert any("launch date is March 3" in m["content"] for m in mems)
    run2 = api.run(project["id"], "agent", agent["id"], {"message": "Hello again"})
    assert "memory item(s)" in run2["output"]  # memories injected into the prompt
    m = api.post("/api/memories", {"scope": "agent", "agent_id": agent["id"], "content": "Prefers bullet points"})
    assert m.status_code == 201
    assert api.delete(f"/api/memories/{m.json()['id']}").status_code == 204


@pytest.mark.parametrize("team_name", ["Research → Write → Review", "Expert Panel", "Managed Research Team", "Smart Router", "Writer vs Critic Debate"])
def test_team_styles(ctx, team_name):
    api, project, lib = ctx["api"], ctx["project"], ctx["lib"]
    team = lib["teams"][team_name]
    run = api.run(project["id"], "team", team["id"], {"task": "Research the latest news about solar panels and calculate 12 * 7"})
    assert run["status"] == "succeeded", run["error"]
    types = [e["type"] for e in api.events(run["id"])]
    assert "team_start" in types and "team_end" in types
    agents = {e["agent"] for e in api.events(run["id"]) if e["type"] == "agent_start"}
    if team["style"] == "supervisor":
        calls = [e["data"]["name"] for e in api.events(run["id"]) if e["type"] == "tool_call"]
        assert any(c.startswith("delegate_to_") for c in calls)
        assert len(agents) >= 3
    if team["style"] == "router":
        assert "route" in types and len(agents) == 1
    if team["style"] in ("sequential", "parallel"):
        assert len(agents) >= 3


def test_workflow_branches(ctx):
    api, project, lib = ctx["api"], ctx["project"], ctx["lib"]
    wf = lib["workflows"]["Support Ticket Triage"]
    urgent = api.run(project["id"], "workflow", wf["id"], {"ticket": "URGENT: checkout is down"})
    assert urgent["status"] == "succeeded", urgent["error"]
    ev = api.events(urgent["id"])
    assert any(e["type"] == "node_skipped" and e["node_id"] == "template_1" for e in ev)
    assert any(e["type"] == "node_end" and e["node_id"] == "agent_1" for e in ev)
    normal = api.run(project["id"], "workflow", wf["id"], {"ticket": "How do I change my avatar?"})
    assert normal["status"] == "succeeded"
    assert "logged your request" in normal["output"]
    report = api.run(project["id"], "workflow", lib["workflows"]["Web Research Report"]["id"], {"topic": "search latest EV battery news"})
    assert report["status"] == "succeeded"


def test_custom_workflow_validation_and_tool_node(ctx):
    api, project = ctx["api"], ctx["project"]
    cyclic = {"name": "bad", "graph": {"nodes": [{"id": "a", "type": "template", "data": {}}, {"id": "b", "type": "template", "data": {}}], "edges": [{"id": "1", "source": "a", "target": "b"}, {"id": "2", "source": "b", "target": "a"}]}}
    assert api.post("/api/workflows/validate", cyclic).json()["valid"] is False
    wf = api.post(
        "/api/workflows",
        {
            "name": "Calc flow",
            "graph": {
                "nodes": [
                    {"id": "input_1", "type": "input", "data": {}},
                    {"id": "tool_1", "type": "tool", "data": {"tool_key": "calculator", "args": '{"expression": "{{ input.a }} * {{ input.b }}"}'}},
                    {"id": "output_1", "type": "output", "data": {"template": "Result: {{ nodes.tool_1.output }}"}},
                ],
                "edges": [{"id": "e1", "source": "input_1", "target": "tool_1"}, {"id": "e2", "source": "tool_1", "target": "output_1"}],
            },
        },
    ).json()
    run = api.run(project["id"], "workflow", wf["id"], {"a": 6, "b": 7})
    assert run["status"] == "succeeded" and "= 42" in run["output"]
    # sandboxed templates: no access to python internals
    evil = api.post("/api/workflows", {"name": "evil", "graph": {"nodes": [{"id": "t", "type": "template", "data": {"template": "{{ ''.__class__.__mro__[1].__subclasses__() }}"}}], "edges": []}}).json()
    run = api.run(project["id"], "workflow", evil["id"], {})
    assert run["status"] == "failed" and "subclasses" not in run["output"]


def test_chat_conversation_with_history(ctx):
    api, project, lib = ctx["api"], ctx["project"], ctx["lib"]
    conv = api.post("/api/conversations", {"project_id": project["id"], "target_type": "agent", "target_id": lib["agents"]["Analyst"]["id"]}).json()
    r = api.post(f"/api/conversations/{conv['id']}/messages", {"content": "What is 15 * 4?"}).json()
    api.wait(r["run"]["id"])
    r2 = api.post(f"/api/conversations/{conv['id']}/messages", {"content": "Thanks!"}).json()
    api.wait(r2["run"]["id"])
    data = api.get(f"/api/conversations/{conv['id']}").json()
    roles = [m["role"] for m in data["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert "= 60" in data["messages"][1]["content"]
    assert data["conversation"]["title"].startswith("What is 15")


def test_sse_stream(ctx):
    api, project, lib = ctx["api"], ctx["project"], ctx["lib"]
    r = api.post("/api/runs", {"project_id": project["id"], "target_type": "agent", "target_id": lib["agents"]["Writer"]["id"], "input": {"message": "Write a haiku"}}).json()
    seen = []
    with api.c.stream("GET", f"/api/runs/{r['id']}/stream", headers=api.h) as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        for line in resp.iter_lines():
            if line.startswith("data: "):
                ev = json.loads(line[6:])
                seen.append(ev["type"])
                if ev["type"] == "run_end":
                    break
    assert seen[-1] == "run_end" and "agent_start" in seen


def test_automations_webhook_and_interval(ctx, client):
    api, project, lib = ctx["api"], ctx["project"], ctx["lib"]
    auto = api.post(
        "/api/automations",
        {"project_id": project["id"], "name": "Hook", "target_type": "agent", "target_id": lib["agents"]["Writer"]["id"], "trigger_type": "webhook", "input": {"message": "Hi"}},
    ).json()
    assert auto["webhook_url"] and "/api/hooks/whk_" in auto["webhook_url"]
    path = auto["webhook_url"].split("8000")[-1]
    hook = client.post(path, json={"message": "Summarise: webhook works"}, params={"wait": "true"})
    assert hook.status_code == 200 and hook.json()["status"] == "succeeded", hook.text
    assert client.post("/api/hooks/whk_invalid", json={}).status_code == 404
    bad_cron = api.post("/api/automations", {"project_id": project["id"], "name": "x", "target_type": "agent", "target_id": lib["agents"]["Writer"]["id"], "trigger_type": "schedule", "cron": "nope"})
    assert bad_cron.status_code == 400
    sched = api.post(
        "/api/automations",
        {"project_id": project["id"], "name": "Every 5", "target_type": "agent", "target_id": lib["agents"]["Writer"]["id"], "trigger_type": "interval", "interval_minutes": 5},
    ).json()
    assert sched["next_run_at"]
    # force it due and tick the scheduler
    import asyncio
    from datetime import datetime, timedelta, timezone

    from app.db import SessionLocal
    from app.engine.scheduler import tick
    from app.models import Automation

    async def make_due():
        async with SessionLocal() as s:
            a = await s.get(Automation, sched["id"])
            a.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await s.commit()

    client.portal.call(make_due)
    assert client.portal.call(tick) == 1
    time.sleep(1.0)
    runs = api.get("/api/runs", params={"trigger": "schedule"}).json()
    assert runs["total"] >= 1


def test_connectors_catalog_and_attach(ctx):
    api, project = ctx["api"], ctx["project"]
    cat = {c["key"] for c in api.get("/api/connectors/catalog").json()}
    assert {"github", "slack", "notion", "mcp", "rest_api", "email", "jira", "linear"} <= cat
    conn = api.post("/api/connections", {"connector_key": "rest_api", "name": "Example API", "config": {"base_url": "https://example.com/api", "auth_value": "Bearer topsecret123"}})
    assert conn.status_code == 201, conn.text
    c = conn.json()
    assert "topsecret123" not in json.dumps(c)  # secrets are never returned
    assert api.post("/api/connections", {"connector_key": "slack", "name": "x", "config": {}}).status_code == 400  # missing required token
    tools = api.get(f"/api/connections/{c['id']}/tools").json()
    assert tools[0]["tool_name"] == "rest_api_request"
    agent = api.post("/api/agents", {"name": "Integrator", "provider": "mock", "connection_ids": [c["id"]]}).json()
    assert agent["connection_ids"] == [c["id"]]
    run = api.run(project["id"], "agent", agent["id"], {"message": "hello"})
    start = next(e for e in api.events(run["id"]) if e["type"] == "agent_start")
    assert "rest_api_request" in start["data"]["tools"]
    # project-level connector + browser policy
    api.patch(f"/api/projects/{project['id']}", {"settings": {"connection_ids": [c["id"]], "web_access": False}})
    run = api.run(project["id"], "agent", ctx["lib"]["agents"]["Researcher"]["id"], {"message": "search the news"})
    start = next(e for e in api.events(run["id"]) if e["type"] == "agent_start")
    assert "rest_api_request" in start["data"]["tools"] and "web_search" not in start["data"]["tools"]
    api.patch(f"/api/projects/{project['id']}", {"settings": {"connection_ids": [], "web_access": True}})


def test_ssrf_protection(ctx):
    api, project, lib = ctx["api"], ctx["project"], ctx["lib"]
    http_tool = lib["tools"]["http_request"]
    for url in ("http://127.0.0.1:8000/api/health", "http://169.254.169.254/latest/meta-data/", "http://localhost/", "file:///etc/passwd"):
        r = api.post(f"/api/tools/{http_tool['id']}/test", {"project_id": project["id"], "arguments": {"url": url}}).json()
        assert r["ok"] is False and "Blocked" in r["output"], (url, r)
    custom = api.post("/api/tools", {"name": "meta", "kind": "http", "config": {"url": "http://169.254.169.254/{{ args.p }}"}, "parameters": {"type": "object", "properties": {"p": {"type": "string"}}}}).json()
    r = api.post(f"/api/tools/{custom['id']}/test", {"project_id": project["id"], "arguments": {"p": "x"}}).json()
    assert r["ok"] is False and "Blocked" in r["output"]
    doc = api.post("/api/documents/from-url", {"owner_type": "project", "owner_id": project["id"], "url": "http://127.0.0.1:22/"})
    assert doc.status_code == 400


def test_tenant_isolation(ctx, client):
    api = ctx["api"]
    token_b, org_b, _ = register(client, "bob@example.com", "Bob", "Bob Inc")
    bob = Api(client, token_b, org_b)
    private_agent = api.post("/api/agents", {"name": "Secret Agent", "provider": "mock"}).json()
    # Bob cannot use Alice's org
    assert client.get("/api/agents", headers={"Authorization": f"Bearer {token_b}", "X-Org-Id": api.org_id}).status_code == 403
    # Bob cannot see/run Alice's private agent from his own org
    assert bob.get(f"/api/agents/{private_agent['id']}").status_code == 404
    bob_project = bob.get("/api/projects").json()[0]
    assert bob.post("/api/runs", {"project_id": bob_project["id"], "target_type": "agent", "target_id": private_agent["id"]}).status_code == 404
    assert bob.post("/api/runs", {"project_id": ctx["project"]["id"], "target_type": "agent", "target_id": ctx["lib"]["agents"]["Writer"]["id"]}).status_code == 404
    # references to another tenant's resources are dropped
    alice_tool = api.post("/api/tools", {"name": "alice_tool", "kind": "http", "config": {"url": "https://example.com"}}).json()
    bob_agent = bob.post("/api/agents", {"name": "Bob agent", "provider": "mock", "tool_ids": [alice_tool["id"]]}).json()
    assert bob_agent["tool_ids"] == []
    # Bob can use the global library in his own org
    run = bob.run(bob_project["id"], "agent", ctx["lib"]["agents"]["Writer"]["id"], {"message": "hi"})
    assert run["status"] == "succeeded" and "Bob Inc" in run["output"]
    assert bob.get(f"/api/runs/{run['id']}").status_code == 200
    assert api.get(f"/api/runs/{run['id']}").status_code == 404
    # non-superadmin cannot modify global library
    writer = ctx["lib"]["agents"]["Writer"]
    assert bob.put(f"/api/agents/{writer['id']}", {"name": "hacked"}).status_code == 403
    assert bob.post("/api/agents", {"name": "g", "scope": "global"}).status_code == 403


def test_rbac_viewer_and_api_keys(ctx, client):
    api = ctx["api"]
    m = api.post("/api/org/members", {"email": "victor@example.com", "role": "viewer", "password": PW})
    assert m.status_code == 201, m.text
    login = client.post("/api/auth/login", json={"email": "victor@example.com", "password": PW}).json()
    viewer = Api(client, login["access_token"], api.org_id)
    assert viewer.get("/api/agents").status_code == 200
    assert viewer.post("/api/agents", {"name": "nope"}).status_code == 403
    assert viewer.get("/api/org/secrets").status_code == 403
    key = api.post("/api/org/api-keys", {"name": "ci", "role": "member"}).json()
    assert key["key"].startswith("afk_")
    r = client.get("/api/agents", headers={"Authorization": f"Bearer {key['key']}"})
    assert r.status_code == 200
    assert api.delete(f"/api/org/api-keys/{key['id']}").status_code == 204
    assert client.get("/api/agents", headers={"Authorization": f"Bearer {key['key']}"}).status_code == 401
    secret = api.post("/api/org/secrets", {"name": "MY_TOKEN", "value": "super-secret-value"})
    assert secret.status_code == 201
    assert "super-secret-value" not in json.dumps(api.get("/api/org/secrets").json())
    audit = api.get("/api/org/audit").json()
    assert any(a["action"] == "apikey.revoke" for a in audit)


def test_provider_keys_are_encrypted_and_masked(ctx):
    api = ctx["api"]
    assert api.put("/api/org/providers/openai", {"api_key": "sk-test-1234567890abcdef"}).status_code == 200
    providers = {p["key"]: p for p in api.get("/api/org/providers").json()["providers"]}
    assert providers["openai"]["configured"] and "1234567890" not in providers["openai"]["org_key"]
    assert api.delete("/api/org/providers/openai").status_code == 204


def test_brute_force_lockout(client):
    register(client, "carol@example.com", "Carol")
    codes = [client.post("/api/auth/login", json={"email": "carol@example.com", "password": "wrong-password"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] in (423, 429)
    # even the right password is refused while locked
    assert client.post("/api/auth/login", json={"email": "carol@example.com", "password": PW}).status_code in (423, 429)


def test_input_limits(ctx):
    api = ctx["api"]
    huge = "x" * (3 * 1024 * 1024)
    r = api.c.post("/api/agents", headers={**api.h, "content-type": "application/json"}, content=json.dumps({"name": "big", "system_prompt": huge}))
    assert r.status_code == 413
    assert api.post("/api/agents", {"name": ""}).status_code == 422
    assert api.post("/api/auth/register", {"email": "weak@example.com", "name": "W", "password": "password"}).status_code == 422


def test_dashboard(ctx):
    d = ctx["api"].get("/api/dashboard").json()
    assert d["counts"]["agents"] >= 6 and len(d["series"]) == 14 and d["recent_runs"]
    assert d["week"]["runs"] > 0
