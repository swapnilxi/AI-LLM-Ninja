# db.py — uses only "document_chunks" table for all document information
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
EMBED_DIM = int(os.getenv("EMBED_DIM", "1024"))            # gte-large = 1024
VECTOR_METRIC = os.getenv("VECTOR_METRIC", "cosine").lower()
IVFFLAT_LISTS = int(os.getenv("IVFFLAT_LISTS", "100"))
CHUNKS_TABLE = os.getenv("CHUNKS_TABLE", "document_chunks")  # keep old name by default

if VECTOR_METRIC not in ("cosine", "l2"):
    raise ValueError("VECTOR_METRIC must be 'cosine' or 'l2'")
VECTOR_OPS = "vector_cosine_ops" if VECTOR_METRIC == "cosine" else "vector_l2_ops"


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def _safe_table_name(name: str) -> str:
    """Allow only a safe identifier for the table name (defense-in-depth)."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Invalid table name")
    return name

def _to_pgvector(embedding: List[float]) -> str:
    """Render a Python list[float] as a Postgres vector literal."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


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
    """
    Ensures extensions exist and that 'document_chunks' has the columns + ANN index we need.
    - Will NOT crash the app if unique index creation fails due to duplicates.
    """
    table = _safe_table_name(CHUNKS_TABLE)

    async with pool.acquire() as conn:
        # Extensions we rely on
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # digest(), gen_random_uuid()


        # Ensure the chunks table exists with all necessary columns
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id SERIAL PRIMARY KEY,
                content TEXT,
                embedding VECTOR({EMBED_DIM}),
                path TEXT NOT NULL,
                filename TEXT NOT NULL,
                size_bytes BIGINT NOT NULL,
                mtime TIMESTAMPTZ NOT NULL,
                sha256 TEXT NOT NULL,
                processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                chunk_index int NOT NULL DEFAULT 0,
                chunk_sha256 text
            );
        """)

        # Columns required for dedupe (no data loss)
        # Ensure 'path' column exists (fixes index creation errors)
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS path TEXT NOT NULL DEFAULT '';")
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS chunk_index int NOT NULL DEFAULT 0;")
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS chunk_sha256 text;")

        # Backfill per-chunk hash for existing rows (skip NULL content)
        await conn.execute(f"""
            UPDATE {table}
            SET chunk_sha256 = encode(digest(content, 'sha256'), 'hex')
            WHERE chunk_sha256 IS NULL AND content IS NOT NULL;
        """)

        # Create unique indexes IF POSSIBLE — don't crash if duplicates exist
        # (You can run the one-time cleanup SQL I shared earlier to remove duplicates,
        # then restart to get these uniques in place.)
        try:
            await conn.execute(f"""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_{table}_doc_idx
                ON {table}(path, chunk_index);
            """)
        except asyncpg.PostgresError as e:
            print(f"[init_db] WARN: couldn't create uq_{table}_doc_idx (duplicates exist?): {e}")

        try:
            await conn.execute(f"""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_{table}_doc_hash
                ON {table}(path, chunk_sha256)
                WHERE chunk_sha256 IS NOT NULL;
            """)
        except asyncpg.PostgresError as e:
            print(f"[init_db] WARN: couldn't create uq_{table}_doc_hash (duplicates exist?): {e}")

        # ANN index for fast vector search
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table}_embedding
            ON {table}
            USING ivfflat (embedding {VECTOR_OPS})
            WITH (lists = {IVFFLAT_LISTS});
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
    pool: asyncpg.Pool,
    *,
    path: str,
    filename: str,
    size_bytes: int,
    mtime_dt,
    sha256: str,
) -> None:
    """
    Update document metadata for all chunks of a document.
    """
    table = _safe_table_name(CHUNKS_TABLE)
    q = f"""
    UPDATE {table}
    SET path = $1, filename = $2, size_bytes = $3, mtime = $4, sha256 = $5, processed_at = now()
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
) -> int:
    """
    Insert chunk rows idempotently with document metadata.
    rows: (chunk_index, content, embedding(list[float]), chunk_sha256)

    If the unique index on (path, chunk_sha256) isn't present yet,
    we fall back to a NOT EXISTS guard to avoid crashing.
    """
    table = _safe_table_name(CHUNKS_TABLE)

    upsert_sql = f"""
        INSERT INTO {table} (path, filename, size_bytes, mtime, sha256, chunk_index, content, embedding, chunk_sha256)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector, $9)
        ON CONFLICT (path, chunk_sha256) DO NOTHING;
    """

    fallback_sql = f"""
        INSERT INTO {table} (path, filename, size_bytes, mtime, sha256, chunk_index, content, embedding, chunk_sha256)
        SELECT $1, $2, $3, $4, $5, $6, $7, $8::vector, $9
        WHERE NOT EXISTS (
            SELECT 1 FROM {table}
            WHERE path = $1 AND chunk_sha256 = $9
        );
    """

    prepared = [
        (path, filename, size_bytes, mtime_dt, sha256, idx, txt, _to_pgvector(emb), chash)
        for (idx, txt, emb, chash) in rows
    ]

    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                await conn.executemany(upsert_sql, prepared)
            except Exception:
                # Likely "there is no unique or exclusion constraint matching the ON CONFLICT"
                await conn.executemany(fallback_sql, prepared)

    # executemany returns None; return 0 to keep the signature stable
    return 0


# -----------------------------------------------------------------------------
# VECTOR SEARCH (FIXES `$1` ERROR)
# -----------------------------------------------------------------------------
async def fetch_similar(
    pool: asyncpg.Pool, embedding: List[float], limit: int = 5, probes: int = 10
) -> List[Tuple[str, float]]:
    """
    Return (content, distance) for top-K nearest chunks.

    IMPORTANT:
    - `SET LOCAL` cannot use bind parameters and cannot be combined with SELECT
      as a single prepared statement. We run it separately with a literal int.
    """
    table = _safe_table_name(CHUNKS_TABLE)
    vec = _to_pgvector(embedding)

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Run as a separate statement; no bind params here.
            await conn.execute(f"SET LOCAL ivfflat.probes = {int(probes)}")

            rows = await conn.fetch(
                f"""
                SELECT content, (embedding <-> $1::vector) AS distance
                FROM {table}
                ORDER BY embedding <-> $1::vector
                LIMIT $2
                """,
                vec, limit
            )

    # Smaller distance = closer (cosine distance in [0,2]; L2 unbounded)
    return [(r["content"], float(r["distance"])) for r in rows]


# -----------------------------------------------------------------------------
# HEALTH
# -----------------------------------------------------------------------------
async def ping(pool: asyncpg.Pool) -> bool:
    async with pool.acquire() as conn:
        return (await conn.fetchval("SELECT 1;")) == 1



# without llm
async def fetch_similar_simple(pool, embedding, limit=5):
    table = _safe_table_name(CHUNKS_TABLE)
    # Convert list to Postgres vector string
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT content FROM {table} ORDER BY embedding <-> $1::vector LIMIT $2",
            embedding_str, limit
        )
        return [r["content"] for r in rows]