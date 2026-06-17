"""Guild service — CRUD operations for guilds and their settings.

Also includes premium/subscription checks used by both the API and the bot.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guild import Guild
from app.models.guild_settings import CATEGORY_DEFAULTS, GuildSettings

logger = logging.getLogger(__name__)


async def get_or_create_guild(
    db: AsyncSession,
    discord_guild_id: str,
    name: str = "",
    *,
    lifetime_free: bool = False,
) -> Guild:
    """Return existing guild or create a new one with defaults."""
    stmt = select(Guild).where(Guild.discord_guild_id == discord_guild_id)
    result = await db.execute(stmt)
    guild = result.scalar_one_or_none()

    if guild is not None:
        # Update name if changed
        if name and guild.name != name:
            guild.name = name
            await db.commit()
        return guild

    guild = Guild(
        discord_guild_id=discord_guild_id,
        name=name,
        lifetime_free=lifetime_free,
    )
    db.add(guild)
    await db.flush()  # get guild.id

    # Create default settings
    guild_settings = GuildSettings(
        guild_id=guild.id,
        moderation=dict(CATEGORY_DEFAULTS["moderation"]),
        economy=dict(CATEGORY_DEFAULTS["economy"]),
        logs=dict(CATEGORY_DEFAULTS["logs"]),
        welcome=dict(CATEGORY_DEFAULTS["welcome"]),
        leveling=dict(CATEGORY_DEFAULTS["leveling"]),
    )
    db.add(guild_settings)
    await db.commit()
    await db.refresh(guild)
    return guild


async def get_guild_by_discord_id(
    db: AsyncSession,
    discord_guild_id: str,
) -> Guild | None:
    """Look up a guild by its Discord snowflake ID."""
    stmt = select(Guild).where(Guild.discord_guild_id == discord_guild_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_settings(db: AsyncSession, guild: Guild) -> dict:
    """Return all settings for a guild, creating defaults if needed."""
    if guild.settings is None:
        guild_settings = GuildSettings(
            guild_id=guild.id,
            moderation=dict(CATEGORY_DEFAULTS["moderation"]),
            economy=dict(CATEGORY_DEFAULTS["economy"]),
            logs=dict(CATEGORY_DEFAULTS["logs"]),
            welcome=dict(CATEGORY_DEFAULTS["welcome"]),
            leveling=dict(CATEGORY_DEFAULTS["leveling"]),
        )
        db.add(guild_settings)
        await db.commit()
        await db.refresh(guild)

    return guild.settings.all_settings()


async def get_category_settings(db: AsyncSession, guild: Guild, category: str) -> dict:
    """Return a single category's settings (merged with defaults)."""
    if category not in CATEGORY_DEFAULTS:
        raise ValueError(f"Unknown category: {category}")

    if guild.settings is None:
        await get_all_settings(db, guild)  # ensure settings row exists

    return guild.settings.get_category(category)


async def update_category_settings(
    db: AsyncSession,
    guild: Guild,
    category: str,
    data: dict,
) -> dict:
    """Merge *data* into the given category and persist."""
    if category not in CATEGORY_DEFAULTS:
        raise ValueError(f"Unknown category: {category}")

    if guild.settings is None:
        await get_all_settings(db, guild)

    result = guild.settings.set_category(category, data)
    await db.commit()
    return result


# ── Premium / Subscription helpers ────────────────────────────

async def check_premium(db: AsyncSession, discord_guild_id: str) -> bool:
    """Return True if the guild has active premium access."""
    guild = await get_guild_by_discord_id(db, discord_guild_id)
    if guild is None:
        return False
    return guild.has_access


async def activate_premium(
    db: AsyncSession,
    discord_guild_id: str,
    days: int = 30,
) -> Guild:
    """Mark a guild as premium for *days* days."""
    guild = await get_or_create_guild(db, discord_guild_id)
    guild.is_premium = True
    guild.subscription_ends_at = datetime.now(timezone.utc) + timedelta(days=days)
    await db.commit()
    await db.refresh(guild)
    return guild


async def sync_bot_guilds(
    db: AsyncSession,
    bot_guilds: list[tuple[str, str]],
) -> int:
    """Register all current bot guilds, setting lifetime_free=True for new ones.

    *bot_guilds* is a list of (discord_guild_id, name) tuples.
    Returns the count of newly created guilds.
    """
    # Fetch all existing guild IDs in one query
    stmt = select(Guild.discord_guild_id)
    result = await db.execute(stmt)
    existing_ids = {row[0] for row in result}

    created = 0
    for gid, name in bot_guilds:
        if gid not in existing_ids:
            await get_or_create_guild(db, gid, name, lifetime_free=True)
            created += 1

    logger.info("Guild sync complete: %d existing, %d newly created (lifetime_free)", len(existing_ids), created)
    return created
