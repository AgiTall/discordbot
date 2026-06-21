"""Unified launcher — runs Discord bot + FastAPI in a single asyncio loop.

Usage:
    python run.py

Both the bot and the web server share the same event loop and process,
which allows FastAPI routers to access the bot instance directly
(e.g. to list guild roles/channels).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# Ensure .env is loaded before anything else
from dotenv import load_dotenv
load_dotenv()

import discord
from discord.ext import commands
import uvicorn

from app.config import settings
from app.main import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("run")


def create_bot() -> commands.Bot:
    """Get the discord.py bot instance from bot.py and configure it."""
    from bot import bot

    @bot.event
    async def on_ready():
        logger.info("Bot is ready as %s (ID: %s)", bot.user, bot.user.id)
        logger.info("Connected to %d guilds", len(bot.guilds))

        # ── Whitelist: register all current guilds ────────────
        from app.database import async_session
        from app.services.guild_service import sync_bot_guilds

        async with async_session() as db:
            bot_guilds = [(str(g.id), g.name) for g in bot.guilds]
            created = await sync_bot_guilds(db, bot_guilds)
            if created:
                logger.info("Registered %d new guilds with lifetime_free=True", created)

        # Sync slash commands
        try:
            synced = await bot.tree.sync()
            logger.info("Synced %d application commands", len(synced))
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)

    return bot


async def main():
    """Start both the FastAPI server and the Discord bot concurrently."""
    bot = create_bot()
    app = create_app(bot)

    # ── Uvicorn config ────────────────────────────────────────
    uvi_config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.port,
        log_level="info",
    )
    server = uvicorn.Server(uvi_config)

    # ── Run both concurrently ─────────────────────────────────
    token = settings.discord_token
    if not token:
        logger.error("DISCORD_TOKEN is not set!")
        sys.exit(1)

    logger.info("Starting FastAPI on port %d + Discord bot...", settings.port)

    await asyncio.gather(
        server.serve(),
        bot.start(token),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
