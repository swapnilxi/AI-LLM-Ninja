import asyncpg
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

DB_URL = os.getenv("DATABASE_URL")

async def get_pool():
    return await asyncpg.create_pool(dsn=DB_URL)

async def init_db(pool):
    async with pool.acquire() as conn:
        # Enable pgvector extension if not already enabled
        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;
        """)
        # Create document_chunks table if it doesn't exist
        #1536 if openAI and 1024 if thenlper/gte-large from HF
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY,
                content TEXT,
                embedding VECTOR(1024)

            );
        """)
        # (Optional) You can also check if table has expected schema, but this covers most use cases.
        
        # 3. Ensure the vector index exists (for fast ANN search)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
            ON document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

async def insert_chunk(pool, content, embedding):
    # Convert list of floats to string in Postgres vector format
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO document_chunks (content, embedding) VALUES ($1, $2::vector)",
            content, embedding_str
        )




# without llm
async def fetch_similar(pool, embedding, limit=5):
    # Convert list to Postgres vector string
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT content FROM document_chunks ORDER BY embedding <-> $1::vector LIMIT $2",
            embedding_str, limit
        )
        return [r["content"] for r in rows]