# db_check.py
import asyncio
import sys
sys.path.append('..')
from RAG_Module.db import init_pool, close_pool  # uses your existing init_pool() and close_pool()

async def main():
    pool = await init_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchval("SELECT version()")
        one = await conn.fetchval("SELECT 1")
    print("✅ Connected to Postgres")
    print("   version:", v)
    print("   select 1:", one)
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
