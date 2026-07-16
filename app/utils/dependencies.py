"""FastAPI dependencies — reusable Depends() for auth and DB sessions."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.user import UserSession
from app.services.auth_service import unsign_session_token

logger = logging.getLogger(__name__)

MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8


async def get_db() -> AsyncSession:
    """Yield an async database session for a single request."""
    async with async_session() as session:
        yield session


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserSession:
    """Extract and validate user from the session cookie.

    Raises 401 if the cookie is missing, invalid, or the session
    doesn't exist in the database.
    """
    signed_token = request.cookies.get("session_token")
    if not signed_token:
        raise HTTPException(
            status_code=401,
            detail={"error": "Unauthorized", "login": "/auth/discord"},
        )

    raw_token = unsign_session_token(signed_token)
    if raw_token is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid or expired session", "login": "/auth/discord"},
        )

    from app.services.auth_service import get_session_by_token

    session_row = await get_session_by_token(raw_token, db)
    if session_row is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "Session not found", "login": "/auth/discord"},
        )

    return session_row


async def require_guild_access(
    guild_id: str,
    user: UserSession,
    request: Request,
) -> bool:
    """Check the user's current Discord permissions for ``guild_id``.

    Cached OAuth guild data is deliberately not trusted here: permissions can
    be revoked while the dashboard session is still valid.  The bot's REST
    API is used so the decision does not depend on the member cache.
    """
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail={"error": "Bot offline"})

    try:
        guild = bot.get_guild(int(guild_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail={"error": "Invalid guild ID"})

    if guild is None:
        raise HTTPException(status_code=404, detail={"error": "Guild not found"})

    try:
        member = await guild.fetch_member(int(user.discord_id))
    except Exception as exc:
        # Unknown Member (and Discord/API failures) must fail closed.  Falling
        # back to guilds_json would reintroduce stale authorization.
        logger.warning(
            "Could not verify Discord permissions for user %s in guild %s: %s",
            user.discord_id,
            guild_id,
            exc,
        )
        raise HTTPException(status_code=403, detail={"error": "Forbidden"})

    permissions = member.guild_permissions
    if permissions.administrator or permissions.manage_guild:
        return True

    raise HTTPException(status_code=403, detail={"error": "Forbidden"})


# Type aliases for cleaner router signatures
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserSession, Depends(get_current_user)]
