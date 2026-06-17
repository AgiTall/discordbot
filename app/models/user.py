"""UserSession model — stores authenticated Discord users and their sessions.

Each row represents a logged-in user.  The ``session_token`` is stored in a
signed HttpOnly cookie so the browser can re-authenticate on subsequent visits
without re-doing the OAuth2 flow.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Discord identity
    discord_id: Mapped[str] = mapped_column(String(32), index=True)
    username: Mapped[str] = mapped_column(String(128))
    global_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # OAuth tokens (stored encrypted in future; plain for MVP)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Session cookie value (unique, random)
    session_token: Mapped[str] = mapped_column(
        String(256), unique=True, index=True
    )

    # Cached list of guild IDs + permissions the user can manage
    # Stored as JSON text so we don't need a separate join table for MVP
    guilds_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<UserSession discord_id={self.discord_id!r} username={self.username!r}>"
