# embedding_openai.py — a complete, minimal "OpenAI embeddings -> Postgres" pipeline, for learning.
#
#   read file -> split into overlapping chunks -> embed with OpenAI -> store in pgvector -> search
#
# The running app does this via app/embeddings/remote.py (OpenAIEmbedder) + app/ingestion/sync.py;
# this file keeps the whole flow in one readable place with its own table (openai_document_chunks).
#
# Run:  OPENAI_API_KEY=sk-... DATABASE_URL=postgresql://... python -m app.embeddings.embedding_openai [file-or-folder]   (from rag-be/)
# Needs: pip install openai asyncpg pypdf python-dotenv   (or: pip install -e ".[learning]")
import asyncio
import os
import sys
from pathlib import Path
from typing import Iterator, List

import asyncpg
from dotenv import load_dotenv
from openai import OpenAI

from ..core.db import _to_pgvector, get_pool  # shared pool + vector text format

# ====== LOAD ENV ======
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# "text-embedding-ada-002" (used before) is legacy; -3-small is cheaper/better and also 1536-dim,
# so the table definition below is unchanged.
OPENAI_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBED_DIM = 1536
DOCUMENTS_DIR = os.getenv("RAG_DATA_DIR", "../rag-data")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))       # characters per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))  # characters shared between neighbouring chunks
BATCH = 64                                             # chunks per API request

client = OpenAI(api_key=OPENAI_API_KEY)  # sync client is fine for ingestion scripts


# ====== DB SETUP ======
async def init_openai_db(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS openai_document_chunks (
                id SERIAL PRIMARY KEY,
                content TEXT,
                embedding VECTOR({EMBED_DIM})
            );
        """)
        # HNSW instead of the original IVFFlat: IVFFlat built on an empty table returns incomplete
        # results (see the note in app/core/db.py). The operator class must match the query operator (<=>).
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_openai_document_chunks_embedding
            ON openai_document_chunks USING hnsw (embedding vector_cosine_ops);
        """)


async def insert_chunk_openai(pool: asyncpg.Pool, content: str, embedding: List[float]) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO openai_document_chunks (content, embedding) VALUES ($1, $2::vector)",
            content, _to_pgvector(embedding),  # asyncpg can't send a raw Python list as `vector`
        )


# ====== 1. LOAD ======
def load_txt_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def load_pdf_file(path: str) -> str:
    from pypdf import PdfReader

    return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)


# ====== 2. CHUNK ======
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Sliding window. The overlap keeps a sentence that straddles a boundary retrievable from either
    side. (app/ingestion/chunker.py has a smarter splitter that respects paragraphs and sentences.)"""
    step = max(1, chunk_size - overlap)
    pieces = (text[i : i + chunk_size].strip() for i in range(0, len(text), step))
    return [p for p in pieces if p]


# ====== 3. OPENAI EMBEDDING ======
def get_embeddings_openai(texts: List[str], model: str = OPENAI_MODEL) -> List[List[float]]:
    """One request, many inputs (far fewer round trips than one call per chunk).
    Results carry an `index`; sort by it so the output order always matches the input order."""
    kwargs = {"dimensions": EMBED_DIM} if model.startswith("text-embedding-3") else {}  # pin the size the table expects
    response = client.embeddings.create(model=model, input=texts, **kwargs)
    return [d.embedding for d in sorted(response.data, key=lambda d: d.index)]


def get_embedding_openai(text: str, model: str = OPENAI_MODEL) -> List[float]:
    return get_embeddings_openai([text], model)[0]


# ====== PIPELINE FUNCTION FOR ONE FILE ======
def process_file_to_chunks_and_embeddings_openai(
    file_path: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> Iterator[tuple]:
    """Yields (chunk_text, embedding) pairs."""
    lower = file_path.lower()
    if lower.endswith((".txt", ".md")):
        text = load_txt_file(file_path)
    elif lower.endswith(".pdf"):
        text = load_pdf_file(file_path)
    else:
        raise ValueError("Unsupported file type")
    chunks = chunk_text(text, chunk_size, overlap)
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        yield from zip(batch, get_embeddings_openai(batch))


# ====== PIPELINE FUNCTION FOR ALL DOCS IN FOLDER ======
async def ingest_all_documents_openai(target: str = DOCUMENTS_DIR) -> None:
    root = Path(target)
    files = [root] if root.is_file() else sorted(
        p for p in root.rglob("*") if p.suffix.lower() in {".txt", ".md", ".pdf"}
    )
    pool = await get_pool()
    await init_openai_db(pool)
    # Simple version: wipe and reload, so running twice doesn't duplicate rows. (db.py shows the
    # smarter approach: hash each chunk/file and skip what is already stored.)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE openai_document_chunks")
    total = 0
    for path in files:
        print(f"Ingesting: {path.name}")
        for chunk, embedding in process_file_to_chunks_and_embeddings_openai(str(path)):
            await insert_chunk_openai(pool, chunk, embedding)
            total += 1
    print(f"Total OpenAI-embedded chunks added: {total}")
    await pool.close()


# ====== 4. FETCH SIMILAR CHUNKS FROM OPENAI TABLE ======
async def fetch_similar_openai(pool: asyncpg.Pool, embedding: List[float], limit: int = 5) -> List[str]:
    """Embed the question with the SAME model as the documents, then pass its vector here.
    `<=>` = cosine distance (the original used `<->`, L2, which doesn't match the cosine index)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT content FROM openai_document_chunks ORDER BY embedding <=> $1::vector LIMIT $2",
            _to_pgvector(embedding), limit,
        )
        return [r["content"] for r in rows]


# ====== CLI USAGE ======
if __name__ == "__main__":
    asyncio.run(ingest_all_documents_openai(sys.argv[1] if len(sys.argv) > 1 else DOCUMENTS_DIR))
