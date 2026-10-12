# 🏗️ Architectural Logs

This document traces the evolution of Project Aura's RAG (Retrieval-Augmented Generation) pipeline.

## V1: Naive Vector Architecture
- **Flow:** User Query -> Embedding -> `ORDER BY cosine_distance LIMIT 10` -> LLM
- **Flaws:** Extremely susceptible to "Semantic Literalness". If the user asked "What's going on?", the vector database surfaced other users asking "What's going on?" rather than actual announcements.

## V2: Agentic Intent Router
- **Flow:** User Query -> Gemini Intent Extraction -> Optimized Query & Chat Filter -> Vector Search -> LLM
- **Upgrades:** The bot now uses Gemini to extract the underlying intent (e.g., "announcements, plans") and the specific target chat (e.g., "tedx") *before* touching the database.

## V3: Conversational Memory
- **Upgrades:** The Python state now holds a rolling memory `user_memory` of the last 3 questions and answers. The bot no longer treats every message in a vacuum; it resolves pronouns and contextual follow-ups perfectly.

## V4: Time-Aware RAG
- **Flaws in V2:** Semantic Time-Blindness. Old messages mathematically outscored new messages.
- **Upgrades:** 
  1. Intent router extracts a `days_limit` integer.
  2. SQL dynamically injects `rm.sent_at >= NOW() - INTERVAL 'X days'`.
  3. Python re-ranks the top 30 semantic matches by `sent_at DESC` to ensure the absolute newest context is fed to the LLM.
  4. The live server clock is injected into the Gemini System Prompt.

## V5: Custom Hybrid Search (BM25 + Vector)
- **Upgrades:** Built a custom SQL scoring algorithm. 
- **Math:** `(1 - cosine_distance) + (CASE WHEN to_tsvector @@ plainto_tsquery THEN 0.15 ELSE 0.0)`.
- If a message matches the semantic meaning AND contains the exact literal keywords, it gets an artificial +15% boost, guaranteeing ruthless accuracy.

## V6: API Quota Protection (Local-Only Worker)
- **Upgrades:** Disabled the background worker's Gemini API dependency. The worker now relies strictly on local `all-MiniLM-L6-v2` vector math (threshold = 0.65). 100% of the API quota is now reserved for the Telegram Bot.

## V7: Premium UI/UX & Confidence Visualization
- **Upgrades:** The bot no longer returns clinical text blocks.
- **System Prompt:** Hardcoded to force double-line breaks between paragraphs and bullet points for maximum human readability.
- **Citation Logic:** Swapped raw `[source](url)` links for minimalist `[↗](url)` arrows placed seamlessly at the end of sentences.
- **Confidence Metric:** The Python backend intercepts the `sim` score `(1 - cosine_distance)` from PostgreSQL, converts it to a percentage, and visualizes it as an ASCII progress bar at the footer of every generation.
- **API Tracking:** The `/health` command dynamically computes the time delta to Midnight PT to track daily quota resets.
