"""Default graph store: one local SQLite file, no server, no extra dependency."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator, Sequence

from ..config import Settings, resolve_path
from ..vectorstores.base import Chunk, Hit
from .base import MIN_ENTITY_LEN, Entity, GraphInfo, GraphStore, norm_entity

SCHEMA = """
CREATE TABLE IF NOT EXISTS g_chunks (
    profile_id TEXT NOT NULL, document_id TEXT NOT NULL, idx INTEGER NOT NULL,
    source TEXT NOT NULL, page INTEGER, text TEXT NOT NULL,
    PRIMARY KEY (document_id, idx)
);
CREATE INDEX IF NOT EXISTS g_chunks_profile ON g_chunks(profile_id);
CREATE TABLE IF NOT EXISTS g_mentions (
    profile_id TEXT NOT NULL, document_id TEXT NOT NULL, idx INTEGER NOT NULL,
    entity TEXT NOT NULL, label TEXT NOT NULL,
    PRIMARY KEY (document_id, idx, entity)
);
CREATE INDEX IF NOT EXISTS g_mentions_entity ON g_mentions(profile_id, entity);
"""
HOP2_ENTITIES = 12  # co-occurring entities followed on the second hop


def _marks(n: int) -> str:
    return ",".join("?" * n)


class SqliteGraphStore(GraphStore):
    def __init__(self, settings: Settings):
        self.path = resolve_path(settings.graph_db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        try:
            with c:
                yield c
        finally:
            c.close()

    def add(self, rows: Sequence[tuple[Chunk, Sequence[str]]]) -> None:
        with self._lock, self._conn() as c:
            for ch, entities in rows:
                c.execute("INSERT OR REPLACE INTO g_chunks VALUES (?,?,?,?,?,?)",
                          (ch.profile_id, ch.document_id, ch.index, ch.source, ch.page, ch.text))
                seen: set[str] = set()
                for e in entities:
                    n = norm_entity(e)
                    if len(n) >= MIN_ENTITY_LEN and n not in seen:
                        seen.add(n)
                        c.execute("INSERT OR REPLACE INTO g_mentions VALUES (?,?,?,?,?)",
                                  (ch.profile_id, ch.document_id, ch.index, n, e.strip()))

    def delete_document(self, document_id: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM g_chunks WHERE document_id=?", (document_id,))
            c.execute("DELETE FROM g_mentions WHERE document_id=?", (document_id,))

    def delete_profile(self, profile_id: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM g_chunks WHERE profile_id=?", (profile_id,))
            c.execute("DELETE FROM g_mentions WHERE profile_id=?", (profile_id,))

    def reset(self) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM g_chunks")
            c.execute("DELETE FROM g_mentions")

    def has_data(self, profile_ids: Sequence[str]) -> bool:
        with self._conn() as c:
            return c.execute(f"SELECT 1 FROM g_mentions WHERE profile_id IN ({_marks(len(profile_ids))}) LIMIT 1",
                             list(profile_ids)).fetchone() is not None

    def find_in_text(self, text: str, profile_ids: Sequence[str], limit: int = 8) -> list[Entity]:
        q = norm_entity(text)
        with self._conn() as c:
            rows = c.execute(
                f"SELECT entity, MIN(label) AS label, COUNT(*) AS n FROM g_mentions "
                f"WHERE profile_id IN ({_marks(len(profile_ids))}) AND instr(?, entity) > 0 "
                f"GROUP BY entity ORDER BY length(entity) DESC, n ASC LIMIT ?", [*profile_ids, q, limit]).fetchall()
        return [Entity(r["entity"], r["label"]) for r in rows]

    def entities_of(self, chunks: Sequence[tuple[str, int]], limit: int = 6) -> list[Entity]:
        if not chunks:
            return []
        where = " OR ".join("(document_id=? AND idx=?)" for _ in chunks)
        args = [v for ch in chunks for v in ch]
        with self._conn() as c:
            rows = c.execute(f"SELECT entity, MIN(label) AS label, COUNT(*) AS n FROM g_mentions WHERE {where} "
                             f"GROUP BY entity ORDER BY n DESC, length(entity) DESC LIMIT ?", [*args, limit]).fetchall()
        return [Entity(r["entity"], r["label"]) for r in rows]

    def _chunks_mentioning(self, c: sqlite3.Connection, norms: Sequence[str], profile_ids: Sequence[str], limit: int):
        return c.execute(
            f"SELECT m.document_id AS d, m.idx AS i, COUNT(DISTINCT m.entity) AS k FROM g_mentions m "
            f"WHERE m.profile_id IN ({_marks(len(profile_ids))}) AND m.entity IN ({_marks(len(norms))}) "
            f"GROUP BY m.document_id, m.idx ORDER BY k DESC, m.document_id, m.idx LIMIT ?",
            [*profile_ids, *norms, limit]).fetchall()

    def neighbors(self, entities, profile_ids, limit, exclude, hops: int = 2) -> list[Hit]:
        norms = [e.norm for e in entities]
        if not norms or limit <= 0:
            return []
        found: dict[tuple[str, int], float] = {}
        with self._conn() as c:
            room = limit + len(exclude)
            for r in self._chunks_mentioning(c, norms, profile_ids, room):
                found[(r["d"], r["i"])] = r["k"] / len(norms)
            if hops >= 2:
                near = c.execute(
                    f"SELECT m2.entity AS e, COUNT(*) AS n FROM g_mentions m1 JOIN g_mentions m2 "
                    f"ON m1.document_id=m2.document_id AND m1.idx=m2.idx "
                    f"WHERE m1.profile_id IN ({_marks(len(profile_ids))}) AND m1.entity IN ({_marks(len(norms))}) "
                    f"AND m2.entity NOT IN ({_marks(len(norms))}) GROUP BY m2.entity ORDER BY n DESC LIMIT ?",
                    [*profile_ids, *norms, *norms, HOP2_ENTITIES]).fetchall()
                near_norms = [r["e"] for r in near]
                if near_norms:
                    for r in self._chunks_mentioning(c, near_norms, profile_ids, room):
                        found.setdefault((r["d"], r["i"]), 0.5 * r["k"] / len(near_norms))
            keys = [k for k, _ in sorted(found.items(), key=lambda kv: -kv[1]) if k not in exclude][:limit]
            hits = []
            for d, i in keys:
                row = c.execute("SELECT * FROM g_chunks WHERE document_id=? AND idx=?", (d, i)).fetchone()
                if row:
                    hits.append(Hit(row["profile_id"], d, row["source"], i, row["text"], round(found[(d, i)], 4), row["page"]))
        return hits

    def ping(self) -> GraphInfo:
        with self._conn() as c:
            chunks = c.execute("SELECT COUNT(*) FROM g_chunks").fetchone()[0]
            ents = c.execute("SELECT COUNT(DISTINCT profile_id || '|' || entity) FROM g_mentions").fetchone()[0]
        return GraphInfo("sqlite", str(self.path), chunks, ents)
