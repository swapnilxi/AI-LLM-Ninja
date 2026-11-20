"""Training window: lesson kinds, Q&A examples in memory, overview/grid stats, knowledge playground search."""
from __future__ import annotations

import pytest

from tests.test_e2e import Api, register


@pytest.fixture(scope="module")
def env(client):
    token, org_id, _ = register(client, "window@example.com", "Window", "Window Co")
    api = Api(client, token, org_id)
    project = api.get("/api/projects").json()[0]
    agent = api.post("/api/agents", {"name": "Pupil", "provider": "mock"}).json()
    other = api.post("/api/agents", {"name": "Bystander", "provider": "mock"}).json()
    return {"api": api, "project": project, "agent": agent, "other": other, "org_id": org_id}


def memories(env):
    return env["api"].get(f"/api/memories?scope=agent&agent_id={env['agent']['id']}").json()


def test_default_kind_is_rule(env):
    api, aid = env["api"], env["agent"]["id"]
    r = api.post(f"/api/agents/{aid}/lessons", {"content": "Always greet by first name."})
    assert r.status_code == 201, r.text
    assert r.json()["kind"] == "rule" and r.json()["prompt"] is None
    mem = next(m for m in memories(env) if m["id"] == r.json()["memory_id"])
    assert mem["content"] == "Always greet by first name." and "kind:rule" in mem["tags"]


def test_fact_and_correction_render_into_memory(env):
    api, aid = env["api"], env["agent"]["id"]
    fact = api.post(f"/api/agents/{aid}/lessons", {"kind": "fact", "content": "Our fiscal year starts in April."}).json()
    corr = api.post(f"/api/agents/{aid}/lessons", {"kind": "correction", "prompt": "Support is open 24/7", "content": "Support is open 9am-5pm on weekdays."}).json()
    assert fact["kind"] == "fact" and corr["kind"] == "correction"
    by_id = {m["id"]: m for m in memories(env)}
    assert by_id[fact["memory_id"]]["content"] == "Fact: Our fiscal year starts in April."
    c = by_id[corr["memory_id"]]["content"]
    assert c.startswith("Correction:") and "24/7" in c and "9am-5pm" in c


def test_example_needs_question_and_renders_qa(env):
    api, aid = env["api"], env["agent"]["id"]
    bad = api.post(f"/api/agents/{aid}/lessons", {"kind": "example", "content": "Answer without question"})
    assert bad.status_code == 422
    r = api.post(f"/api/agents/{aid}/lessons", {"kind": "example", "prompt": "How do I reset my password?", "content": "Go to Settings > Account > Reset password."})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "example" and body["prompt"] == "How do I reset my password?"
    assert body["title"].startswith("How do I reset")  # default title comes from the question
    mem = next(m for m in memories(env) if m["id"] == body["memory_id"])
    assert "How do I reset my password?" in mem["content"] and "Settings > Account" in mem["content"]
    assert "kind:example" in mem["tags"]


def test_invalid_kind_rejected(env):
    r = env["api"].post(f"/api/agents/{env['agent']['id']}/lessons", {"kind": "poem", "content": "x"})
    assert r.status_code == 422


def test_example_still_runs_with_mock_model(env):
    api, aid = env["api"], env["agent"]["id"]
    run = api.run(env["project"]["id"], "agent", aid, {"message": "How do I reset my password?"})
    assert run["status"] == "succeeded", run["error"]


def test_edit_pending_lesson_kind_and_prompt(env):
    api, aid = env["api"], env["agent"]["id"]
    conv = api.post("/api/conversations", {"project_id": env["project"]["id"], "target_type": "agent", "target_id": aid}).json()
    r = api.post(f"/api/conversations/{conv['id']}/messages", {"content": "Always cite the policy number."}).json()
    api.wait(r["run"]["id"])
    out = api.post(f"/api/agents/{aid}/training/reflect", {"conversation_id": conv["id"]}).json()
    assert out["proposed"] >= 1
    pending = api.get(f"/api/agents/{aid}/lessons?status=pending").json()
    lsn = pending[0]
    assert lsn["kind"] == "rule"
    # turning it into an example without a question fails, with one succeeds
    assert api.patch(f"/api/lessons/{lsn['id']}", {"kind": "example"}).status_code == 400
    ok = api.patch(f"/api/lessons/{lsn['id']}", {"kind": "example", "prompt": "Which policy applies?", "content": "Policy 12 applies (see section 3)."})
    assert ok.status_code == 200 and ok.json()["kind"] == "example"
    approved = api.post(f"/api/lessons/{lsn['id']}/approve").json()
    assert approved["status"] == "approved"
    mem = next(m for m in memories(env) if m["id"] == approved["memory_id"])
    assert "Which policy applies?" in mem["content"]


def test_overview_includes_documents_and_kinds(env):
    api, aid = env["api"], env["agent"]["id"]
    d = api.post("/api/documents", {"owner_type": "agent", "owner_id": aid, "title": "Refunds", "content": "Refunds are processed within 14 days of the return.", "pinned": True})
    assert d.status_code == 201, d.text
    files = {"file": ("handbook.md", b"# Handbook\n\nThe office mascot is a heron named Gustav.", "text/markdown")}
    up = api.c.post("/api/documents/upload", headers=api.h, files=files, data={"owner_type": "agent", "owner_id": aid})
    assert up.status_code == 201, up.text
    o = api.get(f"/api/agents/{aid}/training").json()
    assert o["documents"] == 2 and o["chunks"] >= 2 and o["pinned_documents"] == 1 and o["document_bytes"] > 0
    assert o["approved_by_kind"]["example"] >= 1 and o["approved_by_kind"]["fact"] == 1 and o["approved_by_kind"]["correction"] == 1
    assert o["approved"] == sum(o["approved_by_kind"].values())


def test_grid_stats_one_request(env):
    api, aid, other = env["api"], env["agent"]["id"], env["other"]["id"]
    stats = api.get("/api/training/agents").json()
    s = stats[aid]
    assert s["documents"] == 2 and s["chunks"] >= 2 and s["approved"] >= 4 and s["memories"] >= 4
    assert other not in stats or stats[other]["documents"] == 0


def test_playground_search_scopes(env):
    api, aid = env["api"], env["agent"]["id"]
    api.post("/api/documents", {"owner_type": "org", "owner_id": env["org_id"], "title": "Org heron note", "content": "Every heron is a protected bird in the company pond."})
    both = api.get(f"/api/documents/search?q=heron&agent_id={aid}&top_k=5").json()
    assert {h["scope"] for h in both} == {"agent", "org"}
    mine = api.get(f"/api/documents/search?q=heron&agent_id={aid}&agent_only=true").json()
    assert mine and all(h["scope"] == "agent" for h in mine) and "Gustav" in mine[0]["text"]
    assert mine[0]["score"] > 0 and mine[0]["title"] == "handbook.md"
    assert api.get("/api/documents/search?q=heron&agent_only=true").status_code == 400
    assert api.get(f"/api/documents/search?q=heron&agent_id={aid}&top_k=0").status_code == 422


def test_other_org_cannot_see_stats(client, env):
    token, org_id, _ = register(client, "window-outsider@example.com", "Out", "Outsider Co")
    outsider = Api(client, token, org_id)
    assert env["agent"]["id"] not in outsider.get("/api/training/agents").json()
    assert outsider.get(f"/api/agents/{env['agent']['id']}/training").status_code == 404
