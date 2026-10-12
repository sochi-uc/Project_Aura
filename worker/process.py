import asyncio
import os
import sys
import logging
import json
import random
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db import get_pool, close_pool
from common.llm import call_gemini

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AuraWorker")

load_dotenv()

logger.info("Loading embedding model (this may take a moment)...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

BATCH_SIZE = 50
SIMILARITY_THRESHOLD_LOW = 0.65  # Send to LLM
SIMILARITY_THRESHOLD_HIGH = 0.65 # Auto-approve

async def evaluate_borderline_messages(conn, candidates):
    """
    Takes borderline candidates, batches them to Gemini to confirm relevance.
    candidates: list of dicts { 'msg_id', 'text', 'topic_id', 'topic_label' }
    """
    if not candidates:
        return

    # Group by topic for better LLM prompting
    topics_dict = {}
    for c in candidates:
        if c["topic_label"] not in topics_dict:
            topics_dict[c["topic_label"]] = []
        topics_dict[c["topic_label"]].append(c)

    for topic_label, msgs in topics_dict.items():
        prompt = f"You are evaluating if messages are relevant to the topic: '{topic_label}'.\n\n"
        for m in msgs:
            prompt += f"<message id=\"{m['msg_id']}\">{m['text']}</message>\n"
            
        prompt += """
Respond in pure JSON with this exact schema:
{
  "results": [
    {"id": "<message_id>", "relevant": true/false, "reason": "1 line reason"}
  ]
}
"""
        try:
            logger.info(f"Asking Gemini about {len(msgs)} messages for topic '{topic_label}'...")
            res_text = await call_gemini(prompt, is_json=True, max_tokens=4096)
            data = json.loads(res_text)
            
            for item in data.get("results", []):
                msg_id = int(item["id"])
                relevant = bool(item["relevant"])
                reason = item.get("reason", "")
                
                # Update DB
                # Find the candidate matching this msg_id
                cand = next((c for c in msgs if c["msg_id"] == msg_id), None)
                if cand:
                    await conn.execute("""
                        INSERT INTO message_relevance (message_row_id, topic_id, similarity, llm_confirmed, llm_reason)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (message_row_id, topic_id) DO UPDATE 
                        SET llm_confirmed = EXCLUDED.llm_confirmed, llm_reason = EXCLUDED.llm_reason
                    """, msg_id, cand["topic_id"], cand["similarity"], relevant, reason)
                    
        except Exception as e:
            logger.error(f"Failed LLM eval for topic '{topic_label}': {e}")


async def process_batch(pool):
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(f"""
                SELECT id, text 
                FROM raw_messages 
                WHERE processed_at IS NULL 
                  AND processing_started_at IS NULL 
                  AND deleted_at IS NULL
                  AND text != ''
                ORDER BY sent_at ASC 
                FOR UPDATE SKIP LOCKED 
                LIMIT {BATCH_SIZE}
            """)
            
            if not rows:
                return 0
                
            row_ids = [r['id'] for r in rows]
            await conn.execute("UPDATE raw_messages SET processing_started_at = now() WHERE id = ANY($1)", row_ids)
            
    logger.info(f"Processing batch of {len(rows)} messages...")
    
    candidates_for_llm = []
    
    async with pool.acquire() as conn:
        topics = await conn.fetch("SELECT id, label, embedding FROM interest_topics WHERE active = TRUE")
        
        for row in rows:
            msg_id = row["id"]
            text = row["text"]
            
            embedding = embedding_model.encode([text])[0].tolist()
            embedding_str = f"[{','.join(map(str, embedding))}]"
            
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO message_embeddings (message_row_id, embedding)
                    VALUES ($1, $2::vector)
                    ON CONFLICT (message_row_id) DO UPDATE SET embedding = EXCLUDED.embedding
                """, msg_id, embedding_str)
                
                # Check pgvector cosine similarity vs topics directly in SQL!
                sim_rows = await conn.fetch("""
                    SELECT id, label, 1 - (embedding <=> $1::vector) as similarity
                    FROM interest_topics
                    WHERE active = TRUE
                """, embedding_str)
                
                for sr in sim_rows:
                    sim = sr["similarity"]
                    topic_id = sr["id"]
                    
                    if sim >= SIMILARITY_THRESHOLD_HIGH:
                        # Auto-approve!
                        await conn.execute("""
                            INSERT INTO message_relevance (message_row_id, topic_id, similarity, llm_confirmed, llm_reason)
                            VALUES ($1, $2, $3, TRUE, 'Auto-approved due to high vector similarity')
                            ON CONFLICT DO NOTHING
                        """, msg_id, topic_id, sim)
                    elif sim >= SIMILARITY_THRESHOLD_LOW:
                        # Borderline - Needs LLM
                        candidates_for_llm.append({
                            "msg_id": msg_id,
                            "text": text,
                            "topic_id": topic_id,
                            "topic_label": sr["label"],
                            "similarity": sim
                        })
                
                await conn.execute("UPDATE raw_messages SET processed_at = now() WHERE id = $1", msg_id)
                
    # Run LLM batch check for candidates
    async with pool.acquire() as conn:
        await evaluate_borderline_messages(conn, candidates_for_llm)
                
    return len(rows)

async def main():
    pool = await get_pool()
    total = 0
    for _ in range(10):
        count = await process_batch(pool)
        if count == 0:
            logger.info("Queue empty. Worker exiting.")
            break
        total += count
    
    logger.info(f"Total processed this run: {total}")
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
