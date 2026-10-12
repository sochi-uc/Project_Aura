import os
import sys
import yaml
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db import get_pool, close_pool, init_pool
from common.embeddings import get_embedding_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SyncInterests")


async def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "interests.yaml")
    logger.info(f"Loading {config_path}...")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    topics = config.get("topics", [])
    if not topics:
        logger.warning("No topics found in config.")
        return

    embedder = get_embedding_provider()
    logger.info(f"Using embedding provider: {embedder.__class__.__name__}")

    await init_pool()
    pool = await get_pool()

    async with pool.acquire() as conn:
        for t in topics:
            label = t["label"]
            desc = t["description"].strip()

            embedding = embedder.get_embedding(desc)
            embedding_str = embedder.to_vector_sql(embedding)

            await conn.execute("""
                INSERT INTO interest_topics (label, description, embedding)
                VALUES ($1, $2, $3::vector)
                ON CONFLICT (label) DO UPDATE 
                SET description = EXCLUDED.description, embedding = EXCLUDED.embedding, active = TRUE
            """, label, desc, embedding_str)
            logger.info(f"Synced topic: {label}")

    await close_pool()
    logger.info("Sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
