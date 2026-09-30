"""Shared offline fixture: hash embedder + Chroma + SQLite in a tmp dir + a stubbed LLM."""
import importlib
import time

import pytest
from fastapi.testclient import TestClient


class FakeLLM:
    calls: list = []

    def stream(self, messages):
        FakeLLM.calls.append(messages)
        yield "Answer based on: "
        yield messages[-1]["content"][:40]

    def chat(self, messages):
        return "".join(self.stream(messages))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for k, v in {
        "RAG_DATA_DIR": str(data), "CHROMA_PATH": str(tmp_path / "chroma"), "SETTINGS_FILE": str(tmp_path / "s.json"),
        "DB_FILE": str(tmp_path / "app.db"), "EMBEDDING_PROVIDER": "hash", "VECTOR_STORE": "chroma",
        "SYNC_ON_STARTUP": "false", "TOP_K": "3",
    }.items():
        monkeypatch.setenv(k, v)
    import app.main as main
    main = importlib.reload(main)
    FakeLLM.calls = []
    monkeypatch.setattr("app.rag.build_llm", lambda s: FakeLLM())
    with TestClient(main.app) as c:
        c.main, c.data = main, data

        def wait(timeout=15):
            end = time.time() + timeout
            while time.time() < end:
                st = c.get("/api/ingest/status").json()
                if st["state"] in ("done", "error"):
                    return st
                time.sleep(0.05)
            raise AssertionError("index job timeout")

        def sync(pid=None, rebuild=False):
            path = f"/api/profiles/{pid}/sync" if pid else "/api/profiles/sync"
            assert c.post(f"{path}?rebuild={str(rebuild).lower()}").status_code == 200
            return wait()

        c.wait, c.sync = wait, sync
        yield c


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
