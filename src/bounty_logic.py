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


BOUNTY_BASE_MAX_LEVEL = 20
BOUNTY_MAX_LEVEL = 30
PRESTIGIOUS_LICENSE_PRICE = 15.0
BOUNTY_WAGON_PRICE = 875.0


LEGENDARY_BOUNTIES = (
    {"name": "Вирджил «Пастырь» Эдвардс", "reward_min": 150.0, "reward_max": 225.0},
    {"name": "Джин «Бо» Финли", "reward_min": 125.0, "reward_max": 187.50},
    {"name": "Кармела «Куколка» Монтес", "reward_min": 125.0, "reward_max": 187.50},
    {"name": "Филипп Карлье", "reward_min": 125.0, "reward_max": 187.50},
    {"name": "Волк", "reward_min": 100.0, "reward_max": 150.0},
    {"name": "Сесил С. Такер", "reward_min": 100.0, "reward_max": 150.0},
    {"name": "Николай «Юконский» Бородин", "reward_min": 125.0, "reward_max": 187.50},
    {"name": "Барбарелла Алькасар", "reward_min": 100.0, "reward_max": 150.0},
    {"name": "Этта Дойл", "reward_min": 150.0, "reward_max": 225.0},
    {"name": "Семейка Филинов", "reward_min": 125.0, "reward_max": 187.50},
    {"name": "Серджо Винченца", "reward_min": 125.0, "reward_max": 187.50},
    {"name": "Тобин Уинфилд", "reward_min": 150.0, "reward_max": 225.0},
    {"name": "Красный Бен Клемпсон", "reward_min": 150.0, "reward_max": 225.0},
)


# ---------------------------------------------------------------------------
# Цели (уровни преступников)
# ---------------------------------------------------------------------------
BOUNTY_TARGETS = {
    "cheap": {
        "name": "Дешёвый $ преступник",
        "label": "$",
        "target_count": (1, 2),
        "base_chance": 55,          # базовый шанс поимки (%)
        "reward_min": 30.0,
        "reward_max": 50.0,
        "gold": 0.08,
        "xp": 450,
        "targets": ["Карманник из Валентайна", "Пьяный налётчик", "Беглый конокрад", "Мелкий жулик"],
    },
    "medium": {
        "name": "Средний $$ преступник",
        "label": "$$",
        "target_count": (1, 4),
        "base_chance": 40,
        "reward_min": 37.50,
        "reward_max": 75.0,
        "gold": 0.08,
        "xp": 700,
        "targets": ["Главарь шайки", "Грабитель дилижансов", "Поджигатель складов", "Беглый бандит"],
    },
    "expensive": {
        "name": "Дорогой $$$ преступник",
        "label": "$$$",
        "target_count": (1, 6),
        "base_chance": 25,
        "reward_min": 45.0,
        "reward_max": 90.0,
        "gold": 0.08,
        "xp": 900,
        "targets": ["Чёрный стрелок", "Королева контрабандистов", "Мясник из каньона", "Беглый наёмный убийца"],
    },
    "legendary": {
        "name": "Легендарный $$$$ преступник",
        "label": "$$$$",
        "target_count": (1, 6),
        "base_chance": 15,
        "reward_min": 100.0,
        "reward_max": 225.0,
        "gold": 0.24,
        "xp": 1000,
        "targets": [bounty["name"] for bounty in LEGENDARY_BOUNTIES],
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


def calculate_catch_chance(target_key: str, shot: dict, level: int = 1) -> int:
    """Рассчитывает итоговый шанс без привязки к уровню профессии."""
    target = BOUNTY_TARGETS[target_key]
    base = target["base_chance"]

    weapon_bonus = WEAPON_CLASS_CHANCE_BONUS.get(shot["class"], 5)
    ammo_bonus = AMMO_CHANCE_BONUS.get(shot["ammo_type"], 0)
    cond_bonus = condition_chance_bonus(shot["condition_before"])
    total = base + weapon_bonus + ammo_bonus + cond_bonus
    return max(5, min(95, total))  # ограничиваем 5–95%


def bounty_level_cap(bounty):
    return BOUNTY_MAX_LEVEL if bounty.get("prestigious_license") else BOUNTY_BASE_MAX_LEVEL


def simple_bounty_target_key(bounty):
    """Return the best contract tier; profession levels do not gate contracts."""
    if bounty.get("prestigious_license"):
        return "legendary"
    return "expensive"


def roll_bounty_contract(target_key, rng=None):
    rng = rng or random
    target = BOUNTY_TARGETS[target_key]
    target_count = rng.randint(*target["target_count"])
    if target_key == "legendary":
        selected = rng.choice(LEGENDARY_BOUNTIES)
        reward_min = selected["reward_min"]
        reward_max = selected["reward_max"]
        target_name = selected["name"]
    else:
        reward_min = target["reward_min"]
        reward_max = target["reward_max"]
        target_name = rng.choice(target["targets"])
    reward = round(rng.uniform(reward_min, reward_max), 2)
    return {
        "name": target_name,
        "count": target_count,
        "reward": reward,
        "reward_min": reward_min,
        "reward_max": reward_max,
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
        "prestigious_license": False,
        "has_bounty_wagon": False,
        "last_bounty_at": None,
    }


def normalize_bounty_data(bounty):
    if not isinstance(bounty, dict):
        bounty = default_bounty_data()

    bounty["prestigious_license"] = bool(bounty.get("prestigious_license", False))
    bounty["has_bounty_wagon"] = bool(bounty.get("has_bounty_wagon", False))
    try:
        bounty["level"] = max(1, min(bounty_level_cap(bounty), int(bounty.get("level", 1))))
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
    return f"поймано {format_integer(bounty['captures'])}"


def get_bounty_image_file():
    if not os.path.exists(BOUNTY_IMAGE_FILE):
        return None
    return discord.File(BOUNTY_IMAGE_FILE, filename=BOUNTY_IMAGE_ATTACHMENT_NAME)


def build_bounty_embed(guild, account):
    bounty = get_bounty_account(account)
    role_definition = get_role_definition(BOUNTY_ROLE_KEY)
    role = find_guild_role(guild, role_definition)
    icon = get_role_icon(role_definition, role)
    cooldown = get_bounty_cooldown(bounty)
    cooldown_text = "готов к контракту" if cooldown <= 0 else format_duration(cooldown)

    target = BOUNTY_TARGETS[simple_bounty_target_key(bounty)]
    count_min, count_max = target["target_count"]

    embed = discord.Embed(
        title=f"{icon} Охотник за головами",
        description=(
            "Нажмите **«Взять контракт»** — подходящая цель выбирается автоматически.\n\n"
            f"{EMOJI_LIST} Прогресс\n"
            f"├─ Поймано: **{format_integer(bounty['captures'])}**\n"
            f"├─ Сбежало: **{format_integer(bounty['escaped'])}**\n"
            f"└─ Кулдаун: **{cooldown_text}**\n\n"
            f"{EMOJI_TROPHY} Улучшение\n"
            f"└─ Знаменитая лицензия: **{'куплена' if bounty['prestigious_license'] else 'не куплена'}**\n\n"
            f"{EMOJI_WEAPON} Текущий контракт\n"
            f"└─ {target['label']}: **{count_min}–{count_max} целей**, "
            f"**${target['reward_min']:g}–{target['reward_max']:g}**, "
            f"**{format_gold(target['gold'])}**"
        ),
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(BOUNTY_IMAGE_FILE):
        embed.set_image(url=f"attachment://{BOUNTY_IMAGE_ATTACHMENT_NAME}")
    return embed
