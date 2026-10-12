import logging
from typing import Optional
import asyncpg

from common.config import get_config

logger = logging.getLogger("AuraDB")

_pool: Optional[asyncpg.Pool] = None


async def init_pool(min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """
    Initializes the shared asyncpg connection pool using centralized configuration.
    """
    global _pool
    if _pool is None:
        cfg = get_config()
        db_url = cfg.database_url
        if not db_url:
            raise ValueError("DATABASE_URL is not configured in environment or settings.")
        logger.debug("Initializing asyncpg connection pool...")
        _pool = await asyncpg.create_pool(
            db_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=60,
        )
    return _pool


async def get_pool() -> asyncpg.Pool:
    """
    Returns the active database pool, initializing it if necessary.
    """
    if _pool is None:
        await init_pool()
    return _pool


async def close_pool():
    """
    Closes all pool connections cleanly.
    """
    global _pool
    if _pool is not None:
        logger.debug("Closing asyncpg connection pool...")
        await _pool.close()
        _pool = None
