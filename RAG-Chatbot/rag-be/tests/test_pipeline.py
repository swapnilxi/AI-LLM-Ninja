"""End-to-end tests that need no network: hash embedder + Chroma + a stubbed LLM."""
import importlib
import json

import pytest
from fastapi.testclient import TestClient


from conftest import write


@pytest.fixture()
def pets(client):
    """A 'pets' profile holding two documents."""
    write(client.data / "pets" / "cats.txt", "Cats are small carnivorous mammals. Cats sleep for most of the day.")
    write(client.data / "pets" / "space.md", "The Voyager probes left the solar system. Voyager 1 launched in 1977.")
    client.sync()
    client.pets = client.data / "pets"
    return client


def test_sync_chat_and_incremental(pets):
    client = pets
    st = client.sync("pets")
    assert st["state"] == "done" and st["result"]["unchanged"] == 2

    r = client.post("/api/chat", json={"profile_id": "pets", "message": "When did Voyager 1 launch?", "stream": False}).json()
    assert r["sources"][0]["source"] == "space.md" and r["sources"][0]["scope"] == "profile"

    # streaming endpoint yields sources -> tokens -> done
    with client.stream("POST", "/api/chat", json={"profile_id": "pets", "message": "Tell me about cats"}) as resp:
        events = [json.loads(l[6:]) for l in resp.iter_lines() if l.startswith("data: ")]
    assert [e["type"] for e in events][0] == "sources" and events[-1]["type"] == "done"
    assert events[0]["sources"][0]["source"] == "cats.txt"

    # unchanged files are skipped, modified re-indexed, deleted removed
    assert client.sync("pets")["result"]["unchanged"] == 2
    (client.pets / "cats.txt").write_text("Dogs are loyal.")
    (client.pets / "space.md").unlink()
    res = client.sync("pets")["result"]
    assert res["updated"] == ["cats.txt"] and res["removed"] == ["space.md"]
    docs = {d["relative_path"]: d["status"] for d in client.get("/api/profiles/pets/documents").json()["documents"]}
    assert docs == {"cats.txt": "INDEXED"}


def test_embedding_switch_requires_rebuild(pets):
    client = pets
    client.put("/api/config", json={"values": {"embedding_model": "hash-other"}})
    r = client.post("/api/chat", json={"profile_id": "pets", "message": "cats", "stream": False})
    assert r.status_code == 409 and r.json()["code"] == "index_mismatch"
    assert client.sync(rebuild=True)["state"] == "done"
    assert client.post("/api/chat", json={"profile_id": "pets", "message": "cats", "stream": False}).status_code == 200


def test_config_secrets_masked_and_validated(client):
    client.put("/api/config", json={"values": {"gemini_api_key": "AIzaSyABCDEFGHIJKLMN", "top_k": 3}})
    vals = client.get("/api/config").json()["values"]
    assert vals["gemini_api_key"].startswith("••••") and "ABCDEFGH" not in vals["gemini_api_key"]
    # echoing the masked value back must not overwrite the real key
    client.put("/api/config", json={"values": {"gemini_api_key": vals["gemini_api_key"]}})
    assert client.main.cfg.current.gemini_api_key == "AIzaSyABCDEFGHIJKLMN"
    assert client.put("/api/config", json={"values": {"chunk_size": 100, "chunk_overlap": 500}}).status_code == 422


def test_upload_rules_and_path_traversal(client):
    client.get("/api/profiles")
    up = "/api/profiles/common/documents"
    ok = client.post(f"{up}?sync=false", files={"files": ("../evil.txt", b"hello", "text/plain")})
    assert ok.json()["saved"] == ["evil.txt"] and (client.data / "common" / "evil.txt").exists()
    assert not (client.data / "evil.txt").exists()
    assert client.post(up, files={"files": ("x.exe", b"x", "application/x")}).status_code == 400
    assert client.delete("/api/profiles/common/documents/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_admin_token(client, monkeypatch):
    monkeypatch.setattr(client.main.server, "admin_token", "secret")
    assert client.get("/api/health").json()["auth_required"] is True
    assert client.get("/api/config").status_code == 401
    assert client.get("/api/config", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_locked_config(client, monkeypatch):
    monkeypatch.setattr(client.main.server, "allow_ui_config", False)
    assert client.put("/api/config", json={"values": {"top_k": 9}}).status_code == 403


def test_openai_and_groq_providers(monkeypatch):
    """Request shapes for the OpenAI-compatible providers (no network)."""
    from app.config import Settings
    from app.embeddings import build_embedder
    from app.llm import build_llm

    s = Settings(llm_provider="openai", llm_model="gpt-5-mini", llm_max_tokens=50, openai_api_key="k")
    body = build_llm(s)._payload([{"role": "user", "content": "x"}], True)
    assert body["max_completion_tokens"] == 50 and "max_tokens" not in body and "temperature" not in body

    g = build_llm(Settings(llm_provider="groq", groq_api_key="k"))
    assert g.model == "llama-3.3-70b-versatile" and g.base_url == "https://api.groq.com/openai/v1"

    seen = {}

    def fake_request(method, url, **kw):
        seen.update(url=url, json=kw["json"])
        return {"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]}

    monkeypatch.setattr("app.embeddings.remote.request_json", fake_request)
    e = build_embedder(Settings(embedding_provider="openai", openai_api_key="k", embedding_dimensions=256))
    assert e.embed_documents(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]  # re-ordered by index
    assert seen["url"].endswith("/embeddings") and seen["json"]["dimensions"] == 256
    assert e.signature == "openai|text-embedding-3-small|256"


def test_llm_providers_are_self_consistent():
    """Each provider folder's spec.py is the single source of truth; config/UI must agree with it."""
    import typing
    from app.config import Settings
    from app.llm import PROVIDERS, llm_catalog

    assert set(typing.get_args(Settings.model_fields["llm_provider"].annotation)) == set(PROVIDERS)
    defaults = Settings()
    for pid, cls in PROVIDERS.items():
        spec = cls.spec
        assert spec.id == pid and spec.default_model in llm_catalog()[pid]["models"] + [spec.default_model]
        for f in spec.fields:
            assert f in Settings.model_fields, f"{pid}: unknown settings field {f}"
        if spec.base_url_field:
            assert getattr(defaults, spec.base_url_field) == spec.default_base_url, pid
    assert llm_catalog()["openai"]["fields"] == ["openai_api_key", "openai_base_url"]


def test_openai_reasoning_model_quirks(monkeypatch):
    import asyncio
    from app.llm.openai import OpenAILLM, get_openai_chat_response
    from app.config import Settings

    seen = {}
    monkeypatch.setattr("app.llm.oneshot.current_settings", lambda: Settings(openai_api_key="k"))

    def fake_chat(self, messages):
        seen["body"] = self._payload(messages, False)
        return " hi "

    monkeypatch.setattr(OpenAILLM, "chat", fake_chat)
    assert asyncio.run(get_openai_chat_response("ctx", "q", model="gpt-5-mini")) == "hi"
    assert "max_completion_tokens" not in seen["body"] and "temperature" not in seen["body"]  # no cap, no temp
    asyncio.run(get_openai_chat_response("ctx", "q", model="gpt-4o-mini"))
    assert seen["body"]["max_completion_tokens"] == 512 and "temperature" in seen["body"]


def test_query_context_and_provider_override(pets, monkeypatch):
    client = pets
    r = client.post("/api/query-context", json={"profile_id": "pets", "query": "Voyager launch", "limit": 1}).json()
    assert len(r["sources"]) == 1 and "Voyager" in r["context"]

    used = {}
    monkeypatch.setattr("app.rag.pipeline.build_llm", lambda s: (used.update(p=s.llm_provider, m=s.llm_model), type("L", (), {"stream": lambda self, m: iter(["ok"])})())[1])
    client.post("/api/chat", json={"profile_id": "pets", "message": "hi", "stream": False, "provider": "groq", "model": "x"})
    assert used == {"p": "groq", "m": "x"}
    assert client.post("/api/chat", json={"profile_id": "pets", "message": "hi", "provider": "nope"}).status_code == 422
    assert client.get("/").json()["docs"] == "/docs"


def test_streaming_retries_transient_503_before_first_token(monkeypatch):
    """Gemini's 'model is experiencing high demand' 503 should be retried, not shown to the user."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from app.config import Settings
    from app.llm import build_llm

    hits = {"n": 0}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"]))
            hits["n"] += 1
            if hits["n"] <= 2:
                self.send_response(503); self.send_header("retry-after", "0"); self.end_headers()
                self.wfile.write(b'{"error":{"message":"high demand"}}')
                return
            self.send_response(200); self.end_headers()
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": "hello"}}]}) + "\n\ndata: [DONE]\n\n").encode())

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr("app.http.time.sleep", lambda s: None)
    s = Settings(llm_provider="groq", groq_api_key="k", groq_base_url=f"http://127.0.0.1:{srv.server_port}/v1")
    assert build_llm(s).chat([{"role": "user", "content": "x"}]) == "hello" and hits["n"] == 3

    hits["n"] = -10  # never recovers: after the retries the real error is reported
    import pytest
    from app.http import ProviderError
    with pytest.raises(ProviderError, match="503"):
        build_llm(s).chat([{"role": "user", "content": "x"}])
