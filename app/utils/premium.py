"""@premium_required — bot command check decorator.

Usage in discord.py Cog or standalone command:

    @app_commands.command(...)
    @premium_required()
    async def my_command(self, interaction: discord.Interaction):
        ...
"""

from __future__ import annotations

import logging
from functools import wraps

import discord
from discord import app_commands

from app.database import async_session
from app.services.guild_service import get_or_create_guild

logger = logging.getLogger(__name__)


def premium_required():
    """app_commands.check that verifies the guild has active premium access.

    If the guild is not premium and not lifetime_free, the command is
    blocked and the user is shown a purchase prompt.
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            # DMs — no guild context, allow or deny as you see fit
            return True

        guild_id = str(interaction.guild.id)

        async with async_session() as db:
            guild = await get_or_create_guild(db, guild_id, interaction.guild.name)

            if guild.has_access:
                return True

        embed = discord.Embed(
            title="🔒 Доступ ограничен",
            description=(
                "**БОТ НЕ ПРИОБРЕТЕН.**\n"
                "Купите доступ на [pchev.me](https://pchev.me)"
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text="Свяжитесь с администратором сервера для активации.")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False

    return app_commands.check(predicate)
