"""Temporary voice channels with owner controls in the voice-channel chat."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import discord
from discord.ext import commands


LOGGER = logging.getLogger(__name__)
TEMP_VOICE_RECORDS_KEY = "temp_voice_channels"
TEMP_VOICE_CREATOR_KEY = "temp_voice_creator_channel_id"


def sanitize_voice_channel_name(value: str, *, fallback: str = "Быстрый канал") -> str:
    """Return a compact Discord-safe channel name."""
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    name = "".join(character for character in name if character.isprintable())
    return (name or fallback)[:100]


def normalize_temp_voice_records(value: Any) -> dict[str, dict[str, int | None]]:
    """Normalize persisted temporary-channel ownership metadata."""
    if not isinstance(value, dict):
        return {}

    records: dict[str, dict[str, int | None]] = {}
    for raw_channel_id, raw_record in value.items():
        channel_id = str(raw_channel_id).strip()
        if not channel_id.isdigit():
            continue

        if isinstance(raw_record, dict):
            raw_owner_id = raw_record.get("owner_id")
            raw_message_id = raw_record.get("message_id")
        else:
            # Backward-compatible form: {channel_id: owner_id}.
            raw_owner_id = raw_record
            raw_message_id = None

        owner_id = str(raw_owner_id or "").strip()
        if not owner_id.isdigit():
            continue
        message_id = str(raw_message_id or "").strip()
        records[channel_id] = {
            "owner_id": int(owner_id),
            "message_id": int(message_id) if message_id.isdigit() else None,
        }
    return records


class RenameChannelModal(discord.ui.Modal):
    def __init__(self, cog: "TemporaryVoiceCog", channel: discord.VoiceChannel):
        super().__init__(title="Название быстрого канала")
        self.cog = cog
        self.channel_id = channel.id
        self.name_input = discord.ui.TextInput(
            label="Новое название",
            default=channel.name,
            min_length=1,
            max_length=100,
            placeholder="Например: Поход за наградой",
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        channel = await self.cog.require_manager(interaction, self.channel_id)
        if channel is None:
            return
        name = sanitize_voice_channel_name(str(self.name_input.value))
        try:
            await channel.edit(name=name, reason=f"Temporary voice: renamed by {interaction.user}")
        except (discord.Forbidden, discord.HTTPException) as error:
            await interaction.response.send_message(
                f"Не удалось изменить название: {error}", ephemeral=True
            )
            return
        await interaction.response.send_message(f"Название изменено на **{name}**.", ephemeral=True)
        await self.cog.refresh_control_message(channel)


class UserLimitModal(discord.ui.Modal):
    def __init__(self, cog: "TemporaryVoiceCog", channel: discord.VoiceChannel):
        super().__init__(title="Лимит участников")
        self.cog = cog
        self.channel_id = channel.id
        self.limit_input = discord.ui.TextInput(
            label="Количество мест (0 — без лимита)",
            default=str(channel.user_limit or 0),
            min_length=1,
            max_length=2,
            placeholder="0–99",
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        channel = await self.cog.require_manager(interaction, self.channel_id)
        if channel is None:
            return
        raw_limit = str(self.limit_input.value).strip()
        if not raw_limit.isdigit() or not 0 <= int(raw_limit) <= 99:
            await interaction.response.send_message(
                "Укажите целое число от 0 до 99.", ephemeral=True
            )
            return
        user_limit = int(raw_limit)
        try:
            await channel.edit(
                user_limit=user_limit,
                reason=f"Temporary voice: limit changed by {interaction.user}",
            )
        except (discord.Forbidden, discord.HTTPException) as error:
            await interaction.response.send_message(
                f"Не удалось изменить лимит: {error}", ephemeral=True
            )
            return
        label = "снят" if user_limit == 0 else f"установлен: **{user_limit}**"
        await interaction.response.send_message(f"Лимит участников {label}.", ephemeral=True)
        await self.cog.refresh_control_message(channel)


class TransferOwnerSelect(discord.ui.UserSelect):
    def __init__(self, cog: "TemporaryVoiceCog", channel_id: int):
        super().__init__(placeholder="Выберите нового владельца", min_values=1, max_values=1)
        self.cog = cog
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        channel = await self.cog.require_manager(interaction, self.channel_id)
        if channel is None:
            return
        selected = self.values[0]
        member = channel.guild.get_member(selected.id)
        if member is None or member.bot or member not in channel.members:
            await interaction.response.send_message(
                "Новый владелец должен находиться в этом голосовом канале.",
                ephemeral=True,
            )
            return
        self.cog.set_owner(channel, member.id)
        await interaction.response.edit_message(
            content=f"Владельцем канала назначен {member.mention}.", view=None
        )
        await self.cog.refresh_control_message(channel)


class TransferOwnerView(discord.ui.View):
    def __init__(self, cog: "TemporaryVoiceCog", channel_id: int):
        super().__init__(timeout=60)
        self.add_item(TransferOwnerSelect(cog, channel_id))


class TemporaryVoiceControlView(discord.ui.View):
    def __init__(self, cog: "TemporaryVoiceCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Название",
        emoji="✏️",
        style=discord.ButtonStyle.secondary,
        custom_id="temp_voice:rename",
    )
    async def rename_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self.cog.require_manager(interaction)
        if channel is not None:
            await interaction.response.send_modal(RenameChannelModal(self.cog, channel))

    @discord.ui.button(
        label="Лимит",
        emoji="👥",
        style=discord.ButtonStyle.secondary,
        custom_id="temp_voice:limit",
    )
    async def limit_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self.cog.require_manager(interaction)
        if channel is not None:
            await interaction.response.send_modal(UserLimitModal(self.cog, channel))

    @discord.ui.button(
        label="Открыть / закрыть",
        emoji="🔒",
        style=discord.ButtonStyle.secondary,
        custom_id="temp_voice:lock",
    )
    async def lock_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self.cog.require_manager(interaction)
        if channel is None:
            return
        await interaction.response.defer(ephemeral=True)
        try:
            locked = await self.cog.toggle_channel_lock(channel)
        except (discord.Forbidden, discord.HTTPException) as error:
            await interaction.followup.send(f"Не удалось изменить доступ: {error}", ephemeral=True)
            return
        await interaction.followup.send(
            "Канал закрыт для новых участников." if locked else "Канал снова открыт.",
            ephemeral=True,
        )
        await self.cog.refresh_control_message(channel)

    @discord.ui.button(
        label="Передать",
        emoji="👑",
        style=discord.ButtonStyle.primary,
        custom_id="temp_voice:transfer",
    )
    async def transfer_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        channel = await self.cog.require_manager(interaction)
        if channel is None:
            return
        candidates = [member for member in channel.members if not member.bot]
        if len(candidates) < 2:
            await interaction.response.send_message(
                "Для передачи владельца в канале должен находиться другой участник.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Выберите нового владельца:",
            view=TransferOwnerView(self.cog, channel.id),
            ephemeral=True,
        )


class TemporaryVoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._member_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._ready_reconciled = False

    async def cog_load(self) -> None:
        self.bot.add_view(TemporaryVoiceControlView(self))

    def guild_data(self, guild_id: int) -> dict[str, Any]:
        return self.bot.get_economy_guild_data(guild_id)

    def records(self, guild_id: int) -> dict[str, dict[str, int | None]]:
        data = self.guild_data(guild_id)
        raw_records = data.get(TEMP_VOICE_RECORDS_KEY)
        normalized = normalize_temp_voice_records(raw_records)
        if raw_records != normalized:
            data[TEMP_VOICE_RECORDS_KEY] = normalized
        return data.setdefault(TEMP_VOICE_RECORDS_KEY, normalized)

    def save(self) -> None:
        self.bot.save_economy()

    def get_record(self, channel: discord.VoiceChannel) -> dict[str, int | None] | None:
        return self.records(channel.guild.id).get(str(channel.id))

    def set_owner(self, channel: discord.VoiceChannel, owner_id: int) -> None:
        records = self.records(channel.guild.id)
        record = records.get(str(channel.id)) or {"message_id": None}
        records[str(channel.id)] = {
            "owner_id": int(owner_id),
            "message_id": record.get("message_id"),
        }
        self.save()

    def remove_record(self, channel: discord.VoiceChannel) -> None:
        records = self.records(channel.guild.id)
        if records.pop(str(channel.id), None) is not None:
            self.save()

    def creator_channel_id(self, guild_id: int) -> int | None:
        value = self.guild_data(guild_id).get(TEMP_VOICE_CREATOR_KEY)
        try:
            return int(value) if value else None
        except (TypeError, ValueError):
            return None

    async def require_manager(
        self, interaction: discord.Interaction, channel_id: int | None = None
    ) -> discord.VoiceChannel | None:
        guild = interaction.guild
        resolved_id = channel_id or interaction.channel_id
        channel = guild.get_channel(resolved_id) if guild and resolved_id else None
        if not isinstance(channel, discord.VoiceChannel):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Этот элемент управления больше не связан с быстрым каналом.",
                    ephemeral=True,
                )
            return None
        record = self.get_record(channel)
        permissions = getattr(interaction.user, "guild_permissions", None)
        is_admin = bool(permissions and permissions.manage_channels)
        if record is None or (interaction.user.id != record["owner_id"] and not is_admin):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Управлять каналом может только его владелец или администратор.",
                    ephemeral=True,
                )
            return None
        return channel

    def control_embed(self, channel: discord.VoiceChannel) -> discord.Embed:
        record = self.get_record(channel) or {}
        owner_id = record.get("owner_id")
        human_members = [member for member in channel.members if not member.bot]
        default_overwrite = channel.overwrites_for(channel.guild.default_role)
        locked = default_overwrite.connect is False
        limit = str(channel.user_limit) if channel.user_limit else "без лимита"
        embed = discord.Embed(
            title="Управление быстрым каналом",
            description=(
                f"**Канал:** {channel.mention}\n"
                f"**Владелец:** <@{owner_id}>\n"
                f"**Участники:** {len(human_members)} · **лимит:** {limit}\n"
                f"**Доступ:** {'закрыт' if locked else 'открыт'}"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Кнопки доступны владельцу канала и администраторам")
        return embed

    async def refresh_control_message(self, channel: discord.VoiceChannel) -> None:
        record = self.get_record(channel)
        if record is None:
            return
        message = None
        message_id = record.get("message_id")
        if message_id:
            try:
                message = await channel.fetch_message(int(message_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                message = None
        try:
            if message is None:
                message = await channel.send(
                    embed=self.control_embed(channel), view=TemporaryVoiceControlView(self)
                )
                record["message_id"] = message.id
                self.save()
            else:
                await message.edit(
                    embed=self.control_embed(channel), view=TemporaryVoiceControlView(self)
                )
        except (discord.Forbidden, discord.HTTPException):
            LOGGER.warning("Cannot send temporary voice controls in channel %s", channel.id)

    async def toggle_channel_lock(self, channel: discord.VoiceChannel) -> bool:
        default_role = channel.guild.default_role
        overwrite = channel.overwrites_for(default_role)
        locked = overwrite.connect is False
        overwrite.connect = None if locked else False
        await channel.set_permissions(
            default_role,
            overwrite=overwrite,
            reason="Temporary voice: access toggled",
        )
        for member in [member for member in channel.members if not member.bot]:
            member_overwrite = channel.overwrites_for(member)
            member_overwrite.connect = None if locked else True
            await channel.set_permissions(
                member,
                overwrite=None if member_overwrite.is_empty() else member_overwrite,
                reason="Temporary voice: preserve member access",
            )
        return not locked

    async def create_or_reuse_channel(
        self, member: discord.Member, creator: discord.VoiceChannel
    ) -> None:
        key = (member.guild.id, member.id)
        lock = self._member_locks.setdefault(key, asyncio.Lock())
        async with lock:
            records = self.records(member.guild.id)
            for channel_id, record in list(records.items()):
                if record["owner_id"] != member.id:
                    continue
                existing = member.guild.get_channel(int(channel_id))
                if isinstance(existing, discord.VoiceChannel):
                    try:
                        await member.move_to(existing, reason="Temporary voice: return to owned channel")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                    return
                records.pop(channel_id, None)

            name = sanitize_voice_channel_name(f"🔊 {member.display_name}")
            channel = None
            try:
                channel = await member.guild.create_voice_channel(
                    name,
                    category=creator.category,
                    position=creator.position + 1,
                    bitrate=creator.bitrate,
                    rtc_region=creator.rtc_region,
                    video_quality_mode=creator.video_quality_mode,
                    overwrites=dict(creator.overwrites),
                    reason=f"Temporary voice: created for {member}",
                )
                owner_overwrite = channel.overwrites_for(member)
                owner_overwrite.view_channel = True
                owner_overwrite.connect = True
                await channel.set_permissions(
                    member,
                    overwrite=owner_overwrite,
                    reason="Temporary voice: grant owner access",
                )
                await member.move_to(channel, reason="Temporary voice: move owner")
            except (discord.Forbidden, discord.HTTPException) as error:
                LOGGER.warning("Cannot create temporary voice channel for %s: %s", member, error)
                if channel is not None:
                    try:
                        await channel.delete(reason="Temporary voice: owner move failed")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                try:
                    await member.send(
                        "Не удалось создать быстрый голосовой канал. Проверьте права бота "
                        "на управление каналами и перемещение участников."
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
                return

            records[str(channel.id)] = {"owner_id": member.id, "message_id": None}
            self.save()
            await self.refresh_control_message(channel)

    async def clean_or_transfer(self, channel: discord.VoiceChannel) -> None:
        record = self.get_record(channel)
        if record is None:
            return
        members = [member for member in channel.members if not member.bot]
        if not members:
            self.remove_record(channel)
            try:
                await channel.delete(reason="Temporary voice: empty channel")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
            return
        if not any(member.id == record["owner_id"] for member in members):
            self.set_owner(channel, members[0].id)
        await self.refresh_control_message(channel)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot or before.channel == after.channel:
            return
        creator_id = self.creator_channel_id(member.guild.id)
        if after.channel and creator_id and after.channel.id == creator_id:
            await self.create_or_reuse_channel(member, after.channel)
        if isinstance(before.channel, discord.VoiceChannel):
            await self.clean_or_transfer(before.channel)
        if isinstance(after.channel, discord.VoiceChannel) and self.get_record(after.channel):
            await self.refresh_control_message(after.channel)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._ready_reconciled:
            return
        self._ready_reconciled = True
        changed = False
        for guild in self.bot.guilds:
            records = self.records(guild.id)
            for channel_id in list(records):
                channel = guild.get_channel(int(channel_id))
                if not isinstance(channel, discord.VoiceChannel):
                    records.pop(channel_id, None)
                    changed = True
                    continue
                await self.clean_or_transfer(channel)
        if changed:
            self.save()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TemporaryVoiceCog(bot))
