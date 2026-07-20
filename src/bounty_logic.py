import time
import math
import random
import json
import discord
from discord import app_commands
from src.xp_utils import *
from emoji_config import (
    EMOJI_LEVEL,
    EMOJI_LIST,
    EMOJI_MEMBERS,
    EMOJI_ROLE_BOUNTY_HUNTER,
    EMOJI_SEARCH,
    EMOJI_TROPHY,
    EMOJI_WEAPON,
)

BOUNTY_IMAGE_FILE = "assets/images/hunter.png"


BOUNTY_IMAGE_ATTACHMENT_NAME = "hunter.png"


DEFAULT_BOUNTY_BUTTON_EMOJIS = {
    "cheap":      EMOJI_SEARCH,
    "medium":     EMOJI_WEAPON,
    "expensive":  EMOJI_TROPHY,
    "legendary":  EMOJI_ROLE_BOUNTY_HUNTER,
    "leaderboard": EMOJI_MEMBERS,
}


BOUNTY_ROLE_KEY = "bounty_hunter"


BOUNTY_COOLDOWN_SECONDS = 10 * 60


BOUNTY_MAX_LEVEL = 20


# ---------------------------------------------------------------------------
# Цели (уровни преступников)
# ---------------------------------------------------------------------------
BOUNTY_TARGETS = {
    "cheap": {
        "name": "Дешёвый $ преступник",
        "label": "$",
        "base_chance": 55,          # базовый шанс поимки (%)
        "reward_min": 80,
        "reward_max": 120,
        "gold": 0.05,
        "xp": 70,
        "targets": ["Карманник из Валентайна", "Пьяный налётчик", "Беглый конокрад", "Мелкий жулик"],
    },
    "medium": {
        "name": "Средний $$ преступник",
        "label": "$$",
        "base_chance": 40,
        "reward_min": 160,
        "reward_max": 230,
        "gold": 0.12,
        "xp": 130,
        "targets": ["Главарь шайки", "Грабитель дилижансов", "Поджигатель складов", "Беглый бандит"],
    },
    "expensive": {
        "name": "Дорогой $$$ преступник",
        "label": "$$$",
        "base_chance": 25,
        "reward_min": 300,
        "reward_max": 420,
        "gold": 0.25,
        "xp": 230,
        "targets": ["Чёрный стрелок", "Королева контрабандистов", "Мясник из каньона", "Беглый наёмный убийца"],
    },
    "legendary": {
        "name": "Легендарный ★ преступник",
        "label": "★",
        "base_chance": 15,
        "reward_min": 600,
        "reward_max": 900,
        "gold": 0.60,
        "xp": 450,
        "targets": ["Призрак Дикого Запада", "Проклятый Торговец Смертью", "Демон Приграничья", "Бессмертный Стрелок"],
    },
}

# ---------------------------------------------------------------------------
# Бонусы к шансу от класса оружия (%)
# ---------------------------------------------------------------------------
WEAPON_CLASS_CHANCE_BONUS = {
    "revolver":  5,
    "pistol":    5,
    "shotgun":   10,
    "repeater":  15,
    "rifle":     20,
}

# ---------------------------------------------------------------------------
# Бонусы к шансу от типа патронов (%)
# ---------------------------------------------------------------------------
AMMO_CHANCE_BONUS = {
    "normal":        0,
    "split_point":   3,
    "high_velocity": 5,
    "express":       5,
    "explosive":     8,
}

# ---------------------------------------------------------------------------
# Бонус к шансу от состояния оружия (%)
# ---------------------------------------------------------------------------
def condition_chance_bonus(condition: float) -> int:
    """Возвращает бонус к шансу поимки в зависимости от состояния оружия."""
    if condition >= 80:
        return 5
    if condition >= 50:
        return 0
    return -8


def calculate_catch_chance(target_key: str, shot: dict, level: int) -> int:
    """Рассчитывает итоговый шанс поимки (%) с учётом оружия, патронов и уровня."""
    target = BOUNTY_TARGETS[target_key]
    base = target["base_chance"]

    weapon_bonus = WEAPON_CLASS_CHANCE_BONUS.get(shot["class"], 5)
    ammo_bonus = AMMO_CHANCE_BONUS.get(shot["ammo_type"], 0)
    cond_bonus = condition_chance_bonus(shot["condition_before"])
    level_bonus = level // 5  # +1% за каждые 5 уровней

    total = base + weapon_bonus + ammo_bonus + cond_bonus + level_bonus
    return max(5, min(95, total))  # ограничиваем 5–95%


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

    # Показываем шансы поимки для ориентира (без учёта оружия — базовые)
    chances_lines = []
    for key, t in BOUNTY_TARGETS.items():
        chances_lines.append(
            f"├─ {t['name']}: базовый шанс **{t['base_chance']}%** (+оружие/патроны)"
        )
    chances_lines[-1] = chances_lines[-1].replace("├─", "└─")

    embed = discord.Embed(
        title=f"{icon} Охотник за головами",
        description=(
            "Выберите уровень преступника. Шанс поимки зависит от вашего **оружия** и **патронов**.\n\n"
            f"{EMOJI_LIST} Прогресс\n"
            f"├─ Уровень: **{bounty['level']}/{BOUNTY_MAX_LEVEL}**\n"
            f"├─ Опыт: **{bounty['xp']}/{needed}**\n"
            f"├─ Поймано: **{format_integer(bounty['captures'])}**\n"
            f"├─ Сбежало: **{format_integer(bounty['escaped'])}**\n"
            f"└─ Кулдаун: **{cooldown_text}**\n\n"
            f"{EMOJI_WEAPON} Шансы поимки\n"
            + "\n".join(chances_lines)
        ),
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(BOUNTY_IMAGE_FILE):
        embed.set_image(url=f"attachment://{BOUNTY_IMAGE_ATTACHMENT_NAME}")
    return embed
