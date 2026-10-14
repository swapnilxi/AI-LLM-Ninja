"""Graph RAG: SQLite graph store, entity extraction, indexing hooks, scoped expansion, rebuild endpoint."""
import json

from conftest import FakeLLM, write

from app.graphstores.extract import heuristic_entities


def test_heuristic_entities():
    ents = heuristic_entities("The Globex Corporation hired Maria Lopez to run Project Atlas. See the NASA report on api-gateway v2.")
    low = {e.lower() for e in ents}
    assert {"globex corporation", "maria lopez", "project atlas", "nasa", "api-gateway"} <= low
    assert "the" not in low and "see" not in low


def _sources(client, pid, msg, graph):
    r = client.post("/api/chat", json={"profile_id": pid, "message": msg, "graph_rag": graph})
    return next(e for e in (json.loads(l[5:]) for l in r.text.split("\n\n") if l.startswith("data:")) if e["type"] == "sources")


def test_graph_links_chunks_across_documents_and_stays_scoped(client, monkeypatch):
    monkeypatch.setattr("app.rag.pipeline.build_llm", lambda s: FakeLLM())
    client.main.cfg.update({"top_k": 1})
    write(client.data / "acme" / "people.md", "Maria Lopez leads Project Atlas for the company.")
    write(client.data / "acme" / "budget.md", "Project Atlas has a budget of 40k dollars.")
    write(client.data / "acme" / "noise.md", "Completely unrelated text about lunch menus.")
    write(client.data / "globex" / "secret.md", "Project Atlas at Globex is confidential.")
    client.sync()
    st = client.get("/api/status").json()["graph"]
    assert st["ok"] and st["backend"] == "sqlite" and st["entities"] > 0

    off = _sources(client, "acme", "Who is Maria Lopez?", False)
    on = _sources(client, "acme", "Who is Maria Lopez?", True)
    names_on = {s["source"] for s in on["sources"]}
    assert len(on["sources"]) > len(off["sources"])
    assert "budget.md" in names_on  # reached through the shared entity "Project Atlas"
    assert any("maria lopez" == e.lower() for e in on["graph"]["entities"])
    assert all(s["profile_id"] in ("acme", "common") for s in on["sources"])  # never globex


def test_graph_cleanup_and_rebuild(client, monkeypatch):
    monkeypatch.setattr("app.rag.pipeline.build_llm", lambda s: FakeLLM())
    f = write(client.data / "acme" / "a.md", "Maria Lopez leads Project Atlas.")
    client.sync()
    graph = client.main.build_graph(client.main.cfg.current)
    assert graph.ping().chunks == 1
    client.main.build_graph(client.main.cfg.current).reset()
    assert graph.ping().chunks == 0
    body = client.post("/api/graph/rebuild?profile_id=acme").json()
    assert body["chunks"] == 1 and body["graph"]["chunks"] == 1
    f.unlink()
    client.sync()
    assert graph.ping().chunks == 0  # removed with the document


def test_neo4j_selected_without_driver_degrades_gracefully(client, monkeypatch):
    client.main.cfg.update({"graph_store": "neo4j", "neo4j_password": "x"})
    write(client.data / "acme" / "a.md", "Maria Lopez leads Project Atlas.")
    st = client.sync()  # indexing must not fail because the graph is unreachable
    assert st["state"] == "done" and not st["result"]["errors"]
    assert client.get("/api/status").json()["graph"]["ok"] is False


def test_neo4j_uri_validation_and_test_endpoint(client):
    bad = client.put("/api/config", json={"values": {"neo4j_uri": "http://example.com"}})
    assert bad.status_code == 422
    for ok in ("bolt://localhost:7687", "neo4j+s://abc123.databases.neo4j.io", "bolt+ssc://10.0.0.5:7687"):
        assert client.put("/api/config", json={"values": {"neo4j_uri": ok}}).status_code == 200
    r = client.post("/api/config/test", json={"target": "graph", "values": {"graph_store": "sqlite"}}).json()
    assert r["ok"] and "sqlite" in r["detail"]
    r = client.post("/api/config/test", json={"target": "graph", "values": {"graph_store": "neo4j", "neo4j_uri": "bolt://127.0.0.1:1"}}).json()
    assert r["ok"] is False and r["detail"]


def test_neo4j_settings_saved_from_ui_persist_and_apply(client):
    r = client.put("/api/config", json={"values": {"graph_store": "neo4j", "neo4j_uri": "neo4j+s://abc.databases.neo4j.io",
                                                   "neo4j_user": "me", "neo4j_password": "supersecret1"}})
    assert r.status_code == 200
    got = client.get("/api/config").json()
    assert got["values"]["neo4j_uri"] == "neo4j+s://abc.databases.neo4j.io" and got["values"]["graph_store"] == "neo4j"
    assert "supersecret1" not in json.dumps(got) and "neo4j_password" in got["ui_overrides"]  # masked, saved from the UI
    assert client.main.cfg.current.neo4j_password == "supersecret1"  # the real value is what the backend uses
    # the masked value echoed back by the form must not overwrite the real password
    client.put("/api/config", json={"values": {"neo4j_password": got["values"]["neo4j_password"], "neo4j_user": "you"}})
    assert client.main.cfg.current.neo4j_password == "supersecret1" and client.main.cfg.current.neo4j_user == "you"
