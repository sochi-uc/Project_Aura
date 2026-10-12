# 🐛 Bug Fixing Logs

A forensic record of all major anomalies and their resolutions.

### Bug 1: Environment Variables Missing in DB Connection
- **Error:** `asyncpg.exceptions.InvalidAuthorizationSpecificationError: role "app_user" does not exist`
- **Cause:** `common/db.py` was not calling `load_dotenv()`. Standalone scripts defaulted to the system OS user instead of the `.env` database URL.
- **Fix:** Injected `from dotenv import load_dotenv; load_dotenv()` at the top of the file.

### Bug 2: Deprecated LLM Model
- **Error:** `HTTP/1.1 404 Not Found` from Gemini API.
- **Cause:** Codebase hardcoded `gemini-2.5-flash`, which Google disabled.
- **Fix:** Upgraded global parameters to `gemini-3.6-flash`.

### Bug 3: Background Loop Self-Matching
- **Error:** `pgrep` in deployment scripts kept matching itself, causing infinite loops.
- **Fix:** Modified bash scripts to use precise matching that excludes the `bash` process.

### Bug 4: Telegram Markdown Parse Crash
- **Error:** `Can't parse entities: can't find end of the entity starting at byte offset 156`
- **Cause:** Gemini generated unclosed markdown tags (e.g., a rogue `*`). Telegram API strictly rejected the entire message, crashing the bot.
- **Fix:** Wrapped the `edit_text` call in a `try/except`. If Markdown parsing fails, it gracefully falls back to sending the exact same text with `parse_mode=None` (Plain Text).

### Bug 5: Gemini API Quota Exhaustion (429)
- **Error:** `HTTP/1.1 429 Too Many Requests`
- **Cause:** The backfill dumped 24,000 messages. The background worker evaluated borderline vectors by asking Gemini, consuming the entire 1,500 Requests-Per-Day free tier limit while the user slept.
- **Fix:** Modified `worker/process.py` to bypass LLM borderline checks (`SIMILARITY_THRESHOLD_LOW = 0.65`). The worker is now 100% local, saving 100% of the API quota for the bot.

### Bug 6: Semantic Literalness (Bible Verse Anomaly)
- **Error:** Asking "where were all these mentioned" returned a random Bible verse instead of the previous TEDx context.
- **Cause:** Naive Vector Search is stateless. It searched for the literal phrase.
- **Fix:** Injected a rolling `user_memory` array into the python state to append the last 3 interactions to the intent extractor.

### Bug 7: Python Syntax Crash (Unterminated String Literal)
- **Error:** `SyntaxError: unterminated string literal (detected at line 202)`
- **Cause:** While injecting the customized 429 API Quota frontend warning, a literal newline character `\n` was accidentally inserted into a standard Python double-quoted string `""` instead of a triple-quoted string `"""`. This immediately crashed the `aura-bot.service` daemon on startup.
- **Fix:** Used a Python regex script to surgically replace the multi-line literal with escaped `\n` newline codes, successfully restoring the bot's runtime loop.
