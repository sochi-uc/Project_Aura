# ⚡ Project Aura

**Project Aura** is an executive personal AI assistant and proactive intelligence pipeline for Telegram, built with a **loosely coupled, extensible architecture**. It continuously ingests conversations across your Telegram chats, stores and indexes them in PostgreSQL with `pgvector`, scores relevance against your custom interest taxonomy, produces scheduled morning digests, and provides an agentic conversational bot with hybrid retrieval (vector similarity + full-text search) and clickable message citations.

---

## 🏛️ Architecture Overview

```
                      ┌──────────────────────┐
                      │    Telegram Chats    │
                      └──────────┬───────────┘
                                 │ MTProto (Telethon)
                                 ▼
                      ┌──────────────────────┐
                      │  ingestion/listener  │
                      └──────────┬───────────┘
                                 │ Raw Messages
                                 ▼
               ┌────────────────────────────────────┐
               │  PostgreSQL (Database + pgvector)  │
               └─────────┬──────────────────────────┘
                         │
        ┌────────────────┼────────────────────────┐
        ▼                ▼                        ▼
┌──────────────┐  ┌──────────────┐       ┌─────────────────┐
│ worker/      │  │ digest/      │       │ bot/            │
│ process.py   │  │ generate.py  │       │ assistant_bot   │
└───────┬──────┘  └──────┬───────┘       └────────┬────────┘
        │                │                        │
        └────────────────┼────────────────────────┘
                         ▼
        ┌─────────────────────────────────────────┐
        │       Loosely Coupled Common Layer       │
        ├────────────────────┬────────────────────┤
        │  common/llm        │ common/embeddings  │
        │  • GeminiProvider  │ • SentenceTransf.  │
        │  • GroqProvider    │ • MockProvider     │
        │  • OpenAIProvider  │                    │
        │  • MockProvider    │                    │
        ├────────────────────┴────────────────────┤
        │  common/config (Typed, validated)      │
        │  common/db     (Asyncpg connection pool)│
        │  common/links  (Deep link generator)   │
        └─────────────────────────────────────────┘
```

### Components & Decoupled Layers
1. **Centralized Configuration (`common/config.py`)**:
   - Single source of truth for typed application settings.
   - Automatically parses and validates `.env` parameters without scattering raw `os.environ` calls.

2. **Pluggable LLM Interface (`common/llm.py`)**:
   - Provider-agnostic abstract base class `BaseLLMProvider`.
   - Out-of-the-box adapters:
     - `GeminiProvider`: Google Gemini (`gemini-3.6-flash`, etc.) with exponential backoff retry.
     - `GroqProvider`: High-speed Llama 3 models via Groq Cloud (`llama-3.3-70b-versatile`).
     - `OpenAICompatibleProvider`: Compatible with OpenAI, OpenRouter, Ollama, vLLM, and LocalAI.
     - `MockLLMProvider`: Instant deterministic responses for offline testing and CI.
   - Dynamic selection via `LLM_PROVIDER` in `.env`.

3. **Pluggable Embeddings Interface (`common/embeddings.py`)**:
   - Abstract base class `BaseEmbeddingProvider` decoupling callers from ML model dependencies.
   - `SentenceTransformerProvider`: Lazy-loaded local dense vector embeddings (`all-MiniLM-L6-v2`).
   - `MockEmbeddingProvider`: Fast zero-dependency mock embeddings for test suites.
   - Dynamic selection via `EMBEDDING_PROVIDER` in `.env`.

4. **Ingestion Layer (`ingestion/listener.py` & `ingestion/backfill.py`)**:
   - Connects to your Telegram account via Telethon MTProto.
   - Streams incoming messages into the PostgreSQL `raw_messages` table with anti-detection device spoofing and human response delays.
   - `backfill.py` enables retroactive historical synchronization.

5. **Relevance & Vector Pipeline (`worker/process.py` & `scripts/sync_interests.py`)**:
   - Computes dense embeddings and matches them against topic profiles from `config/interests.yaml`.
   - Auto-approves high-confidence matches and routes borderline candidates to the active LLM provider.

6. **Daily Digest (`digest/generate.py`)**:
   - Scheduled executive summary aggregated across active topics.
   - Dispatches a formatted morning digest directly to your Telegram DMs.

7. **Agentic RAG Assistant Bot (`bot/assistant_bot.py`)**:
   - Telegram bot interface providing instant retrieval over monitored chats.
   - Hybrid search (vector cosine similarity + PostgreSQL full-text search).
   - Generates long-form, time-aware analysis with sender attribution and deep links (`https://t.me/c/...`).

---

## 🛠️ Prerequisites

- **Python**: 3.11 or higher
- **PostgreSQL**: 15+ with the [`pgvector`](https://github.com/pgvector/pgvector) extension installed
- **Telegram Developer Credentials**: `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org)
- **Telegram Bot**: Created via [@BotFather](https://t.me/BotFather)
- **LLM API Key**: Google Gemini (default), Groq, or OpenAI / OpenAI-compatible endpoint

---

## 🚀 Quick Start Setup

### 1. Clone & Install

```bash
git clone https://github.com/<your-username>/Project_Aura.git
cd Project_Aura

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Configure Database

Ensure PostgreSQL is running and create the database:

```sql
CREATE DATABASE aura_db;
\c aura_db
CREATE EXTENSION IF NOT EXISTS vector;
```

Run schema initialization and migrations:

```bash
psql -d aura_db -f db/schema.sql
psql -d aura_db -f db/migrations/01_phase2.sql
psql -d aura_db -f db/migrations/02_indexes.sql
```

### 3. Configure Environment

Copy the template environment file:

```bash
cp .env.example .env
```

Edit `.env` to configure your credentials and desired providers:

```dotenv
# Telegram Credentials
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_STRING=your_session_string
ASSISTANT_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_USER_ID=your_numeric_user_id

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/aura_db

# LLM Provider: gemini | groq | openai | mock
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key

# Optional: Groq or OpenAI
GROQ_API_KEY=
OPENAI_API_KEY=
```

### 4. Generate Telegram User Session

```bash
python generate_session.py
```
Scan the displayed QR code with your Telegram mobile app (**Settings → Devices → Link Desktop Device**), and paste the session string into `TELEGRAM_SESSION_STRING` in `.env`.

### 5. Sync Interest Topics

Define your monitored topics in `config/interests.yaml` (see `config/interests.yaml.example`), then sync them:

```bash
python scripts/sync_interests.py
```

---

## 🏃 Running Services

### Manual Execution (Development)

```bash
# Terminal 1: Ingestion Listener
python ingestion/listener.py

# Terminal 2: Worker Pipeline
python worker/process.py

# Terminal 3: Assistant Bot
python bot/assistant_bot.py
```

### Production Execution (systemd)

Template systemd unit files are provided in `systemd/`:

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo cp systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now aura-listener.service
sudo systemctl enable --now aura-bot.service
sudo systemctl enable --now aura-worker.timer
sudo systemctl enable --now aura-digest.timer
```

---

## 🧪 Testing

Run the automated test suite to verify configuration, embedding adapters, and LLM providers:

```bash
python -m unittest discover tests
```

---

## 🩺 Diagnostics

Run the integrated system health diagnostic:

```bash
bash scripts/health.sh
```

---

## 🔒 Security & Privacy

- Strictly zero hardcoded secrets or environment credentials in version control.
- `TELEGRAM_USER_ID` authorization check enforces single-owner security for bot queries.
- Built-in anti-detection spoofing (Samsung S24 / Android 14 MTProto signature) with human reaction jitter.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
