import os
import aiofiles
import asyncpg
import openai
import pdfplumber
from typing import List

# ========== PARAMETERS ==========
DOCUMENTS_DIR = "backend/documents"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
OPENAI_MODEL = "text-embedding-ada-002"
DB_URL = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/dbname")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# ========== DB SETUP ==========
async def get_pool():
    return await asyncpg.create_pool(dsn=DB_URL)

async def init_db(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS openai_document_chunks (
                id SERIAL PRIMARY KEY,
                content TEXT,
                embedding VECTOR(1536)
            );
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_openai_document_chunks_embedding
            ON openai_document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

async def insert_chunk(pool, content, embedding):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO openai_document_chunks (content, embedding) VALUES ($1, $2)",
            content, embedding
        )

# ========== CHUNKING ==========
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    chunks = []
    i = 0
    length = len(text)
    while i < length:
        end = min(i + chunk_size, length)
        chunks.append(text[i:end])
        i += chunk_size - overlap if (chunk_size - overlap) > 0 else chunk_size
    return chunks

# ========== PDF/TXT LOADER ==========
async def load_text_file(path: str) -> str:
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        return await f.read()

def load_pdf_file(path: str) -> str:
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

# ========== EMBEDDING ==========
def get_embedding_openai(text: str, model: str = OPENAI_MODEL) -> List[float]:
    response = openai.embeddings.create(
        input=[text],
        model=model
    )
    return response.data[0].embedding

# ========== MAIN INGEST FUNCTION ==========
async def ingest_documents_with_openai():
    pool = await get_pool()
    await init_db(pool)
    for fname in os.listdir(DOCUMENTS_DIR):
        fpath = os.path.join(DOCUMENTS_DIR, fname)
        text = ""
        if fname.lower().endswith(".txt"):
            text = await load_text_file(fpath)
        elif fname.lower().endswith(".pdf"):
            text = load_pdf_file(fpath)
        else:
            continue  # Skip unsupported file types
        if not text.strip():
            print(f"Skipped {fname} (no extractable text).")
            continue
        chunks = chunk_text(text)
        for chunk in chunks:
            embedding = get_embedding_openai(chunk)
            await insert_chunk(pool, chunk, embedding)
        print(f"Processed {fname} ({len(chunks)} chunks)")
    await pool.close()

# ========== CLI USAGE ==========
if __name__ == "__main__":
    import asyncio
    asyncio.run(ingest_documents_with_openai())
