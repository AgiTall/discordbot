"""API Router for Gangs (Банды) — reads from economy_store (bot's JSON data).

The bot stores gangs in economy_store.guild_data(guild_id)["gangs"],
so this router reads/writes there directly instead of PostgreSQL.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.utils.dependencies import CurrentUser, require_guild_access
from src.constants import ROLE_DEFINITIONS
from src.economy_stats import build_web_emoji_payload
from src.gold_rate_history import normalize_gold_rate_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["gangs"])


def _number(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _get_economy_store(request: Request):
    store = getattr(request.app.state, "economy_data", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Economy store not available")
    return store


def _public_gang(gang_name: str, gang_data: dict[str, Any]) -> dict[str, Any]:
    members = gang_data.get("members", [])
    return {
        "id": gang_data.get("id"),
        "name": gang_name,
        "balance": float(gang_data.get("cash", 0.0)),
        "gold": float(gang_data.get("gold", 0.0)),
        "camp_upgrades": gang_data.get("camp_upgrades", {}),
        "member_count": len(members) if isinstance(members, (list, dict)) else 0,
        "logo_url": gang_data.get("logo_url"),
        "background_url": gang_data.get("bg_url"),
        "description": gang_data.get("description", ""),
    }


async def _require_guild_member(guild_id: str, request: Request, user: CurrentUser):
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot offline")
    try:
        guild = bot.get_guild(int(guild_id))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid guild ID")
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")
    try:
        return await guild.fetch_member(int(user.discord_id))
    except Exception:
        raise HTTPException(status_code=403, detail="You are not a member of this guild")


@router.get("/guilds/{guild_id}/me/profile")
async def get_my_profile(
    guild_id: str,
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    """Return the authenticated player's economy overview."""
    member = await _require_guild_member(guild_id, request, user)
    guild_data = _get_economy_store(request).guild_data(guild_id)
    account = guild_data.get("users", {}).get(str(user.discord_id), {})
    cash = _number(account.get("cash"))
    gold = _number(account.get("gold"))
    safe_cash = _number(account.get("safe_cash"))
    safe_gold = _number(account.get("safe_gold"))
    gold_rate = _number(guild_data.get("gold_rate")) or 543.45
    owned_role_keys = account.get("owned_roles", [])
    if not isinstance(owned_role_keys, list):
        owned_role_keys = []
    owned_role_keys = [str(key) for key in owned_role_keys]
    role_icons = guild_data.get("role_key_icons", {})
    if not isinstance(role_icons, dict):
        role_icons = {}
    owned_roles = [
        {
            "key": definition["key"],
            "name": definition["name"],
            "emoji": str(role_icons.get(definition["key"]) or definition["emoji"]),
        }
        for definition in ROLE_DEFINITIONS
        if definition["key"] in owned_role_keys
    ]

    level_data = {"xp": 0, "level": 1}
    rank_position = None
    get_cog = getattr(getattr(request.app.state, "bot", None), "get_cog", None)
    leveling_cog = get_cog("LevelingCog") if callable(get_cog) else None
    leveling_db = getattr(leveling_cog, "db", None)
    if leveling_db is not None:
        try:
            level_data = await asyncio.to_thread(
                leveling_db.get_user,
                str(guild_id),
                str(user.discord_id),
            )
            rank_position = await asyncio.to_thread(
                leveling_db.get_user_rank_position,
                str(guild_id),
                str(user.discord_id),
            )
        except Exception:
            logger.exception("Failed to load leveling profile for guild %s", guild_id)

    return {
        "id": str(user.discord_id),
        "display_name": member.display_name,
        "avatar_url": str(member.display_avatar.url),
        "cash": cash,
        "gold": gold,
        "treasure_maps": max(0, int(_number(account.get("treasure_maps")))),
        "safe_cash": safe_cash,
        "safe_gold": safe_gold,
        "total_cash": cash + safe_cash,
        "total_gold": gold + safe_gold,
        "wealth": cash + safe_cash + (gold + safe_gold) * gold_rate,
        "gold_rate": gold_rate,
        "gold_rate_history": normalize_gold_rate_history(
            guild_data.get("gold_rate_history"),
            fallback_date=guild_data.get("gold_rate_date"),
            fallback_rate=gold_rate,
        ),
        "owned_roles": owned_role_keys,
        "owned_role_details": owned_roles,
        "level": max(1, int(level_data.get("level", 1) or 1)),
        "xp": max(0, int(level_data.get("xp", 0) or 0)),
        "rank_position": rank_position,
        "gang_name": account.get("gang_name"),
        "emojis": build_web_emoji_payload(guild_data),
    }


@router.get("/guilds/{guild_id}/me/gang")
async def get_my_gang(
    guild_id: str,
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    """Return the authenticated player's gang on a server."""
    await _require_guild_member(guild_id, request, user)

    gangs = _get_economy_store(request).guild_data(guild_id).get("gangs", {})
    player_id = str(user.discord_id)
    for gang_name, gang_data in gangs.items():
        member_ids = {str(member_id) for member_id in gang_data.get("members", [])}
        if player_id in member_ids:
            return {
                "gang": _public_gang(gang_name, gang_data),
                "my_role": (
                    "leader"
                    if str(gang_data.get("leader")) == player_id
                    else "member"
                ),
            }

    raise HTTPException(status_code=404, detail="Player is not in a gang")


@router.get("/guilds/{guild_id}/gangs")
async def get_guild_gangs(
    guild_id: str,
    request: Request,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    """List all gangs for a guild from economy_store."""
    await require_guild_access(guild_id, user, request)

    economy_store = _get_economy_store(request)
    guild_data = economy_store.guild_data(guild_id)
    gangs = guild_data.get("gangs", {})

    result = []
    for g_name, g_data in gangs.items():
        item = _public_gang(g_name, g_data)
        if item["id"] is None:
            item["id"] = hash(g_name) % 10000
        result.append(item)

    return result


@router.delete("/guilds/{guild_id}/gangs/{gang_id}")
async def delete_gang(
    guild_id: str,
    gang_id: int,
    request: Request,
    user: CurrentUser,
):
    """Delete a gang from economy_store by its ID."""
    await require_guild_access(guild_id, user, request)

    economy_store = _get_economy_store(request)
    guild_data = economy_store.guild_data(guild_id)
    gangs = guild_data.get("gangs", {})

    # Find the gang by ID
    target_name = None
    for g_name, g_data in gangs.items():
        if g_data.get("id") == gang_id:
            target_name = g_name
            break

    if target_name is None:
        raise HTTPException(status_code=404, detail="Gang not found")

    del gangs[target_name]
    economy_store.save_all()

    return {"status": "ok"}
