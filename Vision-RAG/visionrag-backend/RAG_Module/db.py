# app/db.py
import os
import json
import asyncio
import asyncpg
from typing import Any, Dict, List, Optional

# ---- Configuration ----
DB_DSN = os.getenv("DB_URL")  # e.g. postgresql://user:pass@host/db?sslmode=require
VECTOR_DIM = int(os.getenv("EMBED_DIM", "768"))  # Gemini text-embedding-004 = 768
IVF_LISTS = int(os.getenv("IVF_LISTS", "100"))   # tweak after you have data
IVF_PROBES = int(os.getenv("IVF_PROBES", "10"))  # query-time probes
STATEMENT_TIMEOUT_MS = int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "15000"))

_pool: Optional[asyncpg.Pool] = None


# ---- Pool lifecycle ----
async def init_pool() -> asyncpg.Pool:
    """
    Create a global asyncpg pool. Call this once at app startup.
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DB_DSN,
            min_size=1,
            max_size=10,
            command_timeout=STATEMENT_TIMEOUT_MS / 1000,
            init=_pool_init_connection,
        )
    return _pool


async def _pool_init_connection(conn: asyncpg.Connection):
    """
    Runs for every new physical connection in the pool.
    Set safe defaults and statement timeout.
    """
    await conn.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")
    # (Optional) tune search_path if you use dedicated schemas
    # await conn.execute("SET search_path TO public")


async def close_pool():
    """
    Gracefully close the pool at app shutdown.
    """
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized. Call init_pool() at startup.")
    return _pool


# ---- Schema / Index init ----
async def init_db():
    """
    Create pgvector extension, tables, and ANN indexes if missing.
    Safe to call multiple times.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS text_chunks (
                id BIGSERIAL PRIMARY KEY,
                doc_id TEXT,
                text   TEXT,
                embedding VECTOR({VECTOR_DIM}),
                meta JSONB
            );
            """)

            await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS images (
                id BIGSERIAL PRIMARY KEY,
                image_id TEXT,
                uri TEXT,
                embedding VECTOR({VECTOR_DIM}),
                meta JSONB
            );
            """)

            await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS image_segments (
                id BIGSERIAL PRIMARY KEY,
                image_id TEXT,
                bbox FLOAT8[],     -- [x1,y1,x2,y2]
                caption TEXT,
                embedding VECTOR({VECTOR_DIM}),
                meta JSONB
            );
            """)

            # IVFFlat indexes (create after some rows exist for best clustering)
            await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS text_chunks_ivf
              ON text_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
            """)
            await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS images_ivf
              ON images USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
            """)
            await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS segments_ivf
              ON image_segments USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
            """)


# ---- Helpers ----
def _as_json(meta: Optional[Dict[str, Any]]) -> str:
    return json.dumps(meta or {})


# NOTE on pgvector binding:
# Passing a Python list[float] and casting with ::vector in SQL works:
#   ... VALUES ($1, $2::vector, ...)
# We also use it in ORDER BY embedding <-> $1::vector for kNN.


# ---- Inserts ----
async def insert_text_chunk(doc_id: str, text: str, embedding: List[float], meta: Optional[Dict[str, Any]] = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO text_chunks (doc_id, text, embedding, meta)
            VALUES ($1, $2, $3::vector, $4::jsonb)
            """,
            doc_id, text, embedding, _as_json(meta)
        )


async def insert_image(image_id: str, uri: str, embedding: List[float], meta: Optional[Dict[str, Any]] = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO images (image_id, uri, embedding, meta)
            VALUES ($1, $2, $3::vector, $4::jsonb)
            """,
            image_id, uri, embedding, _as_json(meta)
        )


async def insert_image_segment(
    image_id: str,
    bbox: List[float],
    caption: str,
    embedding: List[float],
    meta: Optional[Dict[str, Any]] = None
):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO image_segments (image_id, bbox, caption, embedding, meta)
            VALUES ($1, $2, $3, $4::vector, $5::jsonb)
            """,
            image_id, bbox, caption, embedding, _as_json(meta)
        )


# ---- k-NN Search ----
async def set_ivf_probes(conn: asyncpg.Connection, probes: int = IVF_PROBES):
    # In pgvector ≥0.5.1 this is usually: SET ivfflat.probes = N;
    await conn.execute(f"SET ivfflat.probes = {int(probes)}")


async def query_knn(
    table: str,
    embedding: List[float],
    k: int = 10,
    extra_cols: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Return top-k nearest neighbors from a table.
    - table ∈ {'text_chunks','images','image_segments'}
    - distance op: <-> (L2)
    """
    pool = get_pool()
    extra_cols = extra_cols or []
    # choose display column
    display_col = "caption" if table == "image_segments" else ("text" if table == "text_chunks" else "uri")
    cols = ["id", display_col + " AS content", "1 / (1 + embedding <-> $1::vector) AS score"] + extra_cols
    col_sql = ", ".join(cols)

    async with pool.acquire() as conn:
        async with conn.transaction():
            await set_ivf_probes(conn, IVF_PROBES)
            rows = await conn.fetch(
                f"""
                SELECT {col_sql}
                FROM {table}
                ORDER BY embedding <-> $1::vector
                LIMIT {k}
                """,
                embedding
            )
    # Convert to plain dicts
    return [dict(r) for r in rows]


# ---- Example bootstrap (optional) ----
async def _demo():
    await init_pool()
    await init_db()

    # insert one example
    emb = [0.0] * VECTOR_DIM
    emb[0] = 0.123
    await insert_text_chunk("doc-1", "A chair near a lamp", emb, {"source": "demo"})

    # query it back
    res = await query_knn("text_chunks", emb, k=3)
    print("Top hits:", res)

    await close_pool()


if __name__ == "__main__":
    asyncio.run(_demo())
