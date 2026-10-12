import asyncio
import os
import sys
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.db import get_pool, close_pool, init_pool
from ingestion.listener import upsert_chat

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Backfill")
load_dotenv()

api_id = int(os.environ["TELEGRAM_API_ID"])
api_hash = os.environ["TELEGRAM_API_HASH"]
session_string = os.environ["TELEGRAM_SESSION_STRING"]

client = TelegramClient(StringSession(session_string), api_id, api_hash)

async def main():
    await init_pool()
    pool = await get_pool()
    await client.start()
    
    logger.info("Fetching dialogs for backfill...")
    async with pool.acquire() as conn:
        dialogs = await client.get_dialogs(limit=40) # Get top 40 most recently active chats
        for dialog in dialogs:
            chat = dialog.entity
            chat_id = dialog.id
            title = getattr(chat, "title", getattr(chat, "first_name", "Private Chat"))
            username = getattr(chat, "username", None)
            is_supergroup = getattr(chat, "megagroup", False) or getattr(chat, "broadcast", False)
            
            await upsert_chat(conn, chat_id, title, username, is_supergroup)
            logger.info(f"Backfilling up to 1000 msgs for: {title}")
            
            count = 0
            try:
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
                            
                    await conn.execute("""
                        INSERT INTO raw_messages (chat_id, message_id, sender_id, sender_display_name, sent_at, reply_to_message_id, text)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (chat_id, message_id) DO NOTHING
                    """, chat_id, message_id, sender_id, sender_display_name, event.date, getattr(event, "reply_to_msg_id", None), text)
                    count += 1
                logger.info(f"-> Inserted {count} messages.")
            except FloodWaitError as e:
                logger.warning(f"Rate limited! Waiting {e.seconds}s...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Error on {title}: {e}")
                
    await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
