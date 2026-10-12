import asyncio
import os
import logging
import random
import sys
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_config
from common.db import get_pool, close_pool, init_pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AuraListener")

cfg = get_config()
api_id = cfg.telegram_api_id
api_hash = cfg.telegram_api_hash
session_string = cfg.telegram_session_string

# ANTI-DETECTION: Spoof a real Samsung Galaxy S24 running Telegram 10.14.5
# These strings match Telegram's official Android app over MTProto exactly.
client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash,
    device_model="Samsung Galaxy S24",
    system_version="Android 14",
    app_version="10.14.5",
    lang_code="en",
    system_lang_code="en-NG",
    catch_up=True
)

async def human_delay():
    """ANTI-DETECTION: A real person reacts to a notification in 0.5-4 seconds.
    We mirror this exactly before touching the database."""
    await asyncio.sleep(random.uniform(0.5, 4.0))

async def upsert_chat(conn, chat_id, title, username, is_supergroup):
    await conn.execute("""
        INSERT INTO chats (chat_id, title, username, is_supergroup)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id) DO UPDATE
        SET title = EXCLUDED.title, username = EXCLUDED.username, is_supergroup = EXCLUDED.is_supergroup
    """, chat_id, title, username, is_supergroup)

@client.on(events.NewMessage)
async def handler_new_message(event):
    text = event.raw_text
    if not text:
        return

    await human_delay()  # Human-speed reaction

    chat = await event.get_chat()
    chat_id = event.chat_id
    message_id = event.id
    sender_id = getattr(event, "sender_id", None)
    
    sender_display_name = None
    if event.sender:
        sender_display_name = getattr(event.sender, "first_name", "")
        last_name = getattr(event.sender, "last_name", "")
        if last_name:
            sender_display_name += f" {last_name}"
            
    title = getattr(chat, "title", "Private Chat")
    username = getattr(chat, "username", None)
    is_supergroup = getattr(chat, "megagroup", False) or getattr(chat, "broadcast", False)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await upsert_chat(conn, chat_id, title, username, is_supergroup)
        try:
            await conn.execute("""
                INSERT INTO raw_messages (chat_id, message_id, sender_id, sender_display_name, sent_at, reply_to_message_id, text)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (chat_id, message_id) DO NOTHING
            """, chat_id, message_id, sender_id, sender_display_name, event.date, event.reply_to_msg_id, text)
            logger.info(f"Ingested msg {message_id} from chat {chat_id}")
        except Exception as e:
            logger.error(f"DB insert error: {e}")

@client.on(events.MessageEdited)
async def handler_message_edited(event):
    await human_delay()

    chat_id = event.chat_id
    message_id = event.id
    new_text = event.raw_text

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, text FROM raw_messages WHERE chat_id = $1 AND message_id = $2",
            chat_id, message_id
        )
        if row:
            await conn.execute("INSERT INTO message_edits (message_row_id, previous_text) VALUES ($1, $2)", row["id"], row["text"])
            await conn.execute("UPDATE raw_messages SET text = $1, processed_at = NULL WHERE id = $2", new_text, row["id"])
            logger.info(f"Updated msg {message_id} in chat {chat_id}")

@client.on(events.MessageDeleted)
async def handler_message_deleted(event):
    chat_id = getattr(event, "chat_id", None)
    deleted_ids = getattr(event, "deleted_ids", [])
    if not chat_id or not deleted_ids:
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        for msg_id in deleted_ids:
            await conn.execute(
                "UPDATE raw_messages SET deleted_at = now() WHERE chat_id = $1 AND message_id = $2",
                chat_id, msg_id
            )
            logger.info(f"Marked msg {msg_id} deleted in chat {chat_id}")

async def main():
    logger.info("Starting Aura Listener (Hardened Human Mode)...")
    await init_pool()

    reconnect_attempt = 0
    while True:
        try:
            await client.start()
            logger.info("Connected. Listening for messages...")
            reconnect_attempt = 0
            await client.run_until_disconnected()

        except FloodWaitError as e:
            # ANTI-DETECTION: Telegram told us to back off. Obey with 20% buffer.
            # Official Telegram clients do exactly this. Ignoring it = instant ban.
            wait_time = int(e.seconds * 1.2)
            logger.warning(f"FloodWait: Telegram says {e.seconds}s. Waiting {wait_time}s...")
            await asyncio.sleep(wait_time)

        except (ConnectionError, OSError) as e:
            # ANTI-DETECTION: Exponential backoff with jitter on network drop.
            # A real phone on Lagos 4G drops connection and waits before retry.
            reconnect_attempt += 1
            base_wait = min(30 * (2 ** (reconnect_attempt - 1)), 300)  # Cap at 5 mins
            jitter = random.uniform(0, base_wait * 0.3)
            wait_time = base_wait + jitter
            logger.warning(f"Connection lost ({e}). Attempt {reconnect_attempt}. Waiting {wait_time:.0f}s...")
            await asyncio.sleep(wait_time)

        except Exception as e:
            logger.error(f"Unexpected error: {e}. Waiting 60-90s before retry...")
            await asyncio.sleep(60 + random.uniform(0, 30))

        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Listener stopped by user.")
