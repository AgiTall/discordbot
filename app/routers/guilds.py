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

    try:
        guild = bot.get_guild(int(guild_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid guild ID")

    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")

    channels = []
    for ch in guild.channels:
        # discord.ChannelType.text == 0, voice == 2, category == 4, news == 5, forum == 15
        try:
            # Safely get type as integer
            ctype = int(ch.type)
        except Exception:
            ctype = getattr(ch.type, 'value', 0)
            
        cname = None
        if getattr(ch, "category", None):
            # ch.category can be a CategoryChannel or potentially a string/int in odd API states
            cname = getattr(ch.category, "name", str(ch.category))
            
        channels.append(ChannelItem(
            id=str(ch.id),
            name=str(ch.name),
            type=ctype,
            category=cname,
            position=getattr(ch, "position", 0),
        ))

    # Optional: filter out category channels themselves from the dropdown if needed,
    # but we'll return all channels and let the frontend show them.
    channels.sort(key=lambda x: getattr(x, "position", 0))
    return channels


@router.get("/{guild_id}/emojis")
async def get_guild_emojis(
    guild_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Return the guild's custom emojis."""
    await require_guild_access(guild_id, user)

    bot = request.app.state.bot
    if not bot:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Bot offline")

    guild = bot.get_guild(int(guild_id))
    if not guild:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Guild not found")

    emojis = []
    for e in guild.emojis:
        emojis.append({
            "id": str(e.id),
            "name": e.name,
            "url": str(e.url),
            "animated": e.animated,
            "format": f"<a:{e.name}:{e.id}>" if e.animated else f"<:{e.name}:{e.id}>",
        })

    return emojis


@router.get("/{guild_id}/stats")
async def get_guild_stats(
    guild_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Return economy statistics — leaderboard, gangs, globals."""
    await require_guild_access(guild_id, user)

    bot = request.app.state.bot
    if not bot:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Bot offline")

    economy_store = getattr(request.app.state, "economy_data", None)
    if not economy_store:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Economy store not available")

    guild_data = economy_store.guild_data(guild_id)
    users = guild_data.get("users", {})
    gangs = guild_data.get("gangs", {})
    gold_rate = guild_data.get("gold_rate", 543.45)

    # 1. Leaderboard
    user_list = []
    total_cash = 0.0
    total_gold = 0.0

    for u_id, u_data in users.items():
        c = float(u_data.get("cash", 0.0))
        g = float(u_data.get("gold", 0.0))
        total_cash += c
        total_gold += g
        wealth = c + (g * gold_rate)

        name = f"User {u_id}"
        user_obj = bot.get_user(int(u_id))
        if user_obj:
            name = user_obj.display_name
        elif "name" in u_data:
            name = u_data["name"]

        user_list.append({
            "id": u_id,
            "name": name,
            "cash": c,
            "gold": g,
            "wealth": wealth,
            "level": u_data.get("level", 1),
        })

    user_list.sort(key=lambda x: x["wealth"], reverse=True)
    top_10 = user_list[:10]

    # 2. Gangs
    gang_list = []
    for g_name, g_data in gangs.items():
        gc = float(g_data.get("cash", 0.0))
        gg = float(g_data.get("gold", 0.0))
        g_wealth = gc + (gg * gold_rate)
        total_cash += gc
        total_gold += gg

        gang_list.append({
            "name": g_name,
            "id": g_data.get("id", 0),
            "members_count": len(g_data.get("members", [])),
            "cash": gc,
            "gold": gg,
            "wealth": g_wealth,
            "influence": g_data.get("influence", 0),
        })

    gang_list.sort(key=lambda x: x["wealth"], reverse=True)

    return {
        "leaderboard": top_10,
        "gangs": gang_list,
        "globals": {
            "total_users": len(users),
            "total_gangs": len(gangs),
            "total_cash": total_cash,
            "total_gold": total_gold,
            "gold_rate": gold_rate,
        },
    }
