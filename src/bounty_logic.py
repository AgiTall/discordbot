import time
import math
import random
import json
import discord
from discord import app_commands
from src.xp_utils import *

BOUNTY_IMAGE_FILE = "assets/images/hunter.png"


BOUNTY_IMAGE_ATTACHMENT_NAME = "hunter.png"


DEFAULT_BOUNTY_BUTTON_EMOJIS = {
    "easy": "🎯",
    "medium": "⚔️",
    "hard": "🔥",
    "ambush": "🌵",
    "chase": "🐎",
    "negotiate": "🤝",
}


BOUNTY_ROLE_KEY = "bounty_hunter"


BOUNTY_COOLDOWN_SECONDS = 10 * 60


BOUNTY_MAX_LEVEL = 20


BOUNTY_DIFFICULTIES = {
    "easy": {
        "name": "Лёгкий контракт",
        "mod": 2,
        "reward_min": 70,
        "reward_max": 110,
        "gold": 0.05,
        "xp": 70,
        "targets": ["Карманник из Валентайна", "Пьяный налётчик", "Беглый конокрад"],
    },
    "medium": {
        "name": "Опасный преступник",
        "mod": 5,
        "reward_min": 130,
        "reward_max": 210,
        "gold": 0.12,
        "xp": 130,
        "targets": ["Главарь шайки", "Грабитель дилижансов", "Поджигатель складов"],
    },
    "hard": {
        "name": "Легендарная цель",
        "mod": 8,
        "reward_min": 240,
        "reward_max": 360,
        "gold": 0.25,
        "xp": 230,
        "targets": ["Чёрный стрелок", "Королева контрабандистов", "Мясник из каньона"],
    },
}


BOUNTY_TACTICS = {
    "ambush": {
        "name": "Засада",
        "mod": 2,
        "reward_multiplier": 1.0,
        "description": "+2 к броску, но при провале цель сразу сбегает.",
    },
    "chase": {
        "name": "Погоня",
        "mod": 0,
        "reward_multiplier": 1.0,
        "description": "Без модификатора, зато без штрафов к награде.",
    },
    "negotiate": {
        "name": "Переговоры",
        "mod": 1,
        "reward_multiplier": 0.8,
        "description": "+1 к броску, награда меньше на 20%.",
    },
}


def get_bounty_button_emoji(button_key):
    emojis = economy_data.get("bounty_button_emojis", {})
    emoji = emojis.get(button_key)
    if not emoji:
        return str(DEFAULT_BOUNTY_BUTTON_EMOJIS[button_key])
    return str(emoji)


def default_bounty_data():
    return {
        "level": 1,
        "xp": 0,
        "captures": 0,
        "escaped": 0,
        "last_bounty_at": None,
    }


def normalize_bounty_data(bounty):
    if not isinstance(bounty, dict):
        bounty = default_bounty_data()

    try:
        bounty["level"] = max(1, min(BOUNTY_MAX_LEVEL, int(bounty.get("level", 1))))
    except (TypeError, ValueError):
        bounty["level"] = 1
    try:
        bounty["xp"] = max(0, int(bounty.get("xp", 0)))
    except (TypeError, ValueError):
        bounty["xp"] = 0
    try:
        bounty["captures"] = max(0, int(bounty.get("captures", 0)))
    except (TypeError, ValueError):
        bounty["captures"] = 0
    try:
        bounty["escaped"] = max(0, int(bounty.get("escaped", 0)))
    except (TypeError, ValueError):
        bounty["escaped"] = 0
    bounty.setdefault("last_bounty_at", None)
    return bounty


def get_bounty_account(account):
    account["bounty"] = normalize_bounty_data(account.get("bounty"))
    return account["bounty"]


def get_bounty_cooldown(bounty):
    last_bounty_at = bounty.get("last_bounty_at")
    if not last_bounty_at:
        return 0
    seconds_passed = (now_local() - parse_local_datetime(last_bounty_at)).total_seconds()
    return max(0, BOUNTY_COOLDOWN_SECONDS - seconds_passed)


def format_bounty_short(account):
    bounty = get_bounty_account(account)
    needed = xp_for_next_level(bounty["level"], 140)
    return (
        f"уровень {bounty['level']}, опыт {bounty['xp']}/{needed}, "
        f"поймано {format_integer(bounty['captures'])}"
    )


def get_bounty_image_file():
    if not os.path.exists(BOUNTY_IMAGE_FILE):
        return None
    return discord.File(BOUNTY_IMAGE_FILE, filename=BOUNTY_IMAGE_ATTACHMENT_NAME)


def build_bounty_embed(guild, account):
    bounty = get_bounty_account(account)
    role_definition = get_role_definition(BOUNTY_ROLE_KEY)
    role = find_guild_role(guild, role_definition)
    icon = get_role_icon(role_definition, role)
    needed = xp_for_next_level(bounty["level"], 140)
    cooldown = get_bounty_cooldown(bounty)
    cooldown_text = "готов к контракту" if cooldown <= 0 else format_duration(cooldown)
    embed = discord.Embed(
        title=f"{icon} Охотник за головами",
        description=(
            "Выберите сложность контракта, затем тактику поимки.\n\n"
            "📜 Прогресс\n"
            f"├─ Уровень: **{bounty['level']}/{BOUNTY_MAX_LEVEL}**\n"
            f"├─ Опыт: **{bounty['xp']}/{needed}**\n"
            f"├─ Поймано: **{format_integer(bounty['captures'])}**\n"
            f"├─ Сбежало: **{format_integer(bounty['escaped'])}**\n"
            f"└─ Кулдаун: **{cooldown_text}**"
        ),
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(BOUNTY_IMAGE_FILE):
        embed.set_image(url=f"attachment://{BOUNTY_IMAGE_ATTACHMENT_NAME}")
    return embed

