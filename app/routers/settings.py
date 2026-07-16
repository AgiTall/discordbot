"""Settings router — reads/writes guild settings via the bot's own stores.

Instead of PostgreSQL guild_settings tables, this router delegates to
``src.guild_config`` which writes through ``economy_store`` (psycopg2 JSON)
and ``leveling_db`` so that every change applied from the dashboard is
immediately visible to the running bot.
"""

from __future__ import annotations

import asyncio
import logging
from string import Formatter
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


def _setting_ids(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _validate_settings_payload(guild, data: dict[str, Any]) -> None:
    channel_ids = {str(channel.id) for channel in guild.channels}
    role_ids = {str(role.id) for role in guild.roles if role.id != guild.id}

    for key in (
        "newsChannelId",
        "treasureChannelId",
        "agitationChannelId",
        "levelupChannelId",
        "welcomeChannelId",
        "logsChannelId",
    ):
        value = str(data.get(key, "") or "").strip()
        if value and value not in channel_ids:
            raise HTTPException(status_code=400, detail=f"Выбранный канал для {key} недоступен")

    for key in ("threadChannelIds", "commandChannelIds"):
        invalid = [item for item in _setting_ids(data.get(key)) if item not in channel_ids]
        if invalid:
            raise HTTPException(status_code=400, detail=f"В {key} есть недоступный канал")

    welcome_role = str(data.get("welcomeRoleId", "") or "").strip()
    if welcome_role and welcome_role not in role_ids:
        raise HTTPException(status_code=400, detail="Выбранная роль новичка недоступна")

    bounds = {
        "antifarmCooldown": (10, 86400),
        "minMsgLength": (0, 4000),
        "xpMessages": (0, 10000),
        "xpVoice": (0, 10000),
        "xpJobs": (0, 100),
        "xpEvents": (0, 100),
        "xpRateMessages": (0, 100),
        "xpRateVoice": (0, 100),
        "goldRate": (50, 1_000_000_000),
    }
    for key, (minimum, maximum) in bounds.items():
        if key not in data:
            continue
        try:
            value = float(data[key])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Некорректное значение {key}")
        if not minimum <= value <= maximum:
            raise HTTPException(
                status_code=400,
                detail=f"{key} должно быть от {minimum} до {maximum}",
            )

    message_keys = (
        "welcomeMessage",
        "farewellMessage",
        "rolesDescription",
        "rolesFooter",
        "workSuccessMessage",
        "roleRequiredMessage",
        "resetPromptMessage",
    )
    for key in message_keys:
        if key in data and len(str(data[key])) > 2000:
            raise HTTPException(status_code=400, detail=f"{key} длиннее 2000 символов")

    template_examples = {
        "workSuccessMessage": {
            "mention": "@Игрок",
            "scenario": "выполнили работу",
            "reward": "10 $",
        },
        "roleRequiredMessage": {"role": "Самогонщик"},
    }
    for key, example in template_examples.items():
        if key not in data:
            continue
        template = str(data[key])
        allowed_fields = set(example)
        try:
            parsed = list(Formatter().parse(template))
            used_fields = {field for _, field, _, _ in parsed if field is not None}
            if not used_fields <= allowed_fields:
                raise KeyError
            template.format(**example)
        except (KeyError, ValueError, IndexError):
            allowed = ", ".join(f"{{{name}}}" for name in example)
            raise HTTPException(
                status_code=400,
                detail=f"В {key} разрешены только переменные: {allowed}",
            )

    import src.guild_config as guild_config
    configurable_emoji_fields = {
        *guild_config.EMOJI_FIELDS,
        *guild_config.ROLE_ICON_FIELDS,
    }
    for key in configurable_emoji_fields:
        if key in data and len(str(data[key]).strip()) > 80:
            raise HTTPException(status_code=400, detail=f"{key} длиннее 80 символов")


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
    await require_guild_access(guild_id, user, request)
    _ensure_bot_in_guild(request, guild_id)

    economy_store = _get_economy_store(request)
    leveling_db = _get_leveling_db(request)

    import src.guild_config as guild_config
    # EconomyStore is also used synchronously by the bot event loop. Keep all
    # access on that same thread so its mutable cache cannot be changed while
    # save_all() is iterating over it.
    settings = guild_config.get_guild_settings(
        economy_store, leveling_db, guild_id
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
    await require_guild_access(guild_id, user, request)
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
    guild = _get_bot(request).get_guild(int(guild_id))
    _validate_settings_payload(guild, data)

    import src.guild_config as guild_config

    # Get old settings for channel-change notifications
    old_settings = guild_config.get_guild_settings(
        economy_store, leveling_db, guild_id
    )

    try:
        settings = guild_config.set_guild_settings(
            economy_store, leveling_db, guild_id, data
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
                "agitationChannelId": "агитации и объявлений банд",
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
                            asyncio.create_task(
                                channel.send(
                                    f"✅ Этот канал теперь используется для **{purpose}**."
                                )
                            )

    return {"status": "ok", "settings": settings}
