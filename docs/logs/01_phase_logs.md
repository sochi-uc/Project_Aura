# 📁 Phase Logs

This document tracks the high-level phases of Project Aura's development from inception to its current highly-advanced state.

## Phase 1: Windows Prototyping
- Initial proof of concept built on a Windows environment.
- Basic Telethon listener configured.
- Simple `sentence-transformers` vectorization.
- Hardcoded to `gemini-2.5-flash`.

## Phase 2: Linux Production Deployment
- Migrated codebase to Linux production environment.
- Handled PostgreSQL role migrations and `pgvector` extension setup.
- Containerized the ecosystem into four robust `systemd` services:
  - `aura-listener.service`
  - `aura-bot.service`
  - `aura-worker.timer`
  - `aura-digest.timer`

## Phase 3: Historical Backfill
- Discovered that Telethon's `catch_up=True` only listens for missed live messages, lacking historical depth.
- Engineered `backfill.py` to recursively iterate through the top 40 chats and download the last 1,000 messages per chat.
- Successfully dumped ~24,000 historical messages into the `raw_messages` table for deep foundational knowledge.

## Phase 4: Agentic RAG & Pipeline Hardening
- Transitioned from a "Naive RAG" bot to an "Agentic AI".
- Swapped out the basic semantic search for an LLM Intent Router.
- Implemented Conversational Memory.
- Implemented Frontend UI/UX styling.

## Phase 5: Time-Aware & Hybrid Retrieval
- Integrated temporal boundaries to solve Semantic Time-Blindness.
- Combined exact-keyword matching (PostgreSQL Full-Text Search) with Semantic Vector matching (pgvector) to create a custom Hybrid Search scoring algorithm.

## Phase 6: UX Refinement & Quota Hardening
- Rebuilt the bot's front-end logic to enforce an "Apple-style" premium UX (generous whitespace, concise bullet points, minimalist emoji links).
- Implemented a dynamic "Memory Match" confidence bar `[████████░░]` calculated directly from pgvector's cosine distance.
- Integrated a live timezone calculator (`zoneinfo`) into the `/health` command to display a real-time countdown clock to the Google Gemini API Quota reset (Midnight Pacific Time).
