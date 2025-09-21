"""
Migration script to add caption_embedding columns to vision_rag_images and vision_rag_image_segments tables.
Run this once to update your schema.
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)
DB_DSN = os.getenv("DB_URL")
VECTOR_DIM = int(os.getenv("EMBED_DIM", "768"))

async def migrate():
    conn = await asyncpg.connect(dsn=DB_DSN)
    try:
        # Add caption_embedding to vision_rag_images
        await conn.execute(f"""
            ALTER TABLE vision_rag_images
            ADD COLUMN IF NOT EXISTS caption_embedding VECTOR({VECTOR_DIM});
        """)
        # Add caption_embedding to vision_rag_image_segments
        await conn.execute(f"""
            ALTER TABLE vision_rag_image_segments
            ADD COLUMN IF NOT EXISTS caption_embedding VECTOR({VECTOR_DIM});
        """)
        print("Migration completed: caption_embedding columns added.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
