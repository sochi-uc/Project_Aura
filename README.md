# ⚡ Project Aura

**Project Aura** is an executive personal AI assistant and proactive intelligence pipeline for Telegram. It continuously ingests conversations across your Telegram chats, stores and indexes them in PostgreSQL with `pgvector`, scores relevance against your custom interest taxonomy, produces daily morning digests, and provides an agentic conversational bot with hybrid retrieval (vector similarity + full-text search) and direct message citations.

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
│              │  │              │       │                 │
│ • Embeddings │  │ • Daily AI   │       │ • Agentic RAG   │
│ • Relevance  │  │   Executive  │       │ • Hybrid Search │
│ • Topic Tag  │  │   Digest     │       │ • Citations     │
└──────────────┘  └──────────────┘       └─────────────────┘
```

### Components
1. **Ingestion Layer (`ingestion/listener.py` & `ingestion/backfill.py`)**:
   - Connects to your Telegram account via Telethon MTProto.
   - Automatically monitors active private and group chats, streaming incoming messages directly into the PostgreSQL `raw_messages` table.
   - `backfill.py` enables retroactive historical synchronization of existing chats.

2. **Relevance & Vector Pipeline (`worker/process.py` & `scripts/sync_interests.py`)**:
   - Generates 384-dimensional dense semantic embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
   - Compares incoming messages against topic embeddings stored from `config/interests.yaml`.
   - Uses dual similarity thresholds (auto-approve vs. LLM judgment) to flag high-priority discussions.

3. **Daily Digest (`digest/generate.py`)**:
   - Runs on a scheduled timer (or cron) to aggregate top unread matches.
   - Synthesizes an executive summary through Google Gemini.
   - Dispatches a formatted morning digest directly to your Telegram DMs.

4. **Agentic RAG Assistant Bot (`bot/assistant_bot.py`)**:
   - Telegram bot interface providing instant retrieval over all monitored conversations.
   - Employs hybrid search (pgvector cosine similarity + PostgreSQL full-text search).
   - Generates conversational responses with sender attribution, quotes, confidence scores, and deep links (`https://t.me/c/...`).

---

## 🛠️ Prerequisites

- **Python**: 3.11 or higher
- **PostgreSQL**: 15+ with the [`pgvector`](https://github.com/pgvector/pgvector) extension installed
- **Telegram Developer Credentials**: `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org)
- **Telegram Bot**: Created via [@BotFather](https://t.me/BotFather)
- **Google Gemini API Key**: From [Google AI Studio](https://aistudio.google.com/)

---

## 🚀 Quick Start Setup

### 1. Clone & Virtual Environment

```bash
git clone https://github.com/<your-username>/Project_Aura.git
cd Project_Aura

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Database

Ensure PostgreSQL is running and create the database:

```sql
CREATE DATABASE tg_assistant;
\c tg_assistant
CREATE EXTENSION IF NOT EXISTS vector;
```

Run schema initialization and migrations:

```bash
psql -d tg_assistant -f db/schema.sql
psql -d tg_assistant -f db/migrations/01_phase2.sql
psql -d tg_assistant -f db/migrations/02_indexes.sql
```

### 3. Environment Configuration

Copy the template environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```dotenv
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_SESSION_STRING=your_session_string
ASSISTANT_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_USER_ID=your_numeric_user_id
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql://postgres:password@localhost:5432/tg_assistant
```

### 4. Generate Telegram User Session

To allow the listener to authenticate without prompting for SMS codes on headless servers:

```bash
python generate_session.py
```
Scan the displayed QR code with your Telegram mobile app (**Settings → Devices → Link Desktop Device**), and paste the resulting session string into `TELEGRAM_SESSION_STRING` in your `.env`.

### 5. Initialize Interest Topics

Define your monitored topics in `config/interests.yaml` (see `config/interests.yaml.example` as a reference), then sync their embeddings into the database:

```bash
python scripts/sync_interests.py
```

---

## 🏃 Running Services

### Manual Execution (Development)

```bash
# Terminal 1: Ingestion Listener
python ingestion/listener.py

# Terminal 2: Worker (Process batch)
python worker/process.py

# Terminal 3: Assistant Bot
python bot/assistant_bot.py
```

### Production Execution (systemd)

Template service files are provided in `systemd/`:

1. Copy the unit files into `/etc/systemd/system/` (or `~/.config/systemd/user/` for user-level systemd):
   ```bash
   sudo cp systemd/*.service /etc/systemd/system/
   sudo cp systemd/*.timer /etc/systemd/system/
   ```

2. Edit the service files to update `User=YOUR_USER` and `WorkingDirectory=/path/to/Project_Aura`.

3. Reload and enable:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now aura-listener.service
   sudo systemctl enable --now aura-bot.service
   sudo systemctl enable --now aura-worker.timer
   sudo systemctl enable --now aura-digest.timer
   ```

---

## 🩺 Health Diagnostic

A comprehensive diagnostic script is included to check service states and database statistics:

```bash
bash scripts/health.sh
```

---

## 🔒 Security & Privacy

- Never commit `.env` or any `*.session` files to version control.
- `TELEGRAM_USER_ID` acts as an authorization guardrail: only messages from this ID will trigger bot actions.
- Anti-detection user-agent and device strings are built into the MTProto client to prevent unauthorized session flagging.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
