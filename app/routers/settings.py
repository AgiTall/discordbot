"""Settings router — CRUD for guild settings grouped by category."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.schemas.settings import AllSettingsResponse, SettingsCategoryResponse, SettingsUpdate
from app.services import guild_service
from app.utils.dependencies import CurrentUser, DbSession, require_guild_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guilds", tags=["settings"])

VALID_CATEGORIES = {"moderation", "economy", "logs", "welcome", "leveling"}


def _ensure_bot_in_guild(request: Request, guild_id: str) -> bool:
    """Raise 404 if the bot is not in the guild."""
    bot = request.app.state.bot
    if not bot:
        raise HTTPException(status_code=503, detail="Bot offline")
    if not any(str(g.id) == str(guild_id) for g in bot.guilds):
        raise HTTPException(
            status_code=404,
            detail={"error": "Bot is not on this server", "botPresent": False},
        )
    return True


@router.get("/{guild_id}/settings", response_model=AllSettingsResponse)
async def get_all_settings(
    guild_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Return all settings for a guild (all categories)."""
    await require_guild_access(guild_id, user)
    _ensure_bot_in_guild(request, guild_id)

    guild = await guild_service.get_or_create_guild(db, guild_id)
    all_settings = await guild_service.get_all_settings(db, guild)

    return AllSettingsResponse(guild_id=guild_id, settings=all_settings)


@router.get("/{guild_id}/settings/{category}", response_model=SettingsCategoryResponse)
async def get_category_settings(
    guild_id: str,
    category: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Return a single category's settings."""
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    await require_guild_access(guild_id, user)
    _ensure_bot_in_guild(request, guild_id)

    guild = await guild_service.get_or_create_guild(db, guild_id)
    data = await guild_service.get_category_settings(db, guild, category)

    return SettingsCategoryResponse(category=category, settings=data)


@router.put("/{guild_id}/settings/{category}", response_model=SettingsCategoryResponse)
async def update_category_settings(
    guild_id: str,
    category: str,
    body: SettingsUpdate,
    request: Request,
    user: CurrentUser,
    db: DbSession,
):
    """Update (partial merge) a single category's settings."""
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    await require_guild_access(guild_id, user)
    _ensure_bot_in_guild(request, guild_id)

    guild = await guild_service.get_or_create_guild(db, guild_id)
    result = await guild_service.update_category_settings(db, guild, category, body.data)

    return SettingsCategoryResponse(category=category, settings=result)
