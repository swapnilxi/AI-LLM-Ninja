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
"""

_PROFILE_FIELDS = {"name", "description", "instructions", "include_common"}
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
        d["is_common"], d["include_common"] = bool(d["is_common"]), bool(d["include_common"])
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
        if "include_common" in fields:
            fields["include_common"] = int(bool(fields["include_common"]))
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
        with self._conn() as c:
            c.execute(sql, args)

    def recover_interrupted(self) -> None:
        """Documents left INDEXING by a crashed run go back to PENDING (call once at startup)."""
        with self._conn() as c:
            c.execute("UPDATE documents SET status='PENDING' WHERE status='INDEXING'")

    def purge_profile_documents(self, profile_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM documents WHERE profile_id=?", (profile_id,))

    def stats(self, profile_id: str) -> dict:
        with self._conn() as c:
            rows = c.execute("SELECT status, COUNT(*) n, COALESCE(SUM(file_size),0) size FROM documents "
                             "WHERE profile_id=? GROUP BY status", (profile_id,)).fetchall()
        by = {r["status"]: r["n"] for r in rows}
        total = sum(v for k, v in by.items() if k != DELETED)
        return {"documents": total, "indexed": by.get(INDEXED, 0), "pending": sum(by.get(s, 0) for s in (DISCOVERED, PENDING, STALE, INDEXING)),
                "failed": by.get(FAILED, 0), "bytes": sum(r["size"] for r in rows), "by_status": by}
