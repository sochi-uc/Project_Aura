# 🔄 Pipeline Logs

This document maps the exact data flow of Project Aura.

## 1. Ingestion Pipeline (`listener.py`)
- Authenticates with Telegram via MTProto (`Telethon`).
- Listens to incoming messages, edits, and deletions in real-time.
- Inserts raw text into the PostgreSQL `raw_messages` table with `processed_at = NULL`.

## 2. Processing Pipeline (`worker/process.py`)
- Triggered by `aura-worker.timer` every 20 minutes.
- Selects up to 500 unprocessed messages.
- Generates 384-dimensional embeddings locally using `sentence-transformers` (`all-MiniLM-L6-v2`).
- Compares embeddings against the user's `interest_topics`.
- If `cosine_similarity >= 0.65`, the message is flagged as highly relevant and inserted into `message_relevance`.

## 3. Retrieval Pipeline (`bot/assistant_bot.py`)
- Authenticates via `python-telegram-bot`.
- Extracts user intent, target chat, and temporal boundaries.
- Executes the Hybrid Search (Vector + Full-Text) against the database.
- Calculates a "Memory Match" percentage for the UI.
- Generates a beautifully formatted, double-spaced Apple-style response via Gemini 3.6 Flash.
