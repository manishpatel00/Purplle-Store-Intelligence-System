"""
app/core/settings.py — Application configuration settings
"""

import os
from datetime import date

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


class Settings:
    """Read configuration from environment variables with fallback defaults."""

    @property
    def cors_origins(self) -> list[str]:
        origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return [o.strip() for o in origins_str.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/store_intelligence.db")

    @property
    def redis_url(self) -> str:
        return os.getenv("REDIS_URL", "redis://localhost:6379/0")

    @property
    def prometheus_enabled(self) -> bool:
        return os.getenv("PROMETHEUS_ENABLED", "false").lower() in ("true", "1", "yes")

    @property
    def environment(self) -> str:
        return os.getenv("ENVIRONMENT", "development")

    @property
    def reentry_window_seconds(self) -> int:
        return int(os.getenv("REENTRY_WINDOW_SECONDS", "900"))

    @property
    def handoff_window_seconds(self) -> int:
        return int(os.getenv("HANDOFF_WINDOW_SECONDS", "20"))

    @property
    def challenge_date(self) -> date:
        """The challenge evaluation date — used as fallback when no data exists for today."""
        return date(2026, 4, 10)


settings = Settings()
