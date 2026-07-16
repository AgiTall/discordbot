"""Authentication service — OAuth2 flow and session management.

Handles the full lifecycle: code exchange → user fetch → session
creation/retrieval → cookie signing.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import UserSession
from app.services import discord_api

logger = logging.getLogger(__name__)

MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8

# Session cookie lives 30 days
SESSION_MAX_AGE = 30 * 24 * 60 * 60  # seconds

_signer = URLSafeTimedSerializer(settings.session_secret_key)


def sign_session_token(token: str) -> str:
    """Sign a session token for the cookie value."""
    return _signer.dumps(token)


def unsign_session_token(signed: str) -> str | None:
    """Verify and extract the session token from a signed cookie."""
    try:
        return _signer.loads(signed, max_age=SESSION_MAX_AGE)
    except BadSignature:
        return None


def _can_manage_guild(permissions: int | str) -> bool:
    perms = int(permissions)
    return bool(perms & ADMINISTRATOR) or bool(perms & MANAGE_GUILD)


def _build_guild_icon_url(guild_id: str, icon_hash: str | None) -> str | None:
    if not icon_hash:
        return None
    ext = "gif" if icon_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.{ext}"


async def create_session_from_code(
    code: str,
    db: AsyncSession,
    bot_guild_ids: set[str],
) -> tuple[UserSession, str]:
    """Run the full OAuth2 flow and return (session, signed_cookie_value).

    1. Exchange code for tokens
    2. Fetch user profile + guild list
    3. Create or update UserSession row
    4. Return signed cookie value
    """
    # Step 1: exchange code
    token_data = await discord_api.exchange_code(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    token_expires_at = None
    if expires_in:
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    # Step 2: fetch user + guilds
    user_data = await discord_api.get_user(access_token)
    guilds_data = await discord_api.get_user_guilds(access_token)

    # Step 3: keep every guild for the player profile.  The dashboard filters
    # this list to manageable guilds, while authorization itself is verified
    # live against Discord before every protected action.
    guilds = []
    for g in guilds_data:
        gid = str(g["id"])
        can_manage = _can_manage_guild(g.get("permissions", 0))
        guilds.append({
            "id": gid,
            "name": g.get("name", "Сервер"),
            "icon": _build_guild_icon_url(gid, g.get("icon")),
            "canManage": can_manage,
            "botPresent": gid in bot_guild_ids,
        })

    # Step 4: upsert UserSession
    discord_id = str(user_data["id"])
    stmt = select(UserSession).where(UserSession.discord_id == discord_id)
    result = await db.execute(stmt)
    session_row = result.scalar_one_or_none()
    is_new_session = session_row is None

    new_session_token = secrets.token_urlsafe(48)

    if session_row:
        session_row.username = user_data.get("username", "")
        session_row.global_name = user_data.get("global_name")
        session_row.avatar = user_data.get("avatar")
        session_row.access_token = access_token
        session_row.refresh_token = refresh_token
        session_row.token_expires_at = token_expires_at
        session_row.session_token = new_session_token
        session_row.guilds_json = json.dumps(guilds, ensure_ascii=False)
        session_row.last_seen_at = datetime.now(timezone.utc)
    else:
        session_row = UserSession(
            discord_id=discord_id,
            username=user_data.get("username", ""),
            global_name=user_data.get("global_name"),
            avatar=user_data.get("avatar"),
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            session_token=new_session_token,
            guilds_json=json.dumps(guilds, ensure_ascii=False),
        )
        db.add(session_row)

    try:
        await db.commit()
    except IntegrityError:
        if not is_new_session:
            raise

        # A second OAuth callback for the same Discord account may have
        # inserted the row after our SELECT.  The unique constraint makes that
        # race safe; update the winning row so the most recent login wins.
        await db.rollback()
        result = await db.execute(
            select(UserSession).where(UserSession.discord_id == discord_id)
        )
        session_row = result.scalar_one()
        session_row.username = user_data.get("username", "")
        session_row.global_name = user_data.get("global_name")
        session_row.avatar = user_data.get("avatar")
        session_row.access_token = access_token
        session_row.refresh_token = refresh_token
        session_row.token_expires_at = token_expires_at
        session_row.session_token = new_session_token
        session_row.guilds_json = json.dumps(guilds, ensure_ascii=False)
        session_row.last_seen_at = datetime.now(timezone.utc)
        await db.commit()
    await db.refresh(session_row)

    signed = sign_session_token(new_session_token)
    return session_row, signed


async def get_session_by_token(
    session_token: str,
    db: AsyncSession,
) -> UserSession | None:
    """Look up a session by its raw (unsigned) token."""
    stmt = select(UserSession).where(UserSession.session_token == session_token)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_session(session_row: UserSession, db: AsyncSession) -> None:
    """Delete a session row (logout)."""
    await db.delete(session_row)
    await db.commit()
