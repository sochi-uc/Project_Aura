import os
import sys
import yaml
import asyncio
import logging
from sentence_transformers import SentenceTransformer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db import get_pool, close_pool, init_pool

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
        
    logger.info("Loading embedding model (CPU)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    await init_pool()
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        for t in topics:
            label = t["label"]
            desc = t["description"].strip()
            
            # Embed the description
            embedding = model.encode([desc])[0].tolist()
            embedding_str = f"[{','.join(map(str, embedding))}]"
            
            # Upsert into DB
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
