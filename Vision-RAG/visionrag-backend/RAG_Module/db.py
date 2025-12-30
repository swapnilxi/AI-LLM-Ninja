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
# Try to read DB config from settings (preferred) with env fallbacks
try:
    from ..config.config import get_settings
    _settings = get_settings()
    db_conf = getattr(_settings, "db", None)
    if db_conf:
        DB_DSN = os.getenv("DB_URL") or db_conf.dsn
        VECTOR_DIM = int(os.getenv("EMBED_DIM", str(db_conf.embed_dim)))
        IVF_LISTS = int(os.getenv("IVF_LISTS", str(db_conf.ivf_lists)))
        IVF_PROBES = int(os.getenv("IVF_PROBES", str(db_conf.ivf_probes)))
        STATEMENT_TIMEOUT_MS = int(os.getenv("PG_STATEMENT_TIMEOUT_MS", str(db_conf.statement_timeout_ms)))
    else:
        VECTOR_DIM = int(os.getenv("EMBED_DIM", "768"))  # Gemini gemini-embedding-001 = 768
        IVF_LISTS = int(os.getenv("IVF_LISTS", "100"))   # tweak after you have data
        IVF_PROBES = int(os.getenv("IVF_PROBES", "10"))  # query-time probes
        STATEMENT_TIMEOUT_MS = int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "15000"))
except Exception:
    # If config import fails, fall back to environment variables
    VECTOR_DIM = int(os.getenv("EMBED_DIM", "768"))  # Gemini gemini-embedding-001 = 768
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
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                except Exception as e:
                    print("Error creating extension:", e)
                    raise

                try:
                    await conn.execute(f"""
                        CREATE TABLE IF NOT EXISTS vision_rag_text_chunks (
                            id BIGSERIAL PRIMARY KEY,
                            doc_id TEXT,
                            text   TEXT,
                            embedding VECTOR({VECTOR_DIM}),
                            meta JSONB
                        );
                    """)
                except Exception as e:
                    print("Error creating vision_rag_text_chunks table:", e)
                    raise

                try:
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
                    
                    # Add image_data and mime_type columns if they don't exist (migration)
                    try:
                        await conn.execute("""
                            ALTER TABLE vision_rag_images 
                            ADD COLUMN IF NOT EXISTS image_data BYTEA;
                        """)
                        await conn.execute("""
                            ALTER TABLE vision_rag_images 
                            ADD COLUMN IF NOT EXISTS mime_type TEXT;
                        """)
                        print("Successfully added/verified image_data and mime_type columns")
                    except Exception as col_err:
                        print(f"Warning adding columns (may already exist): {col_err}")
                        
                except Exception as e:
                    print("Error creating vision_rag_images table:", e)
                    raise

                try:
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
                except Exception as e:
                    print("Error creating vision_rag_image_segments table:", e)
                    raise

                # IVFFlat indexes (create after some rows exist for best clustering)
                try:
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS vision_rag_text_chunks_ivf
                        ON vision_rag_text_chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
                    """)
                except Exception as e:
                    print("Error creating vision_rag_text_chunks_ivf index:", e)
                    raise
                try:
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS vision_rag_images_ivf
                        ON vision_rag_images USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
                    """)
                except Exception as e:
                    print("Error creating vision_rag_images_ivf index:", e)
                    raise
                try:
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS vision_rag_segments_ivf
                        ON vision_rag_image_segments USING ivfflat (embedding vector_l2_ops) WITH (lists = {IVF_LISTS});
                    """)
                except Exception as e:
                    print("Error creating vision_rag_segments_ivf index:", e)
                    raise
    except Exception as e:
        print("init_db failed:", e)
        raise


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


async def image_exists_by_uri(uri: str) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM vision_rag_images WHERE uri = $1 LIMIT 1", uri)
        return row is not None


async def insert_image(image_id: str, uri: str, embedding: List[float], meta: Optional[Dict[str, Any]] = None, image_data: Optional[bytes] = None, mime_type: Optional[str] = None):
    if await image_exists_by_uri(uri):
        print(f"Image with uri '{uri}' already exists. Skipping insert.")
        return
    caption_embedding = None
    if meta and "caption_embedding" in meta:
        caption_embedding = meta["caption_embedding"]
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO vision_rag_images (image_id, uri, embedding, meta, caption_embedding, image_data, mime_type)
            VALUES ($1, $2, $3::vector, $4::jsonb, $5::vector, $6, $7)
            """,
            image_id, uri, _format_vector(embedding), _as_json(meta), _format_vector(caption_embedding) if caption_embedding else None, image_data, mime_type
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


# -----------------------------------------------------------------------------
# Synchronous class wrapper for legacy code that expects a DatabaseConnection
# -----------------------------------------------------------------------------
class DatabaseConnection:
    """Synchronous wrapper around the async DB helpers.

    Provides simple blocking methods so modules that expect a class
    instance (like the gesture demo) can call into the DB without
    managing asyncio themselves.
    """

    def __init__(self, init_schema: bool = False):
        # Prevent unsafe use inside a running event loop (e.g. FastAPI).
        # The synchronous wrapper uses `asyncio.run()` and is only safe
        # in simple scripts that are not already running an event loop.
        if asyncio.get_event_loop().is_running():
            raise RuntimeError(
                "Synchronous DatabaseConnection cannot be created inside a running event loop. "
                "Use AsyncDatabase in async applications (e.g. FastAPI)."
            )

        # Ensure pool initialized on creation (blocking)
        asyncio.run(init_pool())

        if init_schema:
            asyncio.run(init_db())

    def close(self) -> None:
        """Close the underlying connection pool."""
        try:
            asyncio.run(close_pool())
        except RuntimeError:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_until_complete(close_pool())

    def search_by_embedding(self, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Search images by vector embedding (blocking).

        Returns list of dicts similar to query_knn output.
        """
        return asyncio.run(query_knn("vision_rag_images", embedding, k=limit, extra_cols=["image_id", "uri", "meta"]))

    def search_text_chunks(self, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        return asyncio.run(query_knn("vision_rag_text_chunks", embedding, k=limit, extra_cols=["doc_id", "meta"]))

    def search_segments(self, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        return asyncio.run(query_knn("vision_rag_image_segments", embedding, k=limit, extra_cols=["image_id", "bbox", "meta"]))

    def get_image_by_id(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Return single image row by primary id."""
        async def _get():
            pool = get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM vision_rag_images WHERE id = $1 LIMIT 1", image_id)
                return dict(row) if row else None
        return asyncio.run(_get())

    def search_by_object(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Simple text-based search over `meta` JSON for object names.

        This is a lightweight fallback used by the demo. For production,
        replace with a dedicated object-index lookup.
        """
        async def _search():
            pool = get_pool()
            async with pool.acquire() as conn:
                # naive full-text-ish search in meta JSON
                rows = await conn.fetch(
                    "SELECT id, image_id, uri, meta FROM vision_rag_images WHERE meta::text ILIKE $1 LIMIT $2",
                    f"%{query}%",
                    limit,
                )
                return [dict(r) for r in rows]
        return asyncio.run(_search())


class AsyncDatabase:
    """Asynchronous Database helper class for async applications (FastAPI, etc.).

    Use this class inside async frameworks. It provides async lifecycle
    methods and async query methods that delegate to the existing
    module-level async helpers.
    """

    def __init__(self):
        self._initted = False

    async def init(self, init_schema: bool = False) -> None:
        """Initialize connection pool and optionally the schema."""
        await init_pool()
        if init_schema:
            await init_db()
        self._initted = True

    async def close(self) -> None:
        """Close the underlying pool."""
        await close_pool()
        self._initted = False

    async def search_by_embedding(self, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        return await query_knn("vision_rag_images", embedding, k=limit, extra_cols=["image_id", "uri", "meta"])

    async def search_text_chunks(self, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        return await query_knn("vision_rag_text_chunks", embedding, k=limit, extra_cols=["doc_id", "meta"])

    async def search_segments(self, embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        return await query_knn("vision_rag_image_segments", embedding, k=limit, extra_cols=["image_id", "bbox", "meta"])

    async def get_image_by_id(self, image_id: int) -> Optional[Dict[str, Any]]:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM vision_rag_images WHERE id = $1 LIMIT 1", image_id)
            return dict(row) if row else None

    async def search_by_object(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, image_id, uri, meta FROM vision_rag_images WHERE meta::text ILIKE $1 LIMIT $2",
                f"%{query}%",
                limit,
            )
            return [dict(r) for r in rows]

