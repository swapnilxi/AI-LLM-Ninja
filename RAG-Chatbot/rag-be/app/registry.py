"""SQLite registry: application metadata for profiles and documents.

The filesystem (data/<profile>/**) holds the real documents and the vector store holds the chunks.
This database records *what the app knows about them*: profile settings, and per-document
indexing state (hash, status, which embedding/chunking configuration produced the chunks).
"""
from __future__ import annotations

import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

COMMON_ID = "common"

# document lifecycle
DISCOVERED, PENDING, INDEXING, INDEXED, STALE, FAILED, DELETED = (
    "DISCOVERED", "PENDING", "INDEXING", "INDEXED", "STALE", "FAILED", "DELETED",
)
STATUSES = (DISCOVERED, PENDING, INDEXING, INDEXED, STALE, FAILED, DELETED)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    folder_path TEXT NOT NULL UNIQUE,      -- folder name below the data root (== id)
    description TEXT NOT NULL DEFAULT '',
    instructions TEXT NOT NULL DEFAULT '',
    is_common INTEGER NOT NULL DEFAULT 0,
    include_common INTEGER NOT NULL DEFAULT 1,
    use_faqs INTEGER NOT NULL DEFAULT 1,   -- FAQs of this profile are searchable by chat
    status TEXT NOT NULL DEFAULT 'active', -- active | missing (folder gone) | removed (hidden, not re-discovered)
    last_sync_at REAL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,               -- absolute managed path (never sent to the browser)
    relative_path TEXT NOT NULL,           -- posix path inside the profile folder
    filename TEXT NOT NULL,
    extension TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    mtime_ns INTEGER NOT NULL DEFAULT 0,
    file_hash TEXT NOT NULL DEFAULT '',    -- sha256 of the file as last seen on disk
    indexed_hash TEXT NOT NULL DEFAULT '', -- sha256 of the content that produced the current chunks
    status TEXT NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    embedding_model TEXT NOT NULL DEFAULT '',     -- embedder signature: provider|model|dims
    embedding_version TEXT NOT NULL DEFAULT '',
    chunking_version TEXT NOT NULL DEFAULT '',
    embedding_dimension INTEGER NOT NULL DEFAULT 0,
    indexed_at REAL,
    error_message TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE (profile_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_documents_profile ON documents(profile_id, status);
CREATE TABLE IF NOT EXISTS faqs (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    position INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING | INDEXED | FAILED | DISABLED (not in the vector index)
    indexed_hash TEXT NOT NULL DEFAULT '',  -- sha256(question + answer) that produced the current chunk
    embedding_model TEXT NOT NULL DEFAULT '',
    indexed_at REAL,
    error_message TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_faqs_profile ON faqs(profile_id, position);
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE (profile_id, name)
);
CREATE INDEX IF NOT EXISTS idx_categories_profile ON categories(profile_id, position);
CREATE TABLE IF NOT EXISTS document_categories (
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, category_id)
);
CREATE INDEX IF NOT EXISTS idx_document_categories_category ON document_categories(category_id);
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,  -- the business this agent works for
    name TEXT NOT NULL,
    role TEXT NOT NULL,                    -- planner | researcher | critic | synthesizer
    description TEXT NOT NULL DEFAULT '',
    instructions TEXT NOT NULL DEFAULT '',
    focus TEXT NOT NULL DEFAULT '',        -- researchers: extra search terms appended to every query
    model TEXT NOT NULL DEFAULT '',        -- '' = the configured LLM model
    enabled INTEGER NOT NULL DEFAULT 1,
    position INTEGER NOT NULL DEFAULT 0,
    run_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    last_run_at REAL,
    last_error TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agents_profile ON agents(profile_id, position);
"""

AGENT_ROLES = ("planner", "researcher", "critic", "synthesizer")
_AGENT_FIELDS = {"name", "role", "description", "instructions", "focus", "model", "enabled"}

_FAQ_FIELDS = {"question", "answer", "category", "enabled", "status", "indexed_hash", "embedding_model", "indexed_at", "error_message"}

_PROFILE_FIELDS = {"name", "description", "instructions", "include_common", "use_faqs"}
_DOC_FIELDS = {
    "file_path", "filename", "extension", "file_size", "mtime_ns", "file_hash", "indexed_hash", "status",
    "chunk_count", "embedding_model", "embedding_version", "chunking_version", "embedding_dimension",
    "indexed_at", "error_message",
}


class Registry:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.scan_lock = threading.RLock()  # serialises filesystem->SQLite scans (request threads + index worker)
        with self._conn() as c:
            c.executescript(SCHEMA)
            cols = {row["name"] for row in c.execute("PRAGMA table_info(profiles)")}
            if "use_faqs" not in cols:  # databases created before the FAQ manager
                c.execute("ALTER TABLE profiles ADD COLUMN use_faqs INTEGER NOT NULL DEFAULT 1")
            if "agents_seeded" not in cols:  # databases created before the agent manager
                c.execute("ALTER TABLE profiles ADD COLUMN agents_seeded INTEGER NOT NULL DEFAULT 0")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        # one short-lived connection per operation: safe across request threads and the index worker
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        try:
            with c:
                yield c
        finally:
            c.close()

    # ------------------------------------------------------------ profiles
    @staticmethod
    def _profile(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        d["is_common"], d["include_common"], d["use_faqs"] = bool(d["is_common"]), bool(d["include_common"]), bool(d["use_faqs"])
        return d

    def get_profile(self, profile_id: str) -> dict | None:
        with self._conn() as c:
            return self._profile(c.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone())

    def list_profiles(self, include_removed: bool = False) -> list[dict]:
        sql = "SELECT * FROM profiles" + ("" if include_removed else " WHERE status != 'removed'")
        with self._conn() as c:
            rows = c.execute(sql + " ORDER BY is_common DESC, name COLLATE NOCASE").fetchall()
        return [self._profile(r) for r in rows]

    def create_profile(self, profile_id: str, name: str, *, description: str = "", instructions: str = "",
                       include_common: bool = True) -> dict:
        if not SLUG_RE.match(profile_id):
            raise ValueError(f"Invalid profile id '{profile_id}'")
        now = time.time()
        with self._conn() as c:
            c.execute(
                "INSERT INTO profiles (id, name, folder_path, description, instructions, is_common, include_common, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (profile_id, name, profile_id, description, instructions, int(profile_id == COMMON_ID),
                 int(include_common), now, now),
            )
        return self.get_profile(profile_id)  # type: ignore[return-value]

    def update_profile(self, profile_id: str, **fields: Any) -> dict:
        bad = set(fields) - _PROFILE_FIELDS - {"status", "last_sync_at"}
        if bad:
            raise ValueError(f"Unknown profile fields: {sorted(bad)}")
        for k in ("include_common", "use_faqs"):
            if k in fields:
                fields[k] = int(bool(fields[k]))
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            with self._conn() as c:
                c.execute(f"UPDATE profiles SET {sets}, updated_at=? WHERE id=?", (*fields.values(), time.time(), profile_id))
        return self.get_profile(profile_id)  # type: ignore[return-value]

    def delete_profile(self, profile_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM profiles WHERE id=?", (profile_id,))  # documents cascade

    # ------------------------------------------------------------ documents
    def get_document(self, document_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        return dict(r) if r else None

    def list_documents(self, profile_id: str, statuses: tuple[str, ...] | None = None) -> list[dict]:
        sql, args = "SELECT * FROM documents WHERE profile_id=?", [profile_id]
        if statuses:
            sql += f" AND status IN ({','.join('?' * len(statuses))})"
            args += list(statuses)
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql + " ORDER BY relative_path", args).fetchall()]

    def add_document(self, profile_id: str, relative_path: str, **fields: Any) -> dict:
        now = time.time()
        doc_id = uuid.uuid4().hex
        row = {"file_path": "", "filename": Path(relative_path).name, "extension": Path(relative_path).suffix.lower(),
               "status": DISCOVERED, **fields}
        cols = ["id", "profile_id", "relative_path", "created_at", "updated_at", *row]
        with self._conn() as c:
            c.execute(f"INSERT INTO documents ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                      [doc_id, profile_id, relative_path, now, now, *row.values()])
        return self.get_document(doc_id)  # type: ignore[return-value]

    def update_document(self, document_id: str, **fields: Any) -> None:
        bad = set(fields) - _DOC_FIELDS
        if bad:
            raise ValueError(f"Unknown document fields: {sorted(bad)}")
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        with self._conn() as c:
            c.execute(f"UPDATE documents SET {sets}, updated_at=? WHERE id=?", (*fields.values(), time.time(), document_id))

    def delete_document(self, document_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM documents WHERE id=?", (document_id,))

    def set_status(self, profile_id: str, status: str, *, where: tuple[str, ...] | None = None) -> None:
        """Bulk status change for a profile (e.g. everything -> STALE when re-indexing)."""
        sql, args = "UPDATE documents SET status=?, error_message='', updated_at=? WHERE profile_id=?", [status, time.time(), profile_id]
        if where:
            sql += f" AND status IN ({','.join('?' * len(where))})"
            args += list(where)
        with self._conn() as c:
            c.execute(sql, args)

    def reset_index_state(self, profile_id: str | None = None) -> None:
        """Forget that anything is indexed (after the vector index was dropped)."""
        sql = ("UPDATE documents SET status=CASE WHEN status='DELETED' THEN status ELSE 'STALE' END, chunk_count=0, "
               "indexed_hash='', embedding_model='', embedding_version='', chunking_version='', embedding_dimension=0, "
               "indexed_at=NULL, error_message='', updated_at=?")
        args: list[Any] = [time.time()]
        if profile_id:
            sql += " WHERE profile_id=?"
            args.append(profile_id)
        faq_sql = ("UPDATE faqs SET status='PENDING', indexed_hash='', embedding_model='', indexed_at=NULL, error_message='', "
                   "updated_at=?" + (" WHERE profile_id=?" if profile_id else ""))
        with self._conn() as c:
            c.execute(sql, args)
            c.execute(faq_sql, args)

    # ------------------------------------------------------------ categories (per profile, assignable to documents)
    def list_categories(self, profile_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM categories WHERE profile_id=? ORDER BY position, name COLLATE NOCASE", (profile_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_category(self, category_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
        return dict(r) if r else None

    def create_category(self, profile_id: str, name: str) -> dict:
        now, cid = time.time(), uuid.uuid4().hex
        with self._conn() as c:
            pos = c.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM categories WHERE profile_id=?", (profile_id,)).fetchone()[0]
            c.execute("INSERT INTO categories (id, profile_id, name, position, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                      (cid, profile_id, name, pos, now, now))
        return self.get_category(cid)  # type: ignore[return-value]

    def rename_category(self, category_id: str, name: str) -> dict:
        with self._conn() as c:
            c.execute("UPDATE categories SET name=?, updated_at=? WHERE id=?", (name, time.time(), category_id))
        return self.get_category(category_id)  # type: ignore[return-value]

    def delete_category(self, category_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM categories WHERE id=?", (category_id,))  # document_categories rows cascade

    def document_category_ids(self, profile_id: str) -> dict[str, list[str]]:
        """document_id -> [category_id, ...] for every document of a profile, in one query."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT dc.document_id, dc.category_id FROM document_categories dc "
                "JOIN documents d ON d.id = dc.document_id WHERE d.profile_id=?", (profile_id,),
            ).fetchall()
        out: dict[str, list[str]] = {}
        for r in rows:
            out.setdefault(r["document_id"], []).append(r["category_id"])
        return out

    def category_ids_for_document(self, document_id: str) -> list[str]:
        with self._conn() as c:
            rows = c.execute("SELECT category_id FROM document_categories WHERE document_id=?", (document_id,)).fetchall()
        return [r["category_id"] for r in rows]

    def set_document_categories(self, document_id: str, category_ids: list[str]) -> None:
        """Full replace: a document's categories become exactly `category_ids`."""
        with self._conn() as c:
            c.execute("DELETE FROM document_categories WHERE document_id=?", (document_id,))
            c.executemany("INSERT OR IGNORE INTO document_categories (document_id, category_id) VALUES (?,?)",
                          [(document_id, cid) for cid in category_ids])

    # ------------------------------------------------------------ agents
    @staticmethod
    def _agent(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        return d

    def list_agents(self, profile_id: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM agents", []
        if profile_id:
            sql, args = sql + " WHERE profile_id=?", [profile_id]
        with self._conn() as c:
            rows = c.execute(sql + " ORDER BY profile_id, position, created_at", args).fetchall()
        return [self._agent(r) for r in rows]

    def get_agent(self, agent_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        return self._agent(r) if r else None

    def add_agent(self, profile_id: str, name: str, role: str, *, description: str = "", instructions: str = "",
                  focus: str = "", model: str = "", enabled: bool = True) -> dict:
        if role not in AGENT_ROLES:
            raise ValueError(f"Unknown agent role '{role}'")
        now, aid = time.time(), uuid.uuid4().hex
        with self._conn() as c:
            pos = c.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM agents WHERE profile_id=?", (profile_id,)).fetchone()[0]
            c.execute("INSERT INTO agents (id, profile_id, name, role, description, instructions, focus, model, enabled, position, "
                      "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                      (aid, profile_id, name, role, description, instructions, focus, model, int(enabled), pos, now, now))
        return self.get_agent(aid)  # type: ignore[return-value]

    def update_agent(self, agent_id: str, **fields: Any) -> dict:
        bad = set(fields) - _AGENT_FIELDS
        if bad:
            raise ValueError(f"Unknown agent fields: {sorted(bad)}")
        if fields.get("role", "researcher") not in AGENT_ROLES:
            raise ValueError(f"Unknown agent role '{fields['role']}'")
        if "enabled" in fields:
            fields["enabled"] = int(bool(fields["enabled"]))
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            with self._conn() as c:
                c.execute(f"UPDATE agents SET {sets}, updated_at=? WHERE id=?", (*fields.values(), time.time(), agent_id))
        return self.get_agent(agent_id)  # type: ignore[return-value]

    def delete_agent(self, agent_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM agents WHERE id=?", (agent_id,))

    def record_agent_run(self, agent_id: str, error: str = "") -> None:
        with self._conn() as c:
            c.execute("UPDATE agents SET run_count=run_count+1, error_count=error_count+?, last_run_at=?, last_error=? WHERE id=?",
                      (1 if error else 0, time.time(), error[:500], agent_id))

    def agents_seeded(self, profile_id: str) -> bool:
        with self._conn() as c:
            r = c.execute("SELECT agents_seeded FROM profiles WHERE id=?", (profile_id,)).fetchone()
        return bool(r and r[0])

    def mark_agents_seeded(self, profile_id: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE profiles SET agents_seeded=1 WHERE id=?", (profile_id,))

    # ------------------------------------------------------------ FAQs
    def list_faqs(self, profile_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM faqs WHERE profile_id=? ORDER BY position, created_at", (profile_id,)).fetchall()
        return [self._faq(r) for r in rows]

    @staticmethod
    def _faq(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        return d

    def get_faq(self, faq_id: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM faqs WHERE id=?", (faq_id,)).fetchone()
        return self._faq(r) if r else None

    def add_faq(self, profile_id: str, question: str, answer: str, *, category: str = "", enabled: bool = True) -> dict:
        now, fid = time.time(), uuid.uuid4().hex
        with self._conn() as c:
            pos = c.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM faqs WHERE profile_id=?", (profile_id,)).fetchone()[0]
            c.execute("INSERT INTO faqs (id, profile_id, question, answer, category, enabled, position, created_at, updated_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?)", (fid, profile_id, question, answer, category, int(enabled), pos, now, now))
        return self.get_faq(fid)  # type: ignore[return-value]

    def update_faq(self, faq_id: str, **fields: Any) -> None:
        bad = set(fields) - _FAQ_FIELDS
        if bad:
            raise ValueError(f"Unknown FAQ fields: {sorted(bad)}")
        if "enabled" in fields:
            fields["enabled"] = int(bool(fields["enabled"]))
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            with self._conn() as c:
                c.execute(f"UPDATE faqs SET {sets}, updated_at=? WHERE id=?", (*fields.values(), time.time(), faq_id))

    def delete_faq(self, faq_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM faqs WHERE id=?", (faq_id,))

    def delete_faqs(self, profile_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM faqs WHERE profile_id=?", (profile_id,))

    def recover_interrupted(self) -> None:
        """Documents left INDEXING by a crashed run go back to PENDING (call once at startup)."""
        with self._conn() as c:
            c.execute("UPDATE documents SET status='PENDING' WHERE status='INDEXING'")

    def purge_profile_documents(self, profile_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM documents WHERE profile_id=?", (profile_id,))
        # FAQs are user-authored content: keep the rows, but their chunks are gone with the profile index
        self.reset_faq_index_state(profile_id)

    def reset_faq_index_state(self, profile_id: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE faqs SET status='PENDING', indexed_hash='', embedding_model='', indexed_at=NULL, "
                      "error_message='', updated_at=? WHERE profile_id=?", (time.time(), profile_id))

    def stats(self, profile_id: str) -> dict:
        with self._conn() as c:
            rows = c.execute("SELECT status, COUNT(*) n, COALESCE(SUM(file_size),0) size FROM documents "
                             "WHERE profile_id=? GROUP BY status", (profile_id,)).fetchall()
        with self._conn() as c:
            fq = c.execute("SELECT COUNT(*) n, COALESCE(SUM(status='INDEXED'),0) i, COALESCE(SUM(enabled),0) e FROM faqs "
                           "WHERE profile_id=?", (profile_id,)).fetchone()
        by = {r["status"]: r["n"] for r in rows}
        total = sum(v for k, v in by.items() if k != DELETED)
        return {"documents": total, "indexed": by.get(INDEXED, 0), "pending": sum(by.get(s, 0) for s in (DISCOVERED, PENDING, STALE, INDEXING)),
                "failed": by.get(FAILED, 0), "faqs": fq["n"], "faqs_enabled": fq["e"], "faqs_indexed": fq["i"], "bytes": sum(r["size"] for r in rows), "by_status": by}
