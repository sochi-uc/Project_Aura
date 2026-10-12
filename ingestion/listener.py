"""
ingestion/listener.py — MTProto Ingestion Listener with Anti-Detection Hardening

Design Rationale:
- Telethon MTProto Client Fingerprinting:
  Automated Telegram user accounts frequently trigger security flags if they identify
  themselves with standard script signatures (e.g. Telethon's default "PC 64bit").
  We emulate a legitimate consumer Android device ("Samsung Galaxy S24", Android 14)
  to ensure session headers mirror official mobile application traffic.
- Human Jitter Emulation:
  Real humans take between 0.5 and 4.0 seconds to react to incoming notifications.
  Introducing random micro-delays before database ingestion decouples event timing
  from programmatic machine speed.
- Comprehensive Lifecycle Syncing:
  - New Messages: Streamed into `raw_messages`.
  - Edits: Captured in `message_edits` audit table, triggering worker re-processing.
  - Deletions: Flagged via `deleted_at = now()` to maintain privacy and compliance.
"""

import asyncio
import os
import logging
import random
import sys
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

# Ensure repository root is on sys.path for direct script execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_config
from common.db import get_pool, close_pool, init_pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AuraListener")

# Centralized configuration
cfg = get_config()
api_id = cfg.telegram_api_id
api_hash = cfg.telegram_api_hash
session_string = cfg.telegram_session_string

# ── ANTI-DETECTION DEVICE SPOOFING ──────────────────────────────────────────
# Emulating a real smartphone running an official release build of Telegram.
# This prevents Telegram's heuristics from flagging the session as an automated scraper.
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
    """
    Simulates human reaction time (0.5 to 4.0 seconds) before performing actions.
    Helps smooth out bursty traffic and avoid behavioral anomaly detection.
    """
    await asyncio.sleep(random.uniform(0.5, 4.0))


async def upsert_chat(conn, chat_id, title, username, is_supergroup):
    """Maintains an up-to-date registry of monitored chats in the chats table."""
    await conn.execute("""
        INSERT INTO chats (chat_id, title, username, is_supergroup)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id) DO UPDATE
        SET title = EXCLUDED.title, username = EXCLUDED.username, is_supergroup = EXCLUDED.is_supergroup
    """, chat_id, title, username, is_supergroup)


@client.on(events.NewMessage)
async def handler_new_message(event):
    """
    Streams incoming messages into the raw_messages table for subsequent vectorization.
    """
    text = event.raw_text
    if not text:
        # Ignore media-only messages without captions
        return

    await human_delay()

    chat = await event.get_chat()
    chat_id = event.chat_id
    message_id = event.id
    sender_id = getattr(event, "sender_id", None)

    # Format human-readable sender display name
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
            # ON CONFLICT DO NOTHING ensures idempotency if duplicate events fire
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
    """
    Tracks message edits: logs previous text into message_edits audit log
    and resets processed_at = NULL so the worker recalculates embeddings.
    """
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
            # Archive previous text version
            await conn.execute("INSERT INTO message_edits (message_row_id, previous_text) VALUES ($1, $2)", row["id"], row["text"])
            # Update current content and re-queue for embedding update
            await conn.execute("UPDATE raw_messages SET text = $1, processed_at = NULL WHERE id = $2", new_text, row["id"])
            logger.info(f"Updated msg {message_id} in chat {chat_id}")


@client.on(events.MessageDeleted)
async def handler_message_deleted(event):
    """
    Handles message deletion events: marks rows with deleted_at timestamp
    so deleted items are excluded from future search retrieval.
    """
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
    """
    Main listener lifecycle loop with exponential backoff on network dropouts.
    """
    logger.info("Starting Aura Listener (Hardened Human Mode)...")
    await init_pool()

    reconnect_attempt = 0
    while True:
        try:
            await client.start()
            logger.info("Connected to Telegram MTProto. Listening for incoming events...")
            reconnect_attempt = 0
            await client.run_until_disconnected()

        except FloodWaitError as e:
            # Obey Telegram's rate limiter with an extra 20% safety margin.
            # Bypassing or ignoring FloodWait is the #1 cause of account suspensions.
            wait_time = int(e.seconds * 1.2)
            logger.warning(f"FloodWait encountered: Telegram requested {e.seconds}s. Sleeping for {wait_time}s...")
            await asyncio.sleep(wait_time)

        except (ConnectionError, OSError) as e:
            # Exponential backoff with random jitter for network dropouts
            reconnect_attempt += 1
            base_wait = min(30 * (2 ** (reconnect_attempt - 1)), 300)  # Capped at 5 minutes
            jitter = random.uniform(0, base_wait * 0.3)
            wait_time = base_wait + jitter
            logger.warning(f"Connection lost ({e}). Attempt {reconnect_attempt}. Reconnecting in {wait_time:.0f}s...")
            await asyncio.sleep(wait_time)

        except Exception as e:
            logger.error(f"Unexpected listener exception: {e}. Cooling down for 60-90s...")
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
        logger.info("Listener stopped cleanly by user.")
