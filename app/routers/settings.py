"""Settings router — reads/writes guild settings via the bot's own stores.

Instead of PostgreSQL guild_settings tables, this router delegates to
``src.guild_config`` which writes through ``economy_store`` (psycopg2 JSON)
and ``leveling_db`` so that every change applied from the dashboard is
immediately visible to the running bot.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.utils.dependencies import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guilds", tags=["settings"])


# ── Helpers ───────────────────────────────────────────────────

def _get_bot(request: Request):
    bot = getattr(request.app.state, "bot", None)
    if not bot:
        raise HTTPException(status_code=503, detail="Bot offline")
    return bot


def _get_economy_store(request: Request):
    store = getattr(request.app.state, "economy_data", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Economy store not available")
    return store


def _get_leveling_db(request: Request):
    bot = _get_bot(request)
    cog = bot.get_cog("LevelingCog")
    if cog is None or cog.db is None:
        raise HTTPException(status_code=503, detail="Leveling DB unavailable")
    return cog.db


def _ensure_bot_in_guild(request: Request, guild_id: str) -> bool:
    bot = _get_bot(request)
    if not any(str(g.id) == str(guild_id) for g in bot.guilds):
        raise HTTPException(
            status_code=404,
            detail={"error": "Bot is not on this server", "botPresent": False},
        )
    return True


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/{guild_id}/settings")
async def get_all_settings(
    guild_id: str,
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    """Return all settings for a guild (flat camelCase dict).

    Uses ``src.guild_config.get_guild_settings`` which reads from
    economy_store + leveling_db — the same stores the bot uses.
    """
    from app.utils.dependencies import require_guild_access
    await require_guild_access(guild_id, user)
    _ensure_bot_in_guild(request, guild_id)

    economy_store = _get_economy_store(request)
    leveling_db = _get_leveling_db(request)

    import src.guild_config as guild_config
    settings = await asyncio.to_thread(
        guild_config.get_guild_settings, economy_store, leveling_db, guild_id
    )
    return settings


@router.put("/{guild_id}/settings")
@router.post("/{guild_id}/settings")
async def update_all_settings(
    guild_id: str,
    request: Request,
    user: CurrentUser,
) -> dict:
    """Update settings from a flat camelCase dictionary.

    Accepts either ``{data: {...}}`` (new frontend format) or a plain dict
    (direct) for backwards compatibility.
    """
    from app.utils.dependencies import require_guild_access
    await require_guild_access(guild_id, user)
    _ensure_bot_in_guild(request, guild_id)

    body = await request.json()

    # Support both {data: {...}} and flat dict
    if isinstance(body, dict) and "data" in body and isinstance(body["data"], dict):
        data = body["data"]
    elif isinstance(body, dict):
        data = body
    else:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not data:
        raise HTTPException(status_code=400, detail="No data")

    economy_store = _get_economy_store(request)
    leveling_db = _get_leveling_db(request)

    import src.guild_config as guild_config

    # Get old settings for channel-change notifications
    old_settings = await asyncio.to_thread(
        guild_config.get_guild_settings, economy_store, leveling_db, guild_id
    )

    try:
        settings = await asyncio.to_thread(
            guild_config.set_guild_settings, economy_store, leveling_db, guild_id, data
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Send notification to newly-configured channels ────────
    bot = _get_bot(request)
    if bot and getattr(bot, "loop", None):
        guild = bot.get_guild(int(guild_id))
        if guild:
            channel_map = {
                "newsChannelId": "публикации анонсов и новостей",
                "treasureChannelId": "ежедневной раздачи карт сокровищ",
                "levelupChannelId": "уведомлений о повышении уровня",
                "welcomeChannelId": "приветствий новых участников",
                "logsChannelId": "записи серверных логов",
            }
            for key, purpose in channel_map.items():
                if key in data:
                    old_val = str(old_settings.get(key) or "")
                    new_val = str(settings.get(key) or "")
                    if new_val and new_val != old_val and new_val.isdigit():
                        channel = guild.get_channel(int(new_val))
                        if channel:
                            asyncio.run_coroutine_threadsafe(
                                channel.send(
                                    f"✅ Этот канал теперь используется для **{purpose}**."
                                ),
                                bot.loop,
                            )

    return {"status": "ok", "settings": settings}
