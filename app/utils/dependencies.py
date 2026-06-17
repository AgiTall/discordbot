"""FastAPI dependencies — reusable Depends() for auth and DB sessions."""

from __future__ import annotations

import json
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
) -> bool:
    """Check that the user has MANAGE_GUILD or ADMINISTRATOR for guild_id.

    Raises 403 if access is denied.
    """
    guilds = []
    if user.guilds_json:
        try:
            guilds = json.loads(user.guilds_json)
        except (json.JSONDecodeError, TypeError):
            guilds = []

    for g in guilds:
        if str(g.get("id")) == str(guild_id) and g.get("canManage"):
            return True

    raise HTTPException(status_code=403, detail={"error": "Forbidden"})


# Type aliases for cleaner router signatures
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[UserSession, Depends(get_current_user)]
