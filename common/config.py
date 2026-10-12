import os
import logging
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

logger = logging.getLogger("AuraConfig")

# Auto-load .env from Project_Aura root if not already loaded
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(base_dir, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """
    Centralized, typed configuration for Project Aura.
    Decouples individual modules from direct os.environ and dotenv lookups.
    """
    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/aura_db")
    )

    # LLM Settings
    llm_provider: str = field(
        default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini").lower()
    )
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    )
    groq_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY")
    )
    groq_model: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    openai_api_base: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )

    # Embeddings
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").lower()
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )

    # Telegram Credentials & Tokens
    telegram_api_id: Optional[int] = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_API_ID")) if os.getenv("TELEGRAM_API_ID") else None
    )
    telegram_api_hash: Optional[str] = field(
        default_factory=lambda: os.getenv("TELEGRAM_API_HASH")
    )
    telegram_session_string: Optional[str] = field(
        default_factory=lambda: os.getenv("TELEGRAM_SESSION_STRING")
    )
    assistant_bot_token: Optional[str] = field(
        default_factory=lambda: os.getenv("ASSISTANT_BOT_TOKEN")
    )
    telegram_user_id: Optional[int] = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_USER_ID")) if os.getenv("TELEGRAM_USER_ID") else None
    )

    # Worker Pipeline Thresholds
    batch_size: int = field(
        default_factory=lambda: int(os.getenv("BATCH_SIZE", "50"))
    )
    similarity_threshold_low: float = field(
        default_factory=lambda: float(os.getenv("SIMILARITY_THRESHOLD_LOW", "0.65"))
    )
    similarity_threshold_high: float = field(
        default_factory=lambda: float(os.getenv("SIMILARITY_THRESHOLD_HIGH", "0.65"))
    )


_config_instance: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """
    Returns the singleton AppConfig instance.
    """
    global _config_instance
    if _config_instance is None or reload:
        _config_instance = AppConfig()
    return _config_instance
