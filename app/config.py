"""Application settings loaded from environment variables.

Uses pydantic-settings to validate and parse .env / os.environ
at import-time so that typos and missing keys surface immediately.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Central configuration sourced from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # ignore unknown env vars (e.g. legacy Flask keys)
    )

    # ── Database ──────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://pchevbot:pchevbot_secret@localhost:5432/pchevbot"

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None) -> str:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
            return v
        return "postgresql+asyncpg://pchevbot:pchevbot_secret@localhost:5432/pchevbot"

    # ── Discord ───────────────────────────────────────────────
    discord_client_id: str
    discord_client_secret: str
    discord_token: str           # bot token (previously DISCORD_TOKEN)

    # ── OAuth2 ────────────────────────────────────────────────
    oauth_redirect_uri: str = "http://localhost:10000/auth/discord/callback"

    # ── Session / Security ────────────────────────────────────
    session_secret_key: str      # used to sign session cookies

    # ── Server ────────────────────────────────────────────────
    port: int = 10000
    frontend_url: str = "http://localhost:10000"
    support_url: str = ""
    debug: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        """Accept legacy deployment labels such as DEBUG=release."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"debug", "development", "dev"}:
                return True
        return value

    # ── Render-specific ───────────────────────────────────────
    render: bool = False         # set RENDER=true on Render.com


settings = Settings()
