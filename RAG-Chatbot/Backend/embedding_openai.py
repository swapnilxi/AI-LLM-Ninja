import os
import openai
import asyncpg
from dotenv import load_dotenv
from utils import DOCUMENTS_DIR, chunk_text, load_txt_file, load_pdf_file

# ====== LOAD ENV ======
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "text-embedding-ada-002"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

openai.api_key = OPENAI_API_KEY

# ====== DB SETUP ======
async def get_pool():
    return await asyncpg.create_pool(dsn=DB_URL)

async def init_openai_db(pool):
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

async def insert_chunk_openai(pool, content, embedding):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO openai_document_chunks (content, embedding) VALUES ($1, $2)",
            content, embedding
        )

# ====== OPENAI EMBEDDING ======
def get_embedding_openai(text: str, model: str = OPENAI_MODEL):
    # OpenAI's API is synchronous
    response = openai.embeddings.create(
        input=[text],
        model=model
    )
    return response.data[0].embedding

# ====== PIPELINE FUNCTION FOR ONE FILE ======
def process_file_to_chunks_and_embeddings_openai(
    file_path: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
):
    if file_path.lower().endswith(".txt"):
        text = load_txt_file(file_path)
    elif file_path.lower().endswith(".pdf"):
        text = load_pdf_file(file_path)
    else:
        raise ValueError("Unsupported file type")
    chunks = chunk_text(text, chunk_size, overlap)
    embeddings = [get_embedding_openai(chunk) for chunk in chunks]
    return zip(chunks, embeddings)

# ====== PIPELINE FUNCTION FOR ALL DOCS IN FOLDER ======
async def ingest_all_documents_openai():
    pool = await get_pool()
    await init_openai_db(pool)
    files = [os.path.join(DOCUMENTS_DIR, fname) for fname in os.listdir(DOCUMENTS_DIR)
             if fname.lower().endswith((".txt", ".pdf"))]
    total = 0
    for path in files:
        print(f"Ingesting: {os.path.basename(path)}")
        for chunk, embedding in process_file_to_chunks_and_embeddings_openai(path):
            await insert_chunk_openai(pool, chunk, embedding)
            total += 1
    print(f"Total OpenAI-embedded chunks added: {total}")
    await pool.close()

# ====== OPTIONAL: FETCH SIMILAR CHUNKS FROM OPENAI TABLE ======
async def fetch_similar_openai(pool, embedding, limit=5):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT content FROM openai_document_chunks ORDER BY embedding <-> $1 LIMIT $2",
            embedding, limit
        )
        return [r["content"] for r in rows]

# ====== CLI USAGE ======
if __name__ == "__main__":
    import asyncio
    asyncio.run(ingest_all_documents_openai())
