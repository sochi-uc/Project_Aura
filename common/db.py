"""
common/db.py — Asynchronous PostgreSQL Connection Pool Management

Design Rationale:
- Connection Pooling: Creating a new TCP/TLS connection to PostgreSQL per message
  is prohibitively expensive (10-30ms per handshake). Using `asyncpg.create_pool`
  amortizes connection overhead across concurrent worker and listener tasks.
- Guardrails: Configured with `command_timeout=60` to ensure long-running or locked
  queries are aborted before consuming all available pool workers.
"""

import logging
from typing import Optional
import asyncpg

from common.config import get_config

logger = logging.getLogger("AuraDB")

# Module-level pool reference maintained across the async event loop
_pool: Optional[asyncpg.Pool] = None


async def init_pool(min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """
    Initializes the shared asyncpg connection pool using centralized configuration.
    
    Args:
        min_size: Minimum idle connections maintained in the pool.
        max_size: Upper limit of simultaneous database connections.
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
    Returns the active database pool, lazily initializing it if not yet created.
    """
    if _pool is None:
        await init_pool()
    return _pool


async def close_pool():
    """
    Gracefully shuts down the connection pool and terminates open client connections.
    Should be called during service shutdown or at the end of oneshot batch runs.
    """
    global _pool
    if _pool is not None:
        logger.debug("Closing asyncpg connection pool...")
        await _pool.close()
        _pool = None
