import time
import math
import random
import json
import discord
from discord import app_commands
from src.xp_utils import *
from emoji_config import *


NATURALIST_IMAGE_FILE = "assets/images/naturalist.png"


NATURALIST_IMAGE_ATTACHMENT_NAME = "naturalist.png"


NATURALIST_ROLE_KEY = "naturalist"


NATURALIST_MAX_LEVEL = 20


NATURALIST_SAMPLE_COOLDOWN_SECONDS = 5 * 60


NATURALIST_LEGENDARY_COOLDOWN_SECONDS = 60 * 60

# ---------------------------------------------------------------------------
# Снаряжение — ключи предметов каталога
# ---------------------------------------------------------------------------
NATURALIST_VARMINT_KEY = "rifle_varmint"   # Варминт-винтовка
NATURALIST_REVIVER_KEY = "reviver"         # Оживитель
NATURALIST_DART_KEY    = "sleeping_dart"   # Снотворная стрела

# Бонусы к шансу поимки (%) за наличие снаряжения
NATURALIST_VARMINT_BONUS  = 20   # варминт-винтовка в loadout
NATURALIST_REVIVER_BONUS  = 10   # ≥1 оживителя в инвентаре
NATURALIST_DART_BONUS     = 15   # ≥1 снотворной стрелы в инвентаре

NATURALIST_REGIONS = {
    "forest":    {"name": "Лес",      "emoji": "🌲"},
    "mountains": {"name": "Горы",     "emoji": "⛰️"},
    "wetlands":  {"name": "Болота",   "emoji": "💧"},
    "desert":    {"name": "Пустыня",  "emoji": "🏜️"},
}

# ---------------------------------------------------------------------------
# Животные — базовые шансы снижены, зато снаряжение их поднимает выше старых.
# Награды увеличены ~×2.
# ---------------------------------------------------------------------------
ANIMALS = {
    "rabbit":    {"name": "Кролик",         "region": "forest",    "base_chance": 0.60, "cash": 5.0,  "xp": 30},
    "deer":      {"name": "Олень",          "region": "forest",    "base_chance": 0.50, "cash": 8.0,  "xp": 50},
    "fox":       {"name": "Лиса",           "region": "forest",    "base_chance": 0.45, "cash": 9.0,  "xp": 55},
    "wolf":      {"name": "Волк",           "region": "forest",    "base_chance": 0.40, "cash": 14.0, "xp": 80},
    "bighorn":   {"name": "Горный баран",   "region": "mountains", "base_chance": 0.45, "cash": 9.0,  "xp": 60},
    "eagle":     {"name": "Орёл",           "region": "mountains", "base_chance": 0.40, "cash": 11.0, "xp": 70},
    "moose":     {"name": "Лось",           "region": "mountains", "base_chance": 0.35, "cash": 20.0, "xp": 110},
    "bear":      {"name": "Медведь",        "region": "mountains", "base_chance": 0.30, "cash": 24.0, "xp": 130},
    "beaver":    {"name": "Бобр",           "region": "wetlands",  "base_chance": 0.50, "cash": 8.0,  "xp": 50},
    "frog":      {"name": "Лягушка",        "region": "wetlands",  "base_chance": 0.55, "cash": 4.0,  "xp": 25},
    "boar":      {"name": "Кабан",          "region": "wetlands",  "base_chance": 0.42, "cash": 11.0, "xp": 70},
    "alligator": {"name": "Аллигатор",      "region": "wetlands",  "base_chance": 0.32, "cash": 22.0, "xp": 120},
    "coyote":    {"name": "Койот",          "region": "desert",    "base_chance": 0.48, "cash": 8.0,  "xp": 50},
    "snake":     {"name": "Гремучая змея", "region": "desert",    "base_chance": 0.45, "cash": 7.0,  "xp": 45},
    "pronghorn": {"name": "Вилорог",       "region": "desert",    "base_chance": 0.52, "cash": 8.0,  "xp": 50},
    "cougar":    {"name": "Пума",           "region": "desert",    "base_chance": 0.38, "cash": 17.0, "xp": 90},
}

CATEGORIES = {
    region_key: [
        animal_key
        for animal_key, animal in ANIMALS.items()
        if animal["region"] == region_key
    ]
    for region_key in NATURALIST_REGIONS
}

# Награды за легендарных животных удвоены
LEGENDARY_ANIMALS = {
    "legendary_buck":   {"name": "Легендарный олень",  "required_level": 1,  "cash": 120.0, "gold": 2.0, "xp": 260},
    "legendary_wolf":   {"name": "Легендарный волк",   "required_level": 1,  "cash": 150.0, "gold": 2.5, "xp": 320},
    "legendary_bear":   {"name": "Легендарный медведь","required_level": 1,  "cash": 190.0, "gold": 3.0, "xp": 420},
    "legendary_cougar": {"name": "Легендарная пума",   "required_level": 1,  "cash": 250.0, "gold": 4.0, "xp": 560},
}


def get_naturalist_button_emoji(button_key):
    emojis = economy_data.get("naturalist_button_emojis", {})
    emoji = emojis.get(button_key)
    if not emoji:
        return str(DEFAULT_NATURALIST_BUTTON_EMOJIS[button_key])
    return str(emoji)


def default_naturalist_data():
    return {
        "level": 1,
        "xp": 0,
        "samples": {},
        "last_sample_at": None,
        "legendary_cooldown_until": None,
    }


def normalize_naturalist_data(naturalist):
    if not isinstance(naturalist, dict):
        naturalist = default_naturalist_data()

    try:
        naturalist["level"] = max(
            1, min(NATURALIST_MAX_LEVEL, int(naturalist.get("level", 1)))
        )
    except (TypeError, ValueError):
        naturalist["level"] = 1
    try:
        naturalist["xp"] = max(0, int(naturalist.get("xp", 0)))
    except (TypeError, ValueError):
        naturalist["xp"] = 0

    samples = naturalist.get("samples", {})
    if not isinstance(samples, dict):
        samples = {}
    normalized_samples = {}
    valid_sample_keys = set(ANIMALS) | set(LEGENDARY_ANIMALS)
    for sample_key, amount in samples.items():
        if sample_key not in valid_sample_keys:
            continue
        try:
            amount = max(0, int(amount))
        except (TypeError, ValueError):
            amount = 0
        if amount > 0:
            normalized_samples[sample_key] = amount
    naturalist["samples"] = normalized_samples
    naturalist.setdefault("last_sample_at", None)
    naturalist.setdefault("legendary_cooldown_until", None)
    # Убираем устаревшие поля транквилизаторов, если остались
    naturalist.pop("inventory", None)
    return naturalist


def get_naturalist_account(account):
    account["naturalist"] = normalize_naturalist_data(account.get("naturalist"))
    return account["naturalist"]


def naturalist_sample_cooldown_seconds(naturalist):
    return NATURALIST_SAMPLE_COOLDOWN_SECONDS


def get_naturalist_sample_cooldown(naturalist):
    last_sample_at = naturalist.get("last_sample_at")
    if not last_sample_at:
        return 0
    cooldown = naturalist_sample_cooldown_seconds(naturalist)
    seconds_passed = (now_local() - parse_local_datetime(last_sample_at)).total_seconds()
    return max(0, cooldown - seconds_passed)


def get_naturalist_legendary_cooldown(naturalist):
    cooldown_until = naturalist.get("legendary_cooldown_until")
    if not cooldown_until:
        return 0
    seconds_left = (parse_local_datetime(cooldown_until) - now_local()).total_seconds()
    return max(0, seconds_left)


def get_naturalist_gear(account, catalog_items):
    """Возвращает словарь доступного снаряжения натуралиста."""
    inventory = account.get("inventory", {})
    loadout = account.get("weapon_loadout", {})
    equipped = (
        loadout.get("sidearms", []) + loadout.get("longarms", [])
    )
    has_varmint = NATURALIST_VARMINT_KEY in equipped
    has_reviver  = int(inventory.get(NATURALIST_REVIVER_KEY, 0) or 0) >= 1
    has_dart     = int(inventory.get(NATURALIST_DART_KEY, 0) or 0) >= 1
    return {
        "varmint": has_varmint,
        "reviver": has_reviver,
        "dart":    has_dart,
    }


def calculate_naturalist_chance(base_chance: float, gear: dict) -> float:
    """Итоговый шанс поимки с учётом снаряжения (0.0–0.95)."""
    bonus = 0.0
    if gear["varmint"]:
        bonus += NATURALIST_VARMINT_BONUS / 100
    if gear["reviver"]:
        bonus += NATURALIST_REVIVER_BONUS / 100
    if gear["dart"]:
        bonus += NATURALIST_DART_BONUS / 100
    return min(0.95, base_chance + bonus)


def consume_naturalist_gear(account, gear: dict):
    """Тратит 1 оживитель и 1 снотворную стрелу, если они использовались."""
    inventory = account.setdefault("inventory", {})
    if gear["reviver"]:
        inventory[NATURALIST_REVIVER_KEY] = max(0, int(inventory.get(NATURALIST_REVIVER_KEY, 0)) - 1)
    if gear["dart"]:
        inventory[NATURALIST_DART_KEY] = max(0, int(inventory.get(NATURALIST_DART_KEY, 0)) - 1)


def get_naturalist_sale_multiplier(naturalist):
    return 1.10 if naturalist.get("level", 1) >= 20 else 1.0


def count_naturalist_samples(naturalist):
    return sum(int(amount) for amount in naturalist.get("samples", {}).values())


def format_naturalist_samples_short(naturalist):
    samples = naturalist.get("samples", {})
    if not samples:
        return "нет"
    rows = [
        f"{format_sample_name(sample_key)} x{amount}"
        for sample_key, amount in sorted(samples.items())
    ]
    text = ", ".join(rows[:6])
    if len(rows) > 6:
        text += f" и ещё {len(rows) - 6}"
    return text


def format_naturalist_short(account):
    naturalist = get_naturalist_account(account)
    needed = xp_for_next_level(naturalist["level"], 180)
    return (
        f"уровень {naturalist['level']}, опыт {naturalist['xp']}/{needed}, "
        f"образцы: {format_naturalist_samples_short(naturalist)}"
    )


def has_full_naturalist_category(naturalist, region_key):
    samples = naturalist.get("samples", {})
    return all(samples.get(animal_key, 0) > 0 for animal_key in CATEGORIES[region_key])


def get_naturalist_category_progress(naturalist, region_key):
    samples = naturalist.get("samples", {})
    collected = sum(1 for animal_key in CATEGORIES[region_key] if samples.get(animal_key, 0) > 0)
    total = len(CATEGORIES[region_key])
    return collected, total


def get_naturalist_image_file():
    if not os.path.exists(NATURALIST_IMAGE_FILE):
        return None
    return discord.File(NATURALIST_IMAGE_FILE, filename=NATURALIST_IMAGE_ATTACHMENT_NAME)


def build_gear_status(gear: dict) -> str:
    """Формирует строку снаряжения натуралиста для embed."""
    varmint_mark = "✅" if gear["varmint"] else "❌"
    reviver_mark = "✅" if gear["reviver"] else "❌"
    dart_mark    = "✅" if gear["dart"] else "❌"
    return (
        f"{varmint_mark} Варминт-винтовка (+{NATURALIST_VARMINT_BONUS}%)\n"
        f"{reviver_mark} Оживитель (+{NATURALIST_REVIVER_BONUS}%)\n"
        f"{dart_mark} Снотворная стрела (+{NATURALIST_DART_BONUS}%)"
    )


def build_naturalist_embed(guild, account, note=None, gear=None):
    naturalist = get_naturalist_account(account)
    role_definition = get_role_definition(NATURALIST_ROLE_KEY)
    role = find_guild_role(guild, role_definition)
    icon = get_role_icon(role_definition, role)
    needed = xp_for_next_level(naturalist["level"], 180)
    sample_cooldown = get_naturalist_sample_cooldown(naturalist)
    legendary_cooldown = get_naturalist_legendary_cooldown(naturalist)
    sample_cooldown_text = "готово" if sample_cooldown <= 0 else format_duration(sample_cooldown)
    legendary_text = (
        "доступно" if legendary_cooldown <= 0
        else format_duration(legendary_cooldown)
    )
    note_text = f"\n\n{note}" if note else ""

    gear_text = build_gear_status(gear) if gear else (
        "🔍 Откройте `/naturalist` для проверки снаряжения"
    )

    embed = discord.Embed(
        title=f"{icon} Натуралист",
        description=(
            "Собирайте образцы, сдавайте их Гарриет и закрывайте категории справочника.\n"
            "Шанс поимки зависит от **снаряжения** в вашем loadout и инвентаре.\n\n"
            "🌿 Прогресс\n"
            f"├─ Уровень: **{naturalist['level']}/{NATURALIST_MAX_LEVEL}**\n"
            f"├─ Опыт: **{naturalist['xp']}/{needed}**\n"
            f"├─ Образцы: **{count_naturalist_samples(naturalist)}**\n"
            f"├─ Обычная охота: **{sample_cooldown_text}**\n"
            f"└─ Легендарка: **{legendary_text}**\n\n"
            f"🎒 Снаряжение\n{gear_text}"
            f"{note_text}"
        ),
        color=discord.Color.dark_green(),
    )
    if os.path.exists(NATURALIST_IMAGE_FILE):
        embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
    return embed


def build_naturalist_collection_embed(naturalist):
    lines = []
    for region_key, region in NATURALIST_REGIONS.items():
        collected, total = get_naturalist_category_progress(naturalist, region_key)
        status = "готово к сдаче" if collected == total else f"{collected}/{total}"
        lines.append(f"{region['emoji']} **{region['name']}** — {status}")
    samples = format_naturalist_samples_short(naturalist)
    embed = build_bot_embed(
        "Справочник натуралиста",
        "\n".join(lines) + f"\n\nОбразцы: **{samples}**",
        color=discord.Color.dark_green(),
    )
    if os.path.exists(NATURALIST_IMAGE_FILE):
        embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
    return embed


def build_naturalist_legendary_embed(naturalist):
    lines = []
    for animal_key, animal in LEGENDARY_ANIMALS.items():
        from bot import get_lock_emoji
        lines.append(
            f"**{animal['name']}** — "
            f"сдача {format_money(animal['cash'])} + {format_gold(animal['gold'])}"
        )
    embed = build_bot_embed(
        "Легендарное животное",
        "\n".join(lines),
        color=discord.Color.dark_green(),
    )
    if os.path.exists(NATURALIST_IMAGE_FILE):
        embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
    return embed
