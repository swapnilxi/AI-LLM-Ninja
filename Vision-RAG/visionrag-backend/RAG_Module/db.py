# app/db.py
import os
import json
import asyncio
import asyncpg
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)

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


# ---- Health check ----
async def check_db_connection() -> bool:
    """
    Check if the database connection is active.
    """
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            # Execute a simple query to check the connection
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False


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
                CREATE TABLE IF NOT EXISTS vision_rag_text_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    doc_id TEXT,
                    text   TEXT,
                    embedding VECTOR({VECTOR_DIM}),
                    meta JSONB
                );
            """)

            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS vision_rag_images (
                    id BIGSERIAL PRIMARY KEY,
                    image_id TEXT,
                    uri TEXT,
                    embedding VECTOR({VECTOR_DIM}),
                    meta JSONB,
                    caption_embedding VECTOR({VECTOR_DIM})
                );
            """)

            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS vision_rag_image_segments (
                    id BIGSERIAL PRIMARY KEY,
                    image_id TEXT,
                    bbox FLOAT8[],     -- [x1,y1,x2,y2]
                    caption TEXT,
                    embedding VECTOR({VECTOR_DIM}),
                    meta JSONB,
                    caption_embedding VECTOR({VECTOR_DIM})
                );
            """)

            # IVFFlat indexes (create after some rows exist for best clustering)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS vision_rag_text_chunks_ivf
                ON vision_rag_text_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS vision_rag_images_ivf
                ON vision_rag_images USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS vision_rag_segments_ivf
                ON vision_rag_image_segments USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
            """)


# ---- Helpers ----
def _as_json(meta: Optional[Dict[str, Any]]) -> str:
    return json.dumps(meta or {})


def _format_vector(v: List[float]) -> str:
    """Format a list of floats into a string that pgvector can parse."""
    return "[" + ",".join(map(str, v)) + "]"



# ---- Inserts ----
async def insert_text_chunk(doc_id: str, text: str, embedding: List[float], meta: Optional[Dict[str, Any]] = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO vision_rag_text_chunks (doc_id, text, embedding, meta)
            VALUES ($1, $2, $3::vector, $4::jsonb)
            """,
            doc_id, text, _format_vector(embedding), _as_json(meta)
        )


async def insert_image(image_id: str, uri: str, embedding: List[float], meta: Optional[Dict[str, Any]] = None):
    caption_embedding = None
    if meta and "caption_embedding" in meta:
        caption_embedding = meta["caption_embedding"]
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO vision_rag_images (image_id, uri, embedding, meta, caption_embedding)
            VALUES ($1, $2, $3::vector, $4::jsonb, $5::vector)
            """,
            image_id, uri, _format_vector(embedding), _as_json(meta), _format_vector(caption_embedding) if caption_embedding else None
        )


async def insert_image_segment(
    image_id: str,
    bbox: List[float],
    caption: str,
    embedding: List[float],
    meta: Optional[Dict[str, Any]] = None
):
    caption_embedding = None
    if meta and "caption_embedding" in meta:
        caption_embedding = meta["caption_embedding"]
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO vision_rag_image_segments (image_id, bbox, caption, embedding, meta, caption_embedding)
            VALUES ($1, $2, $3, $4::vector, $5::jsonb, $6::vector)
            """,
            image_id, bbox, caption, _format_vector(embedding), _as_json(meta), _format_vector(caption_embedding) if caption_embedding else None
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
    - table ∈ {'vision_rag_text_chunks','vision_rag_images','vision_rag_image_segments'}
    - distance op: <-> (L2)
    """
    pool = get_pool()
    extra_cols = extra_cols or []
    # choose display column
    display_col = "caption" if table == "vision_rag_image_segments" else ("text" if table == "vision_rag_text_chunks" else "uri")
    cols = ["id", display_col + " AS content", "1.0 / (1.0 + (embedding <-> $1::vector)) AS score"] + extra_cols
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
                _format_vector(embedding),
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
    res = await query_knn("vision_rag_text_chunks", emb, k=3)
    print("Top hits:", res)

    await close_pool()


if __name__ == "__main__":
    asyncio.run(_demo())
