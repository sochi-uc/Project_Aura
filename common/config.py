"""
common/config.py — Centralized Configuration & Environment Management

Design Philosophy:
- Single Source of Truth: Rather than having individual scripts read raw `os.environ`
  values with scattered fallbacks, all configuration parameters are strongly typed
  and centralized in this module.
- Immutability: The `AppConfig` class is a frozen dataclass to ensure runtime settings
  cannot be accidentally mutated by concurrent asynchronous coroutines.
- Robust Path Resolution: Systemd services and cron timers frequently execute with
  varied working directories. We anchor the `.env` lookup relative to the project root
  rather than trusting `os.getcwd()`.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

logger = logging.getLogger("AuraConfig")

# Always anchor the .env path to the project root directory.
# This prevents elusive "missing key" bugs when services are triggered by systemd or cron.
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_base_dir, ".env")
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """
    Immutable application settings container.
    Field defaults reflect sensible production baselines while allowing
    declarative overrides via environment variables.
    """

    # ── Database Layer ──────────────────────────────────────────────────────────
    # Default connection string targets local PostgreSQL with pgvector extension.
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/aura_db")
    )

    # ── LLM Inference Layer ─────────────────────────────────────────────────────
    # Active provider selection ('gemini', 'groq', 'openai', or 'mock').
    # Allows switching between cloud-hosted and self-hosted inference without code changes.
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini").lower()
    )

    # Google Gemini settings (default high-context reasoning engine)
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    )

    # Groq settings (ultra-fast inference, ideal for high-throughput batch evaluation)
    groq_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY")
    )
    groq_model: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    )

    # Generic OpenAI-compatible settings (works with Ollama, vLLM, OpenRouter, or OpenAI)
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    openai_api_base: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

    # ── Dense Vector Embeddings ─────────────────────────────────────────────────
    # Provider used for generating dense semantic representations of messages and topics.
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").lower()
    )
    # Defaulting to 384-dimensional all-MiniLM-L6-v2: provides an optimal balance
    # between CPU inference speed and retrieval quality on standard server hardware.
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )

    # ── Telegram MTProto & Bot Credentials ──────────────────────────────────────
    # MTProto User API credentials from https://my.telegram.org
    telegram_api_id: Optional[int] = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_API_ID")) if os.getenv("TELEGRAM_API_ID") else None
    )
    telegram_api_hash: Optional[str] = field(
        default_factory=lambda: os.getenv("TELEGRAM_API_HASH")
    )

    # Telethon StringSession: allows headless server operation without interactive SMS prompts
    telegram_session_string: Optional[str] = field(
        default_factory=lambda: os.getenv("TELEGRAM_SESSION_STRING")
    )

    # Telegram Bot Token for conversational interface & digest delivery
    assistant_bot_token: Optional[str] = field(
        default_factory=lambda: os.getenv("ASSISTANT_BOT_TOKEN")
    )

    # Crucial security guardrail: only interactions originating from this numeric
    # Telegram user ID are processed. Prevents unauthorized queries to the assistant.
    telegram_user_id: Optional[int] = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_USER_ID")) if os.getenv("TELEGRAM_USER_ID") else None
    )

    # ── Processing Pipeline Parameters ──────────────────────────────────────────
    # Message batch size fetched per worker transaction lock
    batch_size: int = field(
        default_factory=lambda: int(os.getenv("BATCH_SIZE", "50"))
    )

    # Two-tier similarity thresholds:
    # - Low (0.65): Messages scoring above this are treated as borderline and sent to the LLM.
    # - High (0.65): Messages scoring above this are auto-approved directly, saving API tokens.
    # Adjusting these parameters lets the operator balance LLM budget vs. semantic precision.
    similarity_threshold_low: float = field(
        default_factory=lambda: float(os.getenv("SIMILARITY_THRESHOLD_LOW", "0.65"))
    )
    similarity_threshold_high: float = field(
        default_factory=lambda: float(os.getenv("SIMILARITY_THRESHOLD_HIGH", "0.65"))
    )


# Module-level singleton instance
_config_instance: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """
    Returns the shared AppConfig singleton.
    Pass `reload=True` to re-read environment variables (useful in test harnesses).
    """
    global _config_instance
    if _config_instance is None or reload:
        _config_instance = AppConfig()
    return _config_instance
