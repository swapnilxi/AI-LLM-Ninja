"""
Migration script to add image_data and mime_type columns to vision_rag_images table.

This allows storing actual image bytes in the database for serving directly,
without requiring filesystem access.

Run this script once to update your existing database schema:
    python -m RAG_Module.migrate_add_image_data
"""

import asyncio
from .db import get_pool, init_pool


async def migrate():
    """Add image_data and mime_type columns to vision_rag_images table."""
    await init_pool()
    pool = get_pool()
    
    async with pool.acquire() as conn:
        try:
            print("Checking if image_data column exists...")
            # Check if column already exists
            check = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name='vision_rag_images' 
                AND column_name='image_data'
            """)
            
            if check > 0:
                print("✓ image_data column already exists")
            else:
                print("Adding image_data column...")
                await conn.execute("""
                    ALTER TABLE vision_rag_images
                    ADD COLUMN IF NOT EXISTS image_data BYTEA
                """)
                print("✓ Added image_data column")
            
            # Check mime_type column
            check = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name='vision_rag_images' 
                AND column_name='mime_type'
            """)
            
            if check > 0:
                print("✓ mime_type column already exists")
            else:
                print("Adding mime_type column...")
                await conn.execute("""
                    ALTER TABLE vision_rag_images
                    ADD COLUMN IF NOT EXISTS mime_type TEXT
                """)
                print("✓ Added mime_type column")
            
            print("\n✅ Migration completed successfully!")
            print("\nNext steps:")
            print("1. New images uploaded via /image-gemini or /image-local will automatically store bytes in DB")
            print("2. To backfill existing images, you'll need to re-ingest them or write a custom script")
            print("3. The /image endpoint will now serve from DB when image_id doesn't exist on filesystem")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(migrate())
