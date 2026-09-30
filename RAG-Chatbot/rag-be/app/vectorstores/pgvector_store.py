"""PostgreSQL + pgvector. Works for local Postgres, Docker, and hosted services such as Neon."""
from __future__ import annotations

import threading
from urllib.parse import urlparse

from ..config import Settings
from ..http import ProviderError
from .base import Chunk, Hit, IndexMismatchError, SourceInfo, StoreInfo, VectorStore, require_scope, safe_identifier

HNSW_MAX_DIM = 2000  # pgvector limit for HNSW on the `vector` type

_pools: dict[str, object] = {}
_pools_lock = threading.Lock()


def _pool(dsn: str):
    try:
        from psycopg_pool import ConnectionPool
    except ImportError as e:
        raise ProviderError("psycopg is not installed. Run: pip install 'psycopg[binary,pool]'") from e
    with _pools_lock:
        if dsn not in _pools:
            # check=... transparently replaces connections that a serverless DB (Neon) closed while idle.
            _pools[dsn] = ConnectionPool(
                dsn, min_size=0, max_size=5, timeout=20, open=True,
                kwargs={"autocommit": True, "connect_timeout": 15}, check=ConnectionPool.check_connection,
            )
        return _pools[dsn]


def close_pools() -> None:
    with _pools_lock:
        for p in _pools.values():
            p.close()
        _pools.clear()


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


class PgVectorStore(VectorStore):
    def __init__(self, settings: Settings):
        if not settings.database_url:
            raise ProviderError("DATABASE_URL is not set (Postgres / Neon connection string)")
        self.dsn = settings.database_url
        self.table = safe_identifier(settings.vector_table)
        self.pool = _pool(self.dsn)

    def _run(self, sql: str, params=None, *, fetch: bool = False, many: list | None = None):
        import psycopg

        try:
            with self.pool.connection() as conn, conn.cursor() as cur:
                if many is not None:
                    cur.executemany(sql, many)
                else:
                    cur.execute(sql, params)
                return cur.fetchall() if fetch else None
        except psycopg.OperationalError as e:
            raise ProviderError(f"Postgres connection failed: {str(e).strip()[:300]}") from e
        except psycopg.errors.UndefinedFile as e:
            raise ProviderError("pgvector extension is not available on this server") from e
        except psycopg.Error as e:
            raise ProviderError(f"Postgres error: {str(e).strip()[:300]}") from e

    def _table_dim(self) -> int | None:
        rows = self._run(
            "SELECT a.atttypmod FROM pg_attribute a WHERE a.attrelid = to_regclass(%s) "
            "AND a.attname = 'embedding' AND NOT a.attisdropped",
            (self.table,), fetch=True,
        )
        return rows[0][0] if rows else None

    def check(self, signature: str) -> None:
        if self._table_dim() is None:
            return
        cols = self._run("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = 'profile_id'",
                         (self.table,), fetch=True)
        if not cols:
            raise IndexMismatchError(
                f"Table '{self.table}' was built before profiles existed. Rebuild the index to add profile metadata."
            )
        rows = self._run(f"SELECT embed_sig FROM {self.table} LIMIT 1", fetch=True)
        if rows and rows[0][0] != signature:
            raise IndexMismatchError(
                f"Table '{self.table}' was built with '{rows[0][0]}' but the current embedder is "
                f"'{signature}'. Rebuild the index to switch embedding models."
            )

    def ensure(self, dim: int, signature: str) -> None:
        self._run("CREATE EXTENSION IF NOT EXISTS vector")
        existing = self._table_dim()
        if existing is not None:
            self.check(signature)
            if existing == dim:
                return
            self._run(f"DROP TABLE {self.table}")  # empty table with a stale dimension
        self._run(
            f"CREATE TABLE {self.table} (id BIGSERIAL PRIMARY KEY, profile_id TEXT NOT NULL, document_id TEXT NOT NULL, "
            f"source TEXT NOT NULL, chunk_index INT NOT NULL, "
            f"content TEXT NOT NULL, page INT, file_hash TEXT NOT NULL, embed_sig TEXT NOT NULL, "
            f"embedding vector({int(dim)}) NOT NULL, UNIQUE (document_id, chunk_index))"
        )
        self._run(f"CREATE INDEX ON {self.table} (profile_id)")
        if dim <= HNSW_MAX_DIM:
            self._run(f"CREATE INDEX ON {self.table} USING hnsw (embedding vector_cosine_ops)")

    def add(self, chunks: list[Chunk], vectors: list[list[float]], signature: str) -> None:
        if not chunks:
            return
        rows = [(c.profile_id, c.document_id, c.source, c.index, c.text, c.page, c.file_hash, signature, _vec(v))
                for c, v in zip(chunks, vectors)]
        self._run(
            f"INSERT INTO {self.table} (profile_id, document_id, source, chunk_index, content, page, file_hash, embed_sig, embedding) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector) "
            "ON CONFLICT (document_id, chunk_index) DO UPDATE SET source = EXCLUDED.source, content = EXCLUDED.content, page = EXCLUDED.page, "
            "file_hash = EXCLUDED.file_hash, embed_sig = EXCLUDED.embed_sig, embedding = EXCLUDED.embedding",
            many=rows,
        )

    def search(self, vector: list[float], k: int, profile_ids) -> list[Hit]:
        ids = require_scope(profile_ids)
        if self._table_dim() is None:
            return []
        v = _vec(vector)
        rows = self._run(
            f"SELECT profile_id, document_id, source, chunk_index, content, page, 1 - (embedding <=> %s::vector) "
            f"FROM {self.table} WHERE profile_id = ANY(%s) ORDER BY embedding <=> %s::vector LIMIT %s",
            (v, ids, v, k), fetch=True,
        )
        return [Hit(r[0], r[1], r[2], r[3], r[4], float(r[6]), r[5]) for r in rows]

    def delete_document(self, document_id: str) -> None:
        if self._table_dim() is not None:
            self._run(f"DELETE FROM {self.table} WHERE document_id = %s", (document_id,))

    def delete_profile(self, profile_id: str) -> None:
        if self._table_dim() is not None:
            self._run(f"DELETE FROM {self.table} WHERE profile_id = %s", (profile_id,))

    def sources(self) -> dict[str, SourceInfo]:
        if self._table_dim() is None:
            return {}
        rows = self._run(f"SELECT document_id, max(file_hash), count(*) FROM {self.table} GROUP BY document_id", fetch=True)
        return {r[0]: SourceInfo(r[1], r[2]) for r in rows}

    def reset(self) -> None:
        self._run(f"DROP TABLE IF EXISTS {self.table}")

    def ping(self) -> StoreInfo:
        self._run("SELECT 1")
        ext = self._run("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'", fetch=True)
        if not ext:
            raise ProviderError("Connected, but the pgvector extension is not available on this server")
        src = self.sources()
        host = urlparse(self.dsn).hostname or "?"
        return StoreInfo("postgres", host, sum(s.chunks for s in src.values()), len(src), {"table": self.table})
