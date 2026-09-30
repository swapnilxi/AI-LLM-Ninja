# db.py — Postgres + pgvector access with asyncpg; one "document_chunks" table holds everything.
#
# This is the hand-written, learn-by-reading version of vector storage. The running app uses
# app/vectorstores/pgvector_store.py (sync, pooled, works with Neon); this file keeps the raw async SQL
# so every step is visible.
#
# Concepts:
#   1. Connection *pool* instead of a connection per query.
#   2. A table with a VECTOR(n) column + an ANN (approximate nearest neighbour) index.
#   3. Idempotent inserts: per-chunk hash + UNIQUE index + ON CONFLICT DO NOTHING.
#   4. The query operator MUST match the index operator class (cosine: <=> / vector_cosine_ops).
#
# Demo (needs Postgres+pgvector, e.g. `docker compose up -d` in RAG-Chatbot/):
#   DATABASE_URL=postgresql://rag:rag@localhost:5432/rag python -m app.core.db   (from rag-be/)
# Needs: pip install asyncpg python-dotenv   (or: pip install -e ".[learning]")
import asyncio
import os
import re
from typing import List, Optional, Tuple

import asyncpg
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# ENV / CONFIG
# -----------------------------------------------------------------------------
DB_URL = os.getenv("DATABASE_URL")
EMBED_DIM = int(os.getenv("EMBED_DIM", "0"))  # 0 = detect from the configured embedding model (recommended)
VECTOR_METRIC = os.getenv("VECTOR_METRIC", "cosine").lower()
CHUNKS_TABLE = os.getenv("CHUNKS_TABLE", "document_chunks")  # keep old name by default

if VECTOR_METRIC not in ("cosine", "l2"):
    raise ValueError("VECTOR_METRIC must be 'cosine' or 'l2'")

# Index operator class and query operator are a matched pair. FIX: the original built a cosine index
# but searched with `<->` (L2 distance), so the index was never used and "distance" meant something else.
VECTOR_OPS = "vector_cosine_ops" if VECTOR_METRIC == "cosine" else "vector_l2_ops"
DISTANCE_OP = "<=>" if VECTOR_METRIC == "cosine" else "<->"


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def _safe_table_name(name: str) -> str:
    """Identifiers can't be bound as $1 parameters, so validate before f-string interpolation."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Invalid table name")
    return name


def _to_pgvector(embedding: List[float]) -> str:
    """Render list[float] as pgvector's text format '[0.1,0.2]'; cast with ::vector in SQL.
    (asyncpg has no built-in codec for `vector`, so raw Python lists fail.)"""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _resolve_dim() -> int:
    """Vector size of the table = output size of the embedding model that fills it. Set EMBED_DIM to force it,
    otherwise ask the configured embedder (sentence-transformers MiniLM = 384, OpenAI 3-small = 1536, ...)."""
    if EMBED_DIM:
        return EMBED_DIM
    from ..config import current_settings
    from ..embeddings import build_embedder

    return len(build_embedder(current_settings()).embed_query("dimension probe"))


# -----------------------------------------------------------------------------
# POOL
# -----------------------------------------------------------------------------
async def get_pool(min_size: int = 1, max_size: int = 10) -> asyncpg.Pool:
    if not DB_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return await asyncpg.create_pool(dsn=DB_URL, min_size=min_size, max_size=max_size)


# -----------------------------------------------------------------------------
# INIT (NON-FATAL IF DATA IS DIRTY)
# -----------------------------------------------------------------------------
async def init_db(pool: asyncpg.Pool) -> None:
    """Ensure extensions, the chunks table (+ dedupe indexes) and the ANN index exist.
    Safe to run repeatedly; won't crash the app if a unique index can't be built due to old duplicates."""
    table = _safe_table_name(CHUNKS_TABLE)
    dim = await asyncio.to_thread(_resolve_dim)  # may load a model: keep it off the event loop

    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        try:  # only needed to backfill hashes on tables created by the old version
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            has_pgcrypto = True
        except asyncpg.PostgresError:
            has_pgcrypto = False

        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id SERIAL PRIMARY KEY,
                content TEXT,
                embedding VECTOR({dim}),
                path TEXT NOT NULL,                       -- document this chunk came from
                filename TEXT NOT NULL,
                size_bytes BIGINT NOT NULL,
                mtime TIMESTAMPTZ NOT NULL,
                sha256 TEXT NOT NULL,                     -- hash of the whole file (change detection)
                processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                chunk_index INT NOT NULL DEFAULT 0,
                chunk_sha256 TEXT                         -- hash of this chunk (dedupe)
            );
        """)

        # An existing table keeps its old vector size; fail early with advice instead of a cryptic insert error.
        existing = await conn.fetchval(
            "SELECT atttypmod FROM pg_attribute WHERE attrelid = to_regclass($1) AND attname = 'embedding'", table
        )
        if existing and existing != dim:
            raise RuntimeError(
                f"Table '{table}' stores {existing}-dim vectors but the embedding model produces {dim}. "
                f"Use another CHUNKS_TABLE, or drop the table to re-index with the new model."
            )

        # Upgrade older tables that predate these columns (no data loss)
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS path TEXT NOT NULL DEFAULT '';")
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS chunk_index INT NOT NULL DEFAULT 0;")
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS chunk_sha256 TEXT;")
        if has_pgcrypto:
            await conn.execute(f"""
                UPDATE {table}
                SET chunk_sha256 = encode(digest(content, 'sha256'), 'hex')
                WHERE chunk_sha256 IS NULL AND content IS NOT NULL;
            """)

        # Unique indexes make re-ingesting the same file a no-op. Don't crash if duplicates already exist.
        for name, cols, where in (
            (f"uq_{table}_doc_idx", "(path, chunk_index)", ""),
            (f"uq_{table}_doc_hash", "(path, chunk_sha256)", "WHERE chunk_sha256 IS NOT NULL"),
        ):
            try:
                await conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table}{cols} {where};")
            except asyncpg.PostgresError as e:
                print(f"[init_db] WARN: couldn't create {name} (duplicates exist?): {e}")

        # HNSW: graph index that works well on any amount of data, even when built on an empty table.
        # (The original used IVFFlat: `USING ivfflat (embedding OPS) WITH (lists = N)`. IVFFlat clusters
        #  vectors into N buckets when the index is BUILT, so on an empty/small table the buckets are
        #  meaningless and searches with few `probes` silently miss rows. Build it after loading data
        #  and tune with `SET LOCAL ivfflat.probes = k` if you need its lower memory use.)
        # Both index types cap `vector` at 2000 dimensions.
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table}_embedding
            ON {table} USING hnsw (embedding {VECTOR_OPS});
        """)


# -----------------------------------------------------------------------------
# DOCUMENT HELPERS
# -----------------------------------------------------------------------------
async def get_document_by_path(pool: asyncpg.Pool, path: str) -> Optional[dict]:
    table = _safe_table_name(CHUNKS_TABLE)
    q = f"SELECT DISTINCT ON (path) id, sha256 FROM {table} WHERE path = $1"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(q, path)
        return dict(row) if row else None


async def upsert_document_metadata(
    pool: asyncpg.Pool, *, path: str, filename: str, size_bytes: int, mtime_dt, sha256: str
) -> None:
    """Update document metadata on every chunk of a document."""
    table = _safe_table_name(CHUNKS_TABLE)
    q = f"""
    UPDATE {table}
    SET filename = $2, size_bytes = $3, mtime = $4, sha256 = $5, processed_at = now()
    WHERE path = $1
    """
    async with pool.acquire() as conn:
        await conn.execute(q, path, filename, size_bytes, mtime_dt, sha256)


# -----------------------------------------------------------------------------
# CHUNK HELPERS
# -----------------------------------------------------------------------------
async def delete_chunks_for_document(pool: asyncpg.Pool, path: str) -> None:
    table = _safe_table_name(CHUNKS_TABLE)
    async with pool.acquire() as conn:
        await conn.execute(f"DELETE FROM {table} WHERE path = $1", path)


async def insert_chunks(
    pool: asyncpg.Pool,
    path: str,
    filename: str,
    size_bytes: int,
    mtime_dt,
    sha256: str,
    rows: List[Tuple[int, str, List[float], str]],
) -> None:
    """Insert chunk rows idempotently, together with document metadata.
    rows: (chunk_index, content, embedding(list[float]), chunk_sha256)

    If the unique index on (path, chunk_sha256) couldn't be created (old duplicates), fall back to a
    NOT EXISTS guard instead of failing.
    """
    table = _safe_table_name(CHUNKS_TABLE)

    upsert_sql = f"""
        INSERT INTO {table} (path, filename, size_bytes, mtime, sha256, chunk_index, content, embedding, chunk_sha256)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector, $9)
        ON CONFLICT (path, chunk_sha256) WHERE chunk_sha256 IS NOT NULL DO NOTHING;
    """
    fallback_sql = f"""
        INSERT INTO {table} (path, filename, size_bytes, mtime, sha256, chunk_index, content, embedding, chunk_sha256)
        SELECT $1, $2, $3, $4, $5, $6, $7, $8::vector, $9
        WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE path = $1 AND chunk_sha256 = $9);
    """
    prepared = [
        (path, filename, size_bytes, mtime_dt, sha256, idx, txt, _to_pgvector(emb), chash)
        for (idx, txt, emb, chash) in rows
    ]

    async with pool.acquire() as conn:
        try:
            async with conn.transaction():  # all rows or none
                await conn.executemany(upsert_sql, prepared)
        except asyncpg.InvalidColumnReferenceError:
            # "no unique constraint matching the ON CONFLICT specification"
            async with conn.transaction():
                await conn.executemany(fallback_sql, prepared)


# -----------------------------------------------------------------------------
# VECTOR SEARCH
# -----------------------------------------------------------------------------
async def fetch_similar(
    pool: asyncpg.Pool, embedding: List[float], limit: int = 5
) -> List[Tuple[str, float]]:
    """Top-`limit` nearest chunks as (content, distance). Smaller distance = closer.
    (cosine distance is in [0, 2]; L2 is unbounded.)

    Tuning HNSW recall vs speed:  SET LOCAL hnsw.ef_search = 100
    -- `SET` can't take bind parameters; run it as its own statement with a literal int.
    """
    table = _safe_table_name(CHUNKS_TABLE)
    vec = _to_pgvector(embedding)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT content, (embedding {DISTANCE_OP} $1::vector) AS distance
            FROM {table}
            ORDER BY embedding {DISTANCE_OP} $1::vector   -- same operator as the index => index is used
            LIMIT $2
            """,
            vec, limit,
        )
    return [(r["content"], float(r["distance"])) for r in rows]


async def fetch_similar_simple(pool: asyncpg.Pool, embedding: List[float], limit: int = 5) -> List[str]:
    """Same search, text only (the 'context without an LLM' use case)."""
    return [content for content, _ in await fetch_similar(pool, embedding, limit)]


# -----------------------------------------------------------------------------
# HEALTH
# -----------------------------------------------------------------------------
async def ping(pool: asyncpg.Pool) -> bool:
    async with pool.acquire() as conn:
        return (await conn.fetchval("SELECT 1;")) == 1


# -----------------------------------------------------------------------------
# DEMO — tiny 3-D vectors instead of a real model so you can watch the maths:  python -m app.core.db
# -----------------------------------------------------------------------------
async def _demo() -> None:
    import datetime
    import hashlib

    global EMBED_DIM, CHUNKS_TABLE
    EMBED_DIM, CHUNKS_TABLE = 3, "demo_chunks"  # tiny vectors instead of a model
    pool = await get_pool()
    await init_db(pool)
    await delete_chunks_for_document(pool, "demo.txt")
    texts = [("cats purr", [1.0, 0.0, 0.0]), ("dogs bark", [0.0, 1.0, 0.0]), ("cats and dogs", [0.7, 0.7, 0.0])]
    rows = [(i, t, v, hashlib.sha256(t.encode()).hexdigest()) for i, (t, v) in enumerate(texts)]
    now = datetime.datetime.now(datetime.timezone.utc)
    await insert_chunks(pool, "demo.txt", "demo.txt", 0, now, "filehash", rows)
    for text, dist in await fetch_similar(pool, [1.0, 0.1, 0.0], limit=3):
        print(f"{dist:.4f}  {text}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(_demo())
