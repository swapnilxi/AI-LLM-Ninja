"""FAQ manager: SQLite storage, JSON import/export, and the same profile isolation as documents."""
import json

import pytest
from conftest import FakeLLM


@pytest.fixture()
def two(client):
    for name in ("company1", "company2"):
        client.post("/api/profiles", json={"name": name})
    client.wait()
    return client


def faq(c, pid, q, a, **kw):
    r = c.post(f"/api/profiles/{pid}/faqs", json={"question": q, "answer": a, **kw})
    assert r.status_code == 201, r.text
    c.wait()
    return r.json()


def ask(c, pid, q):
    return c.post("/api/chat", json={"profile_id": pid, "message": q, "stream": False}).json()


def test_faq_crud_is_stored_and_used_in_answers(two):
    f = faq(two, "company1", "What are your opening hours?", "We are open 9 to 5 on weekdays. Code OPEN-777.")
    assert f["question"] == "What are your opening hours?" and f["enabled"]
    listing = two.get("/api/profiles/company1/faqs").json()
    assert [x["status"] for x in listing["faqs"]] == ["INDEXED"] and listing["stats"]["faqs_indexed"] == 1

    r = ask(two, "company1", "What are your opening hours?")
    src = r["sources"][0]
    assert src["kind"] == "faq" and src["faq_id"] == f["id"] and "OPEN-777" in src["text"] and src["scope"] == "profile"
    assert "FAQ" in FakeLLM.calls[-1][-1]["content"]

    # edit -> re-embedded
    two.patch(f"/api/profiles/company1/faqs/{f['id']}", json={"answer": "Now open 8 to 6. Code NEW-888."})
    two.wait()
    text = json.dumps(ask(two, "company1", "opening hours"))
    assert "NEW-888" in text and "OPEN-777" not in text

    # delete -> chunk removed immediately
    assert two.delete(f"/api/profiles/company1/faqs/{f['id']}").status_code == 200
    assert ask(two, "company1", "opening hours")["sources"] == []
    assert two.get("/api/profiles/company1/faqs").json()["faqs"] == []


def test_faqs_are_profile_isolated_and_common_is_shared(two):
    faq(two, "company1", "Company 1 wifi password?", "The wifi password is ALPHA-123.")
    faq(two, "company2", "Company 2 wifi password?", "The wifi password is BETA-456.")
    faq(two, "common", "Where is the kitchen?", "The kitchen is on the second floor.")
    r1 = json.dumps(ask(two, "company1", "What is the wifi password?"))
    assert "ALPHA-123" in r1 and "BETA-456" not in r1
    r2 = json.dumps(ask(two, "company2", "What is the wifi password?"))
    assert "BETA-456" in r2 and "ALPHA-123" not in r2
    for pid in ("company1", "company2"):
        srcs = ask(two, pid, "Where is the kitchen?")["sources"]
        assert any(s["kind"] == "faq" and s["scope"] == "common" for s in srcs)
    # a FAQ id of another profile is not reachable
    other = two.get("/api/profiles/company2/faqs").json()["faqs"][0]["id"]
    assert two.patch(f"/api/profiles/company1/faqs/{other}", json={"answer": "hacked"}).status_code == 404
    assert two.delete(f"/api/profiles/company1/faqs/{other}").status_code == 404


def test_disable_and_profile_switch_remove_faqs_from_search(two):
    f = faq(two, "company1", "Secret handshake?", "Two taps then a wave. Code HAND-1.")
    two.patch(f"/api/profiles/company1/faqs/{f['id']}", json={"enabled": False})
    two.wait()
    assert "HAND-1" not in json.dumps(ask(two, "company1", "secret handshake"))
    assert two.get("/api/profiles/company1/faqs").json()["faqs"][0]["status"] == "DISABLED"
    two.patch(f"/api/profiles/company1/faqs/{f['id']}", json={"enabled": True}); two.wait()
    assert "HAND-1" in json.dumps(ask(two, "company1", "secret handshake"))
    # profile-level switch
    assert two.patch("/api/profiles/company1", json={"use_faqs": False}).json()["use_faqs"] is False
    two.wait()
    assert "HAND-1" not in json.dumps(ask(two, "company1", "secret handshake"))
    two.patch("/api/profiles/company1", json={"use_faqs": True}); two.wait()
    assert "HAND-1" in json.dumps(ask(two, "company1", "secret handshake"))


def test_import_export_json_schema(two):
    payload = {"faqs": [{"question": "Q one?", "answer": "A one."}, {"question": "Q two?", "answer": "A two.", "category": "billing"}]}
    r = two.post("/api/profiles/company1/faqs/import", json=payload).json()
    assert r["added"] == 2 and r["skipped_duplicates"] == 0
    two.wait()
    # duplicates (case/space-insensitive) are skipped in append mode
    r = two.post("/api/profiles/company1/faqs/import", json={"faqs": [{"question": " q  ONE? ", "answer": "x"}, {"question": "Q three?", "answer": "A three."}]}).json()
    assert r["added"] == 1 and r["skipped_duplicates"] == 1 and r["total"] == 3
    two.wait()

    exported = two.get("/api/profiles/company1/faqs/export")
    assert "attachment" in exported.headers["content-disposition"]
    data = exported.json()
    assert data == [{"question": "Q one?", "answer": "A one."}, {"question": "Q two?", "answer": "A two."}, {"question": "Q three?", "answer": "A three."}]
    assert all(set(x) == {"question", "answer"} for x in data)

    # what was exported can be imported into another profile (round trip)
    assert two.post("/api/profiles/company2/faqs/import", json={"faqs": data}).json()["added"] == 3
    two.wait()
    assert ask(two, "company2", "Q two?")["sources"][0]["kind"] == "faq"

    # replace deletes the old ones (and their chunks)
    two.post("/api/profiles/company1/faqs/import?mode=replace", json={"faqs": [{"question": "Only one?", "answer": "Yes."}]})
    two.wait()
    assert [f["question"] for f in two.get("/api/profiles/company1/faqs").json()["faqs"]] == ["Only one?"]
    assert "A three" not in json.dumps(ask(two, "company1", "Q three?"))


def test_faq_validation(two):
    base = "/api/profiles/company1/faqs"
    assert two.post(base, json={"question": "", "answer": "x"}).status_code == 422
    assert two.post(base, json={"question": "q", "answer": ""}).status_code == 422
    assert two.post(base, json={"question": "x" * 501, "answer": "a"}).status_code == 422
    assert two.post(f"{base}/import", json={"faqs": [{"question": "q"}]}).status_code == 422       # answer missing
    assert two.post(f"{base}/import?mode=zap", json={"faqs": []}).status_code == 422
    faq(two, "company1", "Dup?", "a")
    assert two.post(base, json={"question": "dup?", "answer": "b"}).status_code == 409
    assert two.post("/api/profiles/nope/faqs", json={"question": "q", "answer": "a"}).status_code == 404


def test_faqs_survive_rebuild_and_profile_index_clear(two):
    faq(two, "company1", "Keep me?", "Yes. Code KEEP-9.")
    two.delete("/api/profiles/company1/index")
    assert two.get("/api/profiles/company1/faqs").json()["faqs"][0]["status"] == "PENDING"
    two.sync("company1")
    assert "KEEP-9" in json.dumps(ask(two, "company1", "Keep me?"))
    assert two.sync(rebuild=True)["state"] == "done"
    assert "KEEP-9" in json.dumps(ask(two, "company1", "Keep me?"))


def test_old_database_gets_use_faqs_column(tmp_path):
    import sqlite3
    from app.registry import Registry

    db = tmp_path / "old.db"
    c = sqlite3.connect(db)
    c.executescript("CREATE TABLE profiles (id TEXT PRIMARY KEY, name TEXT NOT NULL, folder_path TEXT NOT NULL UNIQUE, "
                    "description TEXT NOT NULL DEFAULT '', instructions TEXT NOT NULL DEFAULT '', is_common INTEGER NOT NULL DEFAULT 0, "
                    "include_common INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'active', last_sync_at REAL, "
                    "created_at REAL NOT NULL, updated_at REAL NOT NULL); INSERT INTO profiles (id,name,folder_path,created_at,updated_at) VALUES ('a','A','a',0,0);")
    c.commit(); c.close()
    reg = Registry(db)
    assert reg.get_profile("a")["use_faqs"] is True
