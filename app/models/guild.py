"""Guild model — represents a Discord server in the database.

Tracks premium / subscription state and is the parent for guild settings.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Discord guild snowflake ID (unique)
    discord_guild_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), default="")

    # ── Subscription / Premium ────────────────────────────────
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    lifetime_free: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────
    settings: Mapped[GuildSettings | None] = relationship(
        "GuildSettings",
        back_populates="guild",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ── Helpers ───────────────────────────────────────────────
    @property
    def has_access(self) -> bool:
        """Return True if the guild has premium access or is whitelisted."""
        if self.lifetime_free:
            return True
        if not self.is_premium:
            return False
        if self.subscription_ends_at is None:
            return True
        from datetime import timezone as tz
        return datetime.now(tz.utc) < self.subscription_ends_at

    def __repr__(self) -> str:
        return f"<Guild {self.discord_guild_id!r} name={self.name!r} premium={self.is_premium}>"


# Import here to avoid circular import issues with relationship string refs
from app.models.guild_settings import GuildSettings  # noqa: E402, F401
