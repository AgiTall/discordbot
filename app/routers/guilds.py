"""Guild router — dynamic Discord data (roles, channels)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.schemas.guild import ChannelItem, RoleItem
from app.utils.dependencies import CurrentUser, DbSession, require_guild_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guilds", tags=["guilds"])


@router.get("/{guild_id}/roles", response_model=list[RoleItem])
async def get_guild_roles(
    guild_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Return the guild's roles (excluding @everyone), sorted by position desc."""
    await require_guild_access(guild_id, user)

    bot = request.app.state.bot
    if not bot:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Bot offline")

    guild = bot.get_guild(int(guild_id))
    if not guild:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Guild not found")

    roles = []
    for r in guild.roles:
        # Skip @everyone
        if r.id == guild.id:
            continue

        color_hex = str(r.color)
        if color_hex == "#000000":
            color_hex = "#99aab5"  # Discord default grey

        roles.append(RoleItem(
            id=str(r.id),
            name=r.name,
            color=color_hex,
            position=r.position,
        ))

    roles.sort(key=lambda x: x.position, reverse=True)
    return roles


@router.get("/{guild_id}/channels", response_model=list[ChannelItem])
async def get_guild_channels(
    guild_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Return the guild's channels (text, voice, category), sorted by position."""
    await require_guild_access(guild_id, user)

    bot = request.app.state.bot
    if not bot:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Bot offline")

    guild = bot.get_guild(int(guild_id))
    if not guild:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Guild not found")

    channels = []
    for ch in guild.channels:
        channels.append(ChannelItem(
            id=str(ch.id),
            name=ch.name,
            type=ch.type.value,
            category=ch.category.name if ch.category else None,
            position=ch.position,
        ))

    channels.sort(key=lambda x: x.position)
    return channels
