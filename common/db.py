from dotenv import load_dotenv
load_dotenv()

import os
import asyncpg

_pool = None

async def init_pool():
    global _pool
    if _pool is None:
        db_url = os.environ.get('DATABASE_URL')
        _pool = await asyncpg.create_pool(db_url)
    return _pool

async def get_pool():
    if _pool is None:
        await init_pool()
    return _pool

async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
