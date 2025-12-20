"""
Configuration for SentimentPulse.

Settings come from environment variables; the watch-list (which civic issues
and subreddits to monitor) comes from config/keywords.yaml so it can be edited
without touching code.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database — SQLite by default, Postgres-compatible if DATABASE_URL is set
    database_url: str = Field(
        default="sqlite+aiosqlite:///./sentimentpulse.db",
        alias="DATABASE_URL",
    )

    # Reddit API (optional — falls back to bundled seed data when absent)
    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(
        default="sentimentpulse/2.0 (civic sentiment demo)",
        alias="REDDIT_USER_AGENT",
    )

    # App settings
    debug: bool = Field(default=True, alias="DEBUG")
    # Optional token guarding manual /api/trigger/* endpoints
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")

    # Ingestion
    ingestion_interval_minutes: int = Field(default=15, alias="INGESTION_INTERVAL_MINUTES")
    posts_per_keyword: int = Field(default=25, alias="POSTS_PER_KEYWORD")

    # Concurrency / resilience for the ingestion fan-out
    max_concurrent_requests: int = Field(default=5, alias="MAX_CONCURRENT_REQUESTS")
    request_max_retries: int = Field(default=3, alias="REQUEST_MAX_RETRIES")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class WatchlistConfig:
    """Loads the civic-issue watch-list (subreddits, search terms, topics)."""

    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "keywords.yaml"
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}

    @property
    def project_info(self) -> dict[str, str]:
        return self._config.get("project", {})

    @property
    def subreddits(self) -> list[str]:
        return self._config.get("subreddits", [])

    @property
    def search_keywords(self) -> list[str]:
        return self._config.get("search_keywords", [])

    @property
    def topics(self) -> dict[str, list[str]]:
        return self._config.get("topics", {})


# Global instances
settings = Settings()
watchlist = WatchlistConfig()
