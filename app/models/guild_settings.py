"""GuildSettings model — JSONB-based settings grouped by category.

Each guild has exactly one GuildSettings row.  Individual categories
(moderation, economy, logs, welcome, leveling) are stored as JSONB
columns so partial updates are cheap and schema-flexible.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ── Default values per category ───────────────────────────────

DEFAULT_MODERATION: dict = {
    "spam_protection": False,
    "swear_filter": False,
    "moderator_role_id": None,
}

DEFAULT_ECONOMY: dict = {
    "news_channel_id": None,
    "treasure_channel_id": None,
    "thread_channel_ids": [],
    "gold_rate": 543.45,
    "trade_enabled": True,
    "starting_capital": 500,
}

DEFAULT_LOGS: dict = {
    "channel_id": None,
    "log_join": True,
    "log_leave": True,
    "log_ban": True,
    "log_delete": False,
    "log_edit": False,
    "log_voice": False,
    "log_commands": False,
}

DEFAULT_WELCOME: dict = {
    "enabled": False,
    "channel_id": None,
    "role_id": None,
    "message": "Добро пожаловать на сервер, {mention}! 🎉",
    "farewell_enabled": False,
    "farewell_message": "{user} покинул сервер. До свидания!",
}

DEFAULT_LEVELING: dict = {
    "command_channel_ids": [],
    "allow_all_channels": False,
    "levelup_channel_id": None,
    "levelup_dm": False,
    "antifarm_cooldown": 60,
    "min_msg_length": 0,
    "base_message_xp": 15,
    "base_voice_xp": 10,
    "xp_rate_messages": 1.0,
    "xp_rate_voice": 1.0,
    "xp_rate_jobs": 1.0,
    "xp_rate_events": 1.0,
    "rank_roles": [],       # [{"level": 5, "role_id": "...", "remove_role_id": "..."}]
}

CATEGORY_DEFAULTS: dict[str, dict] = {
    "moderation": DEFAULT_MODERATION,
    "economy": DEFAULT_ECONOMY,
    "logs": DEFAULT_LOGS,
    "welcome": DEFAULT_WELCOME,
    "leveling": DEFAULT_LEVELING,
}


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("guilds.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # ── JSONB category columns ────────────────────────────────
    moderation: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    economy: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    logs: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    welcome: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    leveling: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # ── Relationship back-reference ───────────────────────────
    guild: Mapped["Guild"] = relationship(
        "Guild",
        back_populates="settings",
    )

    # ── Helpers ───────────────────────────────────────────────

    def get_category(self, category: str) -> dict:
        """Return merged defaults + stored values for a category."""
        defaults = CATEGORY_DEFAULTS.get(category, {})
        stored = getattr(self, category, None) or {}
        return {**defaults, **stored}

    def set_category(self, category: str, data: dict) -> dict:
        """Merge *data* into the given category and return the result."""
        current = self.get_category(category)
        current.update(data)
        setattr(self, category, current)
        return current

    def all_settings(self) -> dict[str, dict]:
        """Return all categories as a single dict."""
        return {
            cat: self.get_category(cat)
            for cat in CATEGORY_DEFAULTS
        }

    def __repr__(self) -> str:
        return f"<GuildSettings guild_id={self.guild_id}>"


# Avoid circular import — Guild is already imported at registration time
from app.models.guild import Guild  # noqa: E402, F401
