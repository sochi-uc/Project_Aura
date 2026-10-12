"""
scripts/sync_interests.py — Synchronize User Interest Taxonomy to pgvector

Design Rationale:
- Declarative Taxonomy: Topics and descriptions are authored in YAML (`config/interests.yaml`)
  allowing non-programmers to define their focus areas (work projects, hobbies, committees).
- Vector Pre-Computation: Rather than re-computing topic embeddings on every message evaluation,
  we pre-compute dense embeddings for each topic description and persist them into the
  `interest_topics` table in PostgreSQL.
- Idempotent Upserts: When topic descriptions are edited in YAML, re-running this script
  updates the database record in-place without breaking foreign keys in `message_relevance`.
"""

import os
import sys
import yaml
import asyncio
import logging

# Ensure repository root is on sys.path for direct script execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db import get_pool, close_pool, init_pool
from common.embeddings import get_embedding_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SyncInterests")


async def main():
    """
    Reads config/interests.yaml, generates dense embeddings for each topic description,
    and performs an idempotent UPSERT into the interest_topics table.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "interests.yaml")
    logger.info(f"Loading interest configuration from {config_path}...")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    topics = config.get("topics", [])
    if not topics:
        logger.warning("No topics declared in configuration file.")
        return

    # Use the decoupled embedding provider (default: SentenceTransformer)
    embedder = get_embedding_provider()
    logger.info(f"Using embedding provider: {embedder.__class__.__name__}")

    await init_pool()
    pool = await get_pool()

    async with pool.acquire() as conn:
        for t in topics:
            label = t["label"]
            desc = t["description"].strip()

            # Generate embedding vector and format for pgvector literal
            embedding = embedder.get_embedding(desc)
            embedding_str = embedder.to_vector_sql(embedding)

            # Idempotent upsert: Update description and embedding if label already exists
            await conn.execute("""
                INSERT INTO interest_topics (label, description, embedding)
                VALUES ($1, $2, $3::vector)
                ON CONFLICT (label) DO UPDATE 
                SET description = EXCLUDED.description, embedding = EXCLUDED.embedding, active = TRUE
            """, label, desc, embedding_str)
            logger.info(f"Synced topic: '{label}'")

    await close_pool()
    logger.info("Interest taxonomy synchronization complete.")


if __name__ == "__main__":
    asyncio.run(main())
