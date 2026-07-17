"""
src/utils.py
Вспомогательные функции:
 - embed-хелперы (build_bot_embed, send_embed_response, …)
 - monkey-patching discord
 - admin-утилиты (is_admin, resolve_targets, …)
 - autocomplete-функции
 - poker/cards утилиты
 - treasure-утилиты (run_treasure_map_event, …)
 - каналы и welcome-сообщения
 - логирование на сервер (send_guild_log)
"""

import asyncio
import logging
import math
import os
import random
import re

import discord
from discord import app_commands

from src.constants import (
    CHANNELS_FILE, TREASURE_BANNER_FILE, ROLE_IMAGE_FILE, ROLE_IMAGE_ATTACHMENT_NAME,
    BALANCE_IMAGE_FILE, BALANCE_IMAGE_ATTACHMENT_NAME,
    BOT_EMBED_COLOR, ADMIN_COMMAND_NAMES, ALL_TARGET_ALIASES,
    CARD_RANKS, CARD_SUITS, POKER_HAND_NAMES,
    TREASURE_MAPS_PER_DROP, EXCAVATION_REWARD_CHANCE,
    ROLE_DEFINITIONS,
)


# ──────────────────────────────────────────────────────────────
#  ЛЕНИВЫЙ ДОСТУП К ГЛОБАЛЬНОМУ СОСТОЯНИЮ
# ──────────────────────────────────────────────────────────────

def _state():
    from src import state
    return state


# ──────────────────────────────────────────────────────────────
#  EMBED-ХЕЛПЕРЫ
# ──────────────────────────────────────────────────────────────

def build_bot_embed(title: str, description: str, color=BOT_EMBED_COLOR) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


async def send_embed_response(
    interaction: discord.Interaction,
    title:        str,
    description:  str,
    *,
    ephemeral: bool = False,
    color=BOT_EMBED_COLOR,
    view=None,
    file=None,
):
    embed  = build_bot_embed(title, description, color=color)
    kwargs = {"embed": embed, "ephemeral": ephemeral}
    if view is not None: kwargs["view"] = view
    if file is not None: kwargs["file"] = file
    await interaction.response.send_message(**kwargs)


async def send_embed_followup(
    interaction:  discord.Interaction,
    title:        str,
    description:  str,
    *,
    ephemeral: bool = False,
    color=BOT_EMBED_COLOR,
    view=None,
    wait: bool = False,
):
    embed  = build_bot_embed(title, description, color=color)
    kwargs = {"embed": embed, "ephemeral": ephemeral, "wait": wait}
    if view is not None: kwargs["view"] = view
    return await interaction.followup.send(**kwargs)


async def send_loading_then_edit(
    interaction:  discord.Interaction,
    loading_text: str,
    embed:        discord.Embed,
    *,
    view=None,
    file=None,
    ephemeral: bool = False,
    delay: int = 2,
):
    loading_embed = build_bot_embed(
        "Ожидание",
        f":hourglass_flowing_sand: {loading_text}",
        color=discord.Color.dark_gold(),
    )
    send_kwargs = {"embed": loading_embed, "ephemeral": ephemeral}
    if file is not None: send_kwargs["file"] = file
    await interaction.response.send_message(**send_kwargs)
    await asyncio.sleep(delay)

    edit_kwargs = {"embed": embed}
    if view is not None: edit_kwargs["view"] = view
    await interaction.edit_original_response(**edit_kwargs)


# ──────────────────────────────────────────────────────────────
#  MONKEY-PATCHING DISCORD (авто-embed для plain-text ответов)
# ──────────────────────────────────────────────────────────────

_original_interaction_send_message = discord.InteractionResponse.send_message
_original_webhook_send             = discord.Webhook.send


async def _embed_interaction_send_message(self, content=None, *args, **kwargs):
    if content is not None and kwargs.get("embed") is None and kwargs.get("embeds") is None:
        kwargs["embed"] = build_bot_embed("Сообщение", str(content))
        content = None
    return await _original_interaction_send_message(self, content, *args, **kwargs)


async def _embed_webhook_send(self, content=None, *args, **kwargs):
    if content is not None and kwargs.get("embed") is None and kwargs.get("embeds") is None:
        kwargs["embed"] = build_bot_embed("Сообщение", str(content))
        content = None
    return await _original_webhook_send(self, content, *args, **kwargs)


def apply_discord_embed_patch():
    """Вызвать один раз при запуске бота."""
    discord.InteractionResponse.send_message = _embed_interaction_send_message
    discord.Webhook.send                     = _embed_webhook_send


# ──────────────────────────────────────────────────────────────
#  ЛОГИРОВАНИЕ СОБЫТИЙ НА СЕРВЕР
# ──────────────────────────────────────────────────────────────

async def send_guild_log(
    guild,
    event_key:   str,
    description: str,
    color=discord.Color.dark_grey(),
):
    from src.economy_store import set_economy_guild_id, reset_economy_guild_id, now_local
    token = set_economy_guild_id(guild.id)
    try:
        data = _state().economy_data.current()
        if not data.get("logs_channel_id"):
            return
        log_flags = {
            "join":        "log_join",
            "leave":       "log_leave",
            "ban":         "log_ban",
            "unban":       "log_ban",
            "delete":      "log_delete",
            "edit":        "log_edit",
            "voice_join":  "log_voice",
            "voice_leave": "log_voice",
            "command":     "log_commands",
        }
        flag = log_flags.get(event_key)
        if flag and not data.get(flag):
            return
        channel = guild.get_channel(int(data["logs_channel_id"]))
        if not channel:
            return
        titles = {
            "join":        "Участник присоединился",
            "leave":       "Участник вышел",
            "ban":         "Участник забанен",
            "unban":       "Участник разбанен",
            "delete":      "Сообщение удалено",
            "edit":        "Сообщение изменено",
            "voice_join":  "Вход в голосовой канал",
            "voice_leave": "Выход из голосового канала",
            "command":     "Команда использована",
        }
        embed = discord.Embed(
            title=       titles.get(event_key, "Событие"),
            description= description,
            color=       color,
            timestamp=   now_local(),
        )
        await channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to send guild log: {e}")
    finally:
        reset_economy_guild_id(token)


# ──────────────────────────────────────────────────────────────
#  КАНАЛЫ ДЛЯ ТРЕДОВ
# ──────────────────────────────────────────────────────────────

def load_channels() -> set:
    if not os.path.exists(CHANNELS_FILE):
        return set()
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        return {int(line.strip()) for line in f if line.strip().isdigit()}


def save_channels(channels_set: set):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        for channel_id in channels_set:
            f.write(f"{channel_id}\n")


def get_guild_thread_channel_ids(guild_id) -> set:
    from src.economy_store import save_economy
    data        = _state().economy_data.guild_data(guild_id)
    channel_ids = set()
    for raw_id in data.get("thread_channel_ids") or []:
        try:
            channel_ids.add(int(raw_id))
        except (TypeError, ValueError):
            continue
    return channel_ids


def set_guild_thread_channel_ids(guild_id, channel_ids: set):
    from src.economy_store import save_economy
    data = _state().economy_data.guild_data(guild_id)
    data["thread_channel_ids"] = sorted({int(c) for c in channel_ids})
    save_economy()


# ──────────────────────────────────────────────────────────────
#  WELCOME / FAREWELL
# ──────────────────────────────────────────────────────────────

def format_welcome_message(template, member) -> str:
    text = template or "Добро пожаловать, {mention}!"
    return (
        text
        .replace("{mention}", member.mention)
        .replace("{user}",    member.display_name)
        .replace("{server}",  member.guild.name)
        .replace("{count}",   str(member.guild.member_count or "?"))
    )


# ──────────────────────────────────────────────────────────────
#  ADMIN-УТИЛИТЫ
# ──────────────────────────────────────────────────────────────

def is_admin_interaction(interaction: discord.Interaction) -> bool:
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


async def ensure_admin_interaction(interaction: discord.Interaction) -> bool:
    if is_admin_interaction(interaction):
        return True
    message = "У вас недостаточно прав. Требуется право Администратор."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
    return False


def is_all_target(value) -> bool:
    return str(value).strip().casefold() in ALL_TARGET_ALIASES


def is_valid_amount(amount) -> bool:
    return math.isfinite(amount) and amount > 0


def set_non_negative(account: dict, key: str, value):
    account[key] = max(0.0, float(value))


def parse_member_id(value) -> int | None:
    text = str(value).strip()
    match = re.fullmatch(r"<@!?(\d{15,25})>", text)
    if match:
        return int(match.group(1))
    if text.isdigit():
        return int(text)
    return None


async def resolve_member_text(interaction: discord.Interaction, value):
    if isinstance(value, discord.Member):
        return value
    if interaction.guild is None:
        return None
    text      = str(value).strip()
    member_id = parse_member_id(text)
    if member_id is not None:
        member = interaction.guild.get_member(member_id)
        if member is not None:
            return member
        try:
            return await interaction.guild.fetch_member(member_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
    normalized = text.casefold()
    for member in interaction.guild.members:
        names = {
            member.name.casefold(),
            member.display_name.casefold(),
            str(member).casefold(),
        }
        global_name = getattr(member, "global_name", None)
        if global_name:
            names.add(global_name.casefold())
        if normalized in names:
            return member
    return None


async def resolve_admin_targets(interaction: discord.Interaction, value):
    """Возвращает (members_list, is_all, error_message)."""
    from src.xp_utils import format_integer
    if is_all_target(value):
        if interaction.guild is None:
            return [], True, "Команда `all` доступна только на сервере."
        members = [m for m in interaction.guild.members if not m.bot]
        if not members:
            return [], True, "Не нашёл участников для массовой операции."
        return members, True, None
    member = await resolve_member_text(interaction, value)
    if member is None:
        return [], False, "Не нашёл участника. Укажите `all`, ID, упоминание или точное имя."
    return [member], False, None


def format_target_result(targets, is_all) -> str:
    from src.xp_utils import format_integer
    if is_all:
        return f"**{format_integer(len(targets))} участников**"
    return targets[0].mention


# ──────────────────────────────────────────────────────────────
#  AUTOCOMPLETE
# ──────────────────────────────────────────────────────────────

async def role_key_autocomplete(interaction: discord.Interaction, current: str):
    from src.role_utils import normalize_role_name
    normalized = normalize_role_name(current)
    choices    = []
    for rd in ROLE_DEFINITIONS:
        search_values = [rd["key"], rd["name"], *rd.get("aliases", [])]
        if normalized and not any(
            normalized in normalize_role_name(v) for v in search_values
        ):
            continue
        choices.append(
            app_commands.Choice(
                name=  f"{rd['emoji']} {rd['name']}",
                value= rd["key"],
            )
        )
    return choices[:25]


async def role_name_autocomplete(interaction: discord.Interaction, current: str):
    from src.role_utils import normalize_role_name
    normalized = normalize_role_name(current)
    choices    = []
    for rd in ROLE_DEFINITIONS:
        search_values = [rd["key"], rd["name"], *rd.get("aliases", [])]
        if normalized and not any(
            normalized in normalize_role_name(v) for v in search_values
        ):
            continue
        choices.append(
            app_commands.Choice(
                name=  f"{rd['emoji']} {rd['name']}",
                value= rd["name"],
            )
        )
    guild = interaction.guild
    if guild is not None:
        existing = {c.value.casefold() for c in choices}
        for role in guild.roles:
            if normalized and normalized not in normalize_role_name(role.name):
                continue
            if role.name.casefold() in existing or role.is_default():
                continue
            choices.append(app_commands.Choice(name=role.name[:100], value=role.name))
            if len(choices) >= 25:
                break
    return choices[:25]


async def emoji_target_autocomplete(interaction: discord.Interaction, current: str):
    from src.role_utils import normalize_role_name
    from src.constants import EMOJI_TARGETS
    normalized = normalize_role_name(current)
    matches    = []
    for name, value in EMOJI_TARGETS:
        if normalized and normalized not in normalize_role_name(name) and normalized not in value:
            continue
        matches.append(app_commands.Choice(name=name, value=value))
    return matches[:25]


# ──────────────────────────────────────────────────────────────
#  КАЗИНО / КАРТЫ
# ──────────────────────────────────────────────────────────────

def validate_bet(amount) -> tuple[float, str | None]:
    if amount is None:
        return 0.0, None
    if not math.isfinite(amount) or amount < 0:
        return 0.0, "Ставка должна быть числом от нуля и выше."
    return round(float(amount), 2), None


def build_card_deck() -> list:
    return [(rank, suit) for suit in CARD_SUITS for rank in CARD_RANKS]


def format_card(card) -> str:
    from src.card_emojis import format_card_emoji
    return format_card_emoji(card)


def format_cards(cards) -> str:
    return " ".join(format_card(c) for c in cards)


def card_rank_value(rank: str) -> int:
    if rank == "A": return 14
    if rank == "K": return 13
    if rank == "Q": return 12
    if rank == "J": return 11
    return int(rank)


def evaluate_poker_hand(cards) -> tuple:
    values       = sorted((card_rank_value(r) for r, _ in cards), reverse=True)
    suits        = [s for _, s in cards]
    counts       = {v: values.count(v) for v in set(values)}
    grouped      = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    unique_values = sorted(set(values), reverse=True)
    is_flush     = len(set(suits)) == 1
    is_wheel     = set(values) == {14, 5, 4, 3, 2}
    is_straight  = len(unique_values) == 5 and (
        unique_values[0] - unique_values[-1] == 4 or is_wheel
    )
    straight_high = 5 if is_wheel else unique_values[0]

    if is_straight and is_flush:
        score = (8, [straight_high])
    elif grouped[0][1] == 4:
        score = (7, [grouped[0][0], grouped[1][0]])
    elif grouped[0][1] == 3 and grouped[1][1] == 2:
        score = (6, [grouped[0][0], grouped[1][0]])
    elif is_flush:
        score = (5, values)
    elif is_straight:
        score = (4, [straight_high])
    elif grouped[0][1] == 3:
        kickers = sorted([v for v in values if v != grouped[0][0]], reverse=True)
        score   = (3, [grouped[0][0], *kickers])
    elif grouped[0][1] == 2 and grouped[1][1] == 2:
        pairs   = sorted([v for v, c in grouped if c == 2], reverse=True)
        kicker  = max(v for v, c in grouped if c == 1)
        score   = (2, [*pairs, kicker])
    elif grouped[0][1] == 2:
        pair    = grouped[0][0]
        kickers = sorted([v for v in values if v != pair], reverse=True)
        score   = (1, [pair, *kickers])
    else:
        score = (0, values)

    return score, POKER_HAND_NAMES[score[0]]


# ──────────────────────────────────────────────────────────────
#  ФАЙЛЫ (изображения)
# ──────────────────────────────────────────────────────────────

def get_treasure_banner_file() -> discord.File | None:
    if not os.path.exists(TREASURE_BANNER_FILE):
        return None
    return discord.File(TREASURE_BANNER_FILE, filename=TREASURE_BANNER_FILE)


def get_role_image_file() -> discord.File | None:
    if not os.path.exists(ROLE_IMAGE_FILE):
        return None
    return discord.File(ROLE_IMAGE_FILE, filename=ROLE_IMAGE_ATTACHMENT_NAME)


def get_balance_image_file() -> discord.File | None:
    if not os.path.exists(BALANCE_IMAGE_FILE):
        return None
    return discord.File(BALANCE_IMAGE_FILE, filename=BALANCE_IMAGE_ATTACHMENT_NAME)


# ──────────────────────────────────────────────────────────────
#  TREASURE: ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ──────────────────────────────────────────────────────────────

def normalize_treasure_maps(account: dict) -> int:
    try:
        account["treasure_maps"] = max(0, int(account.get("treasure_maps", 0)))
    except (TypeError, ValueError):
        account["treasure_maps"] = 0
    return account["treasure_maps"]


def grant_treasure_maps_to_all(amount: int, guild=None) -> int:
    from src.economy_store import get_account
    granted    = 0
    player_ids = {
        user_id
        for user_id, account in _state().economy_data["users"].items()
        if isinstance(account, dict)
    }
    if guild is not None:
        player_ids.update(str(m.id) for m in guild.members if not m.bot)
    for user_id in player_ids:
        account = get_account(user_id)
        normalize_treasure_maps(account)
        account["treasure_maps"] += amount
        granted += 1
    return granted


def build_treasure_drop_embed(granted_count: int, amount: int) -> discord.Embed:
    from src.xp_utils import format_integer
    from src.formatters import format_treasure_maps
    embed = discord.Embed(
        title=       "Посылка на почте",
        description= (
            'Вам на почту пришёл документ с подписью **"от старого приятеля"**. '
            "Открывая конверт, вы находите в нём карту сокровищ!\n\n"
            "Используйте `/excavation`, чтобы отправиться на раскопки."
        ),
        color=       discord.Color.gold(),
    )
    embed.add_field(name="Получили",    value=f"**{format_integer(granted_count)} игроков**", inline=True)
    embed.add_field(name="Выдано каждому", value=f"**{format_treasure_maps(amount)}**", inline=True)
    embed.add_field(name="Команда",     value="`/excavation`", inline=True)
    embed.set_footer(text="Ежедневная выдача в 12:00 по МСК")
    if os.path.exists(TREASURE_BANNER_FILE):
        embed.set_image(url=f"attachment://{TREASURE_BANNER_FILE}")
    return embed


async def resolve_treasure_channel():
    channel_id = _state().economy_data.get("treasure_channel_id")
    if not channel_id:
        return None
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return None
    channel = _state().bot.get_channel(channel_id)
    if channel is not None:
        return channel
    try:
        return await _state().bot.fetch_channel(channel_id)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return None


async def send_treasure_drop_announcement(channel, granted_count: int, amount: int):
    embed  = build_treasure_drop_embed(granted_count, amount)
    banner = get_treasure_banner_file()
    if banner:
        await channel.send(embed=embed, file=banner)
    else:
        await channel.send(embed=embed)


async def run_treasure_map_event(
    amount: int = TREASURE_MAPS_PER_DROP,
    scheduled: bool = False,
    guild=None,
):
    from src.economy_store import today_msk_iso, update_gold_rate, save_economy
    scheduled_date = today_msk_iso()
    channel        = await resolve_treasure_channel()
    target_guild   = guild or getattr(channel, "guild", None)

    async with _state().economy_lock:
        if scheduled and _state().economy_data.get("last_treasure_map_drop_date") == scheduled_date:
            return 0, None, True

        update_gold_rate()
        granted_count = grant_treasure_maps_to_all(amount, guild=target_guild)

        if scheduled:
            _state().economy_data["last_treasure_map_drop_date"] = scheduled_date

        save_economy()

    if channel is not None:
        await send_treasure_drop_announcement(channel, granted_count, amount)

    return granted_count, channel, False


# ──────────────────────────────────────────────────────────────
#  TREASURE: EMBED-СТРОИТЕЛИ
# ──────────────────────────────────────────────────────────────

def build_treasure_hunt_embed(user, remaining_maps, attempts_left: int = 2, note=None) -> discord.Embed:
    from src.formatters import format_treasure_maps
    from emoji_config import DEFAULT_TREASURE_DIG_EMOJI
    description = (
        f"{user.mention}, карта привела вас к трём подозрительным местам.\n"
        f"Клад спрятан только под одной кнопкой. Попыток: **{attempts_left}**.\n"
        f"Карт осталось: **{format_treasure_maps(remaining_maps)}**."
    )
    if note:
        description += f"\n\n{note}"
    embed = build_bot_embed("Раскопки", description, color=discord.Color.dark_gold())
    if os.path.exists(TREASURE_BANNER_FILE):
        embed.set_image(url=f"attachment://{TREASURE_BANNER_FILE}")
    return embed


def build_treasure_result_embed(user, title: str, description: str) -> discord.Embed:
    embed = build_bot_embed(
        title,
        f"{user.mention}, {description}",
        color=discord.Color.gold(),
    )
    if os.path.exists(TREASURE_BANNER_FILE):
        embed.set_image(url=f"attachment://{TREASURE_BANNER_FILE}")
    return embed


# ──────────────────────────────────────────────────────────────
#  BIND ECONOMY CONTEXT (interaction_check для bot.tree)
# ──────────────────────────────────────────────────────────────

async def bind_economy_context(interaction: discord.Interaction) -> bool:
    """Устанавливает guild-контекст и проверяет права перед каждой командой."""
    from src.economy_store import set_economy_guild_id
    import json

    set_economy_guild_id(interaction.guild_id)

    if interaction.type == discord.InteractionType.autocomplete:
        return True

    command_name = getattr(getattr(interaction, "command", None), "name", None)
    if command_name in ADMIN_COMMAND_NAMES and not is_admin_interaction(interaction):
        await ensure_admin_interaction(interaction)
        return False

    if interaction.guild and interaction.type == discord.InteractionType.application_command:
        if command_name != "command-chat":
            cog = _state().bot.get_cog("LevelingCog")
            if cog:
                guild_id  = str(interaction.guild.id)
                allow_all = cog.db.get_setting(guild_id, "allow_all_channels", "false") == "true"
                if not allow_all:
                    raw = cog.db.get_setting(guild_id, "command_channels", "[]")
                    try:
                        allowed = json.loads(raw)
                    except Exception:
                        allowed = []
                    if allowed and interaction.channel.id not in allowed:
                        channels_str = ", ".join(f"<#{c}>" for c in allowed)
                        await interaction.response.send_message(
                            f"Команды можно использовать только в этих каналах: {channels_str}",
                            ephemeral=True,
                        )
                        return False

    if interaction.guild and interaction.type == discord.InteractionType.application_command and command_name:
        asyncio.create_task(
            send_guild_log(
                interaction.guild,
                "command",
                f"{interaction.user.mention} использовал `/{command_name}` в {interaction.channel.mention}",
                color=discord.Color.blurple(),
            )
        )

    return True
