"""Agent management API + the multi-agent answering pipeline (offline: hash embedder, stubbed LLM)."""
import json

from conftest import FakeLLM, write


def _setup(client):
    write(client.data / "acme" / "policy.md", "Refunds are issued within 14 days of purchase.")
    write(client.data / "globex" / "policy.md", "Globex refunds take 30 days.")
    client.sync()


def _events(client, pid, msg="how long do refunds take?"):
    r = client.post("/api/chat", json={"profile_id": pid, "message": msg, "multi_agent": True})
    assert r.status_code == 200
    return [json.loads(l[5:]) for l in r.text.split("\n\n") if l.startswith("data:")]


def test_default_team_and_filter(client):
    _setup(client)
    body = client.get("/api/agents").json()
    assert {b["id"] for b in body["businesses"]} >= {"acme", "globex"}
    assert {a["role"] for a in body["agents"]} == {"planner", "researcher", "critic", "synthesizer"}
    acme = client.get("/api/agents?profile_id=acme").json()["agents"]
    assert acme and all(a["profile_id"] == "acme" for a in acme)
    assert client.get("/api/agents?profile_id=nope").status_code == 404


def test_crud_and_validation(client):
    _setup(client)
    a = client.post("/api/agents", json={"profile_id": "acme", "name": "Legal", "role": "researcher", "focus": "contract"})
    assert a.status_code == 201 and a.json()["profile_name"]
    aid = a.json()["id"]
    assert client.post("/api/agents", json={"profile_id": "acme", "name": "X", "role": "wizard"}).status_code == 422
    assert client.patch(f"/api/agents/{aid}", json={"enabled": False, "instructions": " be brief "}).json()["instructions"] == "be brief"
    assert client.patch(f"/api/agents/{aid}", json={"role": "wizard"}).status_code == 422
    assert client.delete(f"/api/agents/{aid}").status_code == 200
    assert client.delete(f"/api/agents/{aid}").status_code == 404


def test_deleted_team_is_not_reseeded_but_defaults_can_be_restored(client):
    _setup(client)
    for a in client.get("/api/agents?profile_id=acme").json()["agents"]:
        client.delete(f"/api/agents/{a['id']}")
    assert client.get("/api/agents?profile_id=acme").json()["agents"] == []
    assert len(client.post("/api/profiles/acme/agents/defaults").json()["added"]) == 4


def test_multi_agent_run_is_profile_scoped_and_tracked(client, monkeypatch):
    monkeypatch.setattr("app.agents.orchestrator.build_llm", lambda s: FakeLLM())
    _setup(client)
    client.get("/api/agents")
    evs = _events(client, "acme")
    roles = [e["role"] for e in evs if e["type"] == "agent" and e["status"] == "done"]
    assert roles == ["planner", "researcher", "synthesizer"] or "synthesizer" in roles
    sources = next(e for e in evs if e["type"] == "sources")["sources"]
    assert sources and all(s["profile_id"] in ("acme", "common") for s in sources)
    assert evs[-1]["type"] == "done"
    runs = {a["role"]: a["run_count"] for a in client.get("/api/agents?profile_id=acme").json()["agents"]}
    assert runs["planner"] == 1 and runs["synthesizer"] == 1
    # another business's agents were not used
    assert all(a["run_count"] == 0 for a in client.get("/api/agents?profile_id=globex").json()["agents"])


def test_disabled_agents_are_skipped(client, monkeypatch):
    monkeypatch.setattr("app.agents.orchestrator.build_llm", lambda s: FakeLLM())
    _setup(client)
    for a in client.get("/api/agents?profile_id=acme").json()["agents"]:
        client.patch(f"/api/agents/{a['id']}", json={"enabled": False})
    evs = _events(client, "acme")
    assert not [e for e in evs if e["type"] == "agent"]
    assert any(e["type"] == "token" for e in evs)


class GraphLLM(FakeLLM):
    def chat(self, messages):
        if "named entities" in messages[0]["content"]:
            return '["Globex", "refunds", "refunds"]'
        return super().chat(messages)


def test_graph_rag_llm_fallback_when_graph_disabled(client, monkeypatch):
    client.main.cfg.update({"graph_enabled": False})
    monkeypatch.setattr("app.rag.pipeline.build_llm", lambda s: GraphLLM())
    _setup(client)
    write(client.data / "acme" / "other.md", "Refunds for Globex orders are handled by the partner desk.")
    client.sync()

    def run(graph):
        r = client.post("/api/chat", json={"profile_id": "acme", "message": "refund policy", "graph_rag": graph})
        return next(e for e in (json.loads(l[5:]) for l in r.text.split("\n\n") if l.startswith("data:")) if e["type"] == "sources")

    off, on = run(False), run(True)
    assert off["graph"] == {"enabled": False, "entities": []}
    assert on["graph"]["entities"] == ["Globex", "refunds"]
    assert len(on["sources"]) >= len(off["sources"])
    assert all(s["profile_id"] in ("acme", "common") for s in on["sources"])
