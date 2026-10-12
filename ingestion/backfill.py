"""
ingestion/backfill.py — Historical Dialogue & Message Synchronization

Design Rationale:
- Bootstrapping Knowledge: When Project Aura is installed on a new machine or database,
  listening only to new real-time messages leaves an empty knowledge base.
- Rate-Limited Historical Pagination: This utility iterates the top 40 most active
  dialogs and syncs up to 1,000 historical messages per chat, ensuring ample conversational
  history for RAG retrieval without exceeding MTProto pagination limits.
"""

import asyncio
import os
import sys
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

# Ensure repository root is on sys.path for direct script execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_config
from common.db import get_pool, close_pool, init_pool
from ingestion.listener import upsert_chat

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Backfill")

cfg = get_config()
api_id = cfg.telegram_api_id
api_hash = cfg.telegram_api_hash
session_string = cfg.telegram_session_string

client = TelegramClient(StringSession(session_string), api_id, api_hash)


async def main():
    """
    Connects to Telegram MTProto and synchronizes historical messages from recent chats.
    """
    await init_pool()
    pool = await get_pool()
    await client.start()

    logger.info("Fetching recent dialogs for historical backfill...")
    async with pool.acquire() as conn:
        # Limit to 40 most recently active chats to avoid MTProto rate-limiting
        dialogs = await client.get_dialogs(limit=40)
        for dialog in dialogs:
            chat = dialog.entity
            chat_id = dialog.id
            title = getattr(chat, "title", getattr(chat, "first_name", "Private Chat"))
            username = getattr(chat, "username", None)
            is_supergroup = getattr(chat, "megagroup", False) or getattr(chat, "broadcast", False)

            await upsert_chat(conn, chat_id, title, username, is_supergroup)
            logger.info(f"Backfilling up to 1,000 messages for: {title}")

            count = 0
            try:
                # Page backwards through historical messages
                async for event in client.iter_messages(chat_id, limit=1000):
                    text = event.raw_text
                    if not text:
                        continue

                    message_id = event.id
                    sender_id = getattr(event, "sender_id", None)
                    sender_display_name = None
                    if event.sender:
                        sender_display_name = getattr(event.sender, "first_name", "")
                        last_name = getattr(event.sender, "last_name", "")
                        if last_name:
                            sender_display_name += f" {last_name}"

                    # Idempotent insert: Skip if already present
                    await conn.execute("""
                        INSERT INTO raw_messages (chat_id, message_id, sender_id, sender_display_name, sent_at, reply_to_message_id, text)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (chat_id, message_id) DO NOTHING
                    """, chat_id, message_id, sender_id, sender_display_name, event.date, event.reply_to_msg_id, text)
                    count += 1

                logger.info(f"Backfill complete for '{title}': {count} messages synchronized.")

            except FloodWaitError as e:
                logger.warning(f"FloodWait hit while backfilling '{title}'. Sleeping {e.seconds}s...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Error while backfilling '{title}': {e}")

    await client.disconnect()
    await close_pool()
    logger.info("All selected dialogs backfilled successfully.")


if __name__ == "__main__":
    asyncio.run(main())
