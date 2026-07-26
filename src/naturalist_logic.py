import time
import math
import random
import json
from datetime import datetime, timedelta, timezone
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
NATURALIST_LEGENDARY_REQUIRED_LEVEL = 5
NATURALIST_HARRIET_ANGER_MIN_SECONDS = 5 * 60
NATURALIST_HARRIET_ANGER_MAX_SECONDS = 7 * 60
NATURALIST_TRANQ_PACK_SIZE = 20
NATURALIST_TRANQ_PACK_PRICE = 0.56
NATURALIST_REVIVER_PRICE = 5.0
NATURALIST_PHEROMONE_PRICE = 20.0
NATURALIST_CAMP_PRICE = 750.0
NATURALIST_TRANQ_CAP = 100


def _now():
    return datetime.now(timezone.utc)


def _parse_datetime(value):
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed

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
NATURALIST_PHEROMONE_BONUS = 10

NATURALIST_REGIONS = {
    "forest":    {"name": "Обитатели лесов и рек", "emoji": "🌲", "payout": 160.0},
    "mountains": {"name": "Обитатели гор и лугов", "emoji": "⛰️", "payout": 140.0},
    "wetlands":  {"name": "Обитатели болот",       "emoji": "💧", "payout": 110.0},
    "desert":    {"name": "Обитатели пустынь",     "emoji": "🏜️", "payout": 80.0},
}

# ---------------------------------------------------------------------------
# Обычный образец приносит не больше $4 и 50 опыта.
# ---------------------------------------------------------------------------
ANIMALS = {
    "rabbit":    {"name": "Кролик",         "region": "forest",    "base_chance": 0.60, "cash": 1.0, "xp": 50},
    "deer":      {"name": "Олень",          "region": "forest",    "base_chance": 0.50, "cash": 2.0, "xp": 50},
    "fox":       {"name": "Лиса",           "region": "forest",    "base_chance": 0.45, "cash": 2.5, "xp": 50},
    "wolf":      {"name": "Волк",           "region": "forest",    "base_chance": 0.40, "cash": 4.0, "xp": 50},
    "bighorn":   {"name": "Горный баран",   "region": "mountains", "base_chance": 0.45, "cash": 2.5, "xp": 50},
    "eagle":     {"name": "Орёл",           "region": "mountains", "base_chance": 0.40, "cash": 3.0, "xp": 50},
    "moose":     {"name": "Лось",           "region": "mountains", "base_chance": 0.35, "cash": 3.5, "xp": 50},
    "bear":      {"name": "Медведь",        "region": "mountains", "base_chance": 0.30, "cash": 4.0, "xp": 50},
    "beaver":    {"name": "Бобр",           "region": "wetlands",  "base_chance": 0.50, "cash": 2.0, "xp": 50},
    "frog":      {"name": "Лягушка",        "region": "wetlands",  "base_chance": 0.55, "cash": 1.0, "xp": 50},
    "boar":      {"name": "Кабан",          "region": "wetlands",  "base_chance": 0.42, "cash": 3.0, "xp": 50},
    "alligator": {"name": "Аллигатор",      "region": "wetlands",  "base_chance": 0.32, "cash": 4.0, "xp": 50},
    "coyote":    {"name": "Койот",          "region": "desert",    "base_chance": 0.48, "cash": 2.0, "xp": 50},
    "snake":     {"name": "Гремучая змея",  "region": "desert",    "base_chance": 0.45, "cash": 1.5, "xp": 50},
    "pronghorn": {"name": "Вилорог",        "region": "desert",    "base_chance": 0.52, "cash": 2.0, "xp": 50},
    "cougar":    {"name": "Пума",           "region": "desert",    "base_chance": 0.38, "cash": 4.0, "xp": 50},
}

CATEGORIES = {
    region_key: [
        animal_key
        for animal_key, animal in ANIMALS.items()
        if animal["region"] == region_key
    ]
    for region_key in NATURALIST_REGIONS
}

# Легендарные образцы доступны с 5 уровня: $15–60 и 350 опыта.
# pelt_materials — сколько материалов получит Криппс за цельную шкуру.
LEGENDARY_ANIMALS = {
    "legendary_buck": {"name": "Легендарный олень", "required_level": 5, "cash": 15.0, "xp": 350, "pelt_materials": 21.88},
    "legendary_wolf": {"name": "Легендарный волк", "required_level": 5, "cash": 30.0, "xp": 350, "pelt_materials": 25.0},
    "legendary_bear": {"name": "Легендарный медведь", "required_level": 5, "cash": 45.0, "xp": 350, "pelt_materials": 31.25},
    "legendary_cougar": {"name": "Легендарная пума", "required_level": 5, "cash": 60.0, "xp": 350, "pelt_materials": 44.38},
    "wapiti_iname": {"name": "Вапити Инаме", "required_level": 5, "cash": 25.5, "xp": 350, "pelt_materials": 41.16},
    "alligator_brown_blood": {"name": "Аллигатор «Бурая кровь»", "required_level": 5, "cash": 23.5, "xp": 350, "pelt_materials": 40.63},
    "deer_quick_shadow": {"name": "Олень «Быстрая тень»", "required_level": 5, "cash": 31.5, "xp": 350, "pelt_materials": 56.88},
    "bighorn_blood_horn": {"name": "Толсторог «Рог крови»", "required_level": 5, "cash": 29.0, "xp": 350, "pelt_materials": 56.25},
    "beaver_night_rustle": {"name": "Бобр «Ночной шорох»", "required_level": 5, "cash": 28.5, "xp": 350, "pelt_materials": 55.63},
    "bear_golden_spirit": {"name": "Медведь «Золотой дух»", "required_level": 5, "cash": 36.0, "xp": 350, "pelt_materials": 62.5},
    "coyote_milky_way": {"name": "Койот «Млечный путь»", "required_level": 5, "cash": 20.5, "xp": 350, "pelt_materials": 38.13},
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
        "stamps": {},
        "legendary_pelts": {},
        "inventory": {"tranquilizers": 0, "pheromones": 0},
        "has_wilderness_camp": False,
        "last_sample_at": None,
        "legendary_cooldown_until": None,
        "harriet_angry_until": None,
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
    pelts = naturalist.get("legendary_pelts", {})
    if not isinstance(pelts, dict):
        pelts = {}
    naturalist["legendary_pelts"] = {
        key: max(0, int(amount))
        for key, amount in pelts.items()
        if key in LEGENDARY_ANIMALS and str(amount).lstrip("-").isdigit() and int(amount) > 0
    }
    stamps = naturalist.get("stamps", {})
    if not isinstance(stamps, dict):
        stamps = {}
    naturalist["stamps"] = {
        key: True for key, stamped in stamps.items()
        if key in valid_sample_keys and bool(stamped)
    }
    inventory = naturalist.get("inventory", {})
    if not isinstance(inventory, dict):
        inventory = {}
    naturalist["inventory"] = {}
    for key, cap in (
        ("tranquilizers", NATURALIST_TRANQ_CAP),
        ("pheromones", 100),
    ):
        try:
            amount = max(0, min(cap, int(inventory.get(key, 0) or 0)))
        except (TypeError, ValueError):
            amount = 0
        naturalist["inventory"][key] = amount
    naturalist["has_wilderness_camp"] = bool(
        naturalist.get("has_wilderness_camp", False)
    )
    naturalist.setdefault("last_sample_at", None)
    naturalist.setdefault("legendary_cooldown_until", None)
    naturalist.setdefault("harriet_angry_until", None)
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
    seconds_passed = (_now() - _parse_datetime(last_sample_at)).total_seconds()
    return max(0, cooldown - seconds_passed)


def get_naturalist_legendary_cooldown(naturalist):
    cooldown_until = naturalist.get("legendary_cooldown_until")
    if not cooldown_until:
        return 0
    seconds_left = (_parse_datetime(cooldown_until) - _now()).total_seconds()
    return max(0, seconds_left)


def get_harriet_anger_cooldown(naturalist):
    cooldown_until = naturalist.get("harriet_angry_until")
    if not cooldown_until:
        return 0
    seconds_left = (_parse_datetime(cooldown_until) - _now()).total_seconds()
    return max(0, seconds_left)


def anger_harriet(naturalist, rng=None):
    rng = rng or random
    seconds = rng.randint(
        NATURALIST_HARRIET_ANGER_MIN_SECONDS,
        NATURALIST_HARRIET_ANGER_MAX_SECONDS,
    )
    naturalist["harriet_angry_until"] = (
        _now() + timedelta(seconds=seconds)
    ).isoformat(timespec="seconds")
    return seconds


def add_legendary_pelt(naturalist, animal_key):
    if animal_key not in LEGENDARY_ANIMALS:
        raise ValueError("Неизвестное легендарное животное.")
    pelts = naturalist.setdefault("legendary_pelts", {})
    pelts[animal_key] = int(pelts.get(animal_key, 0) or 0) + 1
    return LEGENDARY_ANIMALS[animal_key]["pelt_materials"]


def pop_best_legendary_pelt(naturalist):
    pelts = naturalist.setdefault("legendary_pelts", {})
    available = [
        key for key, amount in pelts.items()
        if key in LEGENDARY_ANIMALS and int(amount or 0) > 0
    ]
    if not available:
        return None
    animal_key = max(
        available,
        key=lambda key: LEGENDARY_ANIMALS[key]["pelt_materials"],
    )
    pelts[animal_key] -= 1
    if pelts[animal_key] <= 0:
        pelts.pop(animal_key, None)
    return animal_key, LEGENDARY_ANIMALS[animal_key]


def calculate_legendary_pelt_wagon_fill(current_fill, animal_key):
    animal = LEGENDARY_ANIMALS[animal_key]
    current_fill = max(0.0, min(100.0, float(current_fill)))
    if animal["pelt_materials"] >= 50:
        return 100.0
    return min(100.0, current_fill + 50.0)


def get_naturalist_gear(account, catalog_items):
    """Возвращает словарь доступного снаряжения натуралиста."""
    inventory = account.get("inventory", {})
    loadout = account.get("weapon_loadout", {})
    equipped = (
        loadout.get("sidearms", []) + loadout.get("longarms", [])
    )
    has_varmint = NATURALIST_VARMINT_KEY in equipped
    has_reviver  = int(inventory.get(NATURALIST_REVIVER_KEY, 0) or 0) >= 1
    naturalist = get_naturalist_account(account)
    naturalist_inventory = naturalist["inventory"]
    has_dart = (
        int(naturalist_inventory.get("tranquilizers", 0) or 0) >= 1
        or int(inventory.get(NATURALIST_DART_KEY, 0) or 0) >= 1
    )
    has_pheromone = int(naturalist_inventory.get("pheromones", 0) or 0) >= 1
    return {
        "varmint": has_varmint,
        "reviver": has_reviver,
        "dart":    has_dart,
        "pheromone": has_pheromone,
    }


def calculate_naturalist_chance(
    base_chance: float, gear: dict, *, legendary=False
) -> float:
    """Итоговый шанс поимки с учётом снаряжения (0.0–0.95)."""
    bonus = 0.0
    if gear["varmint"]:
        bonus += NATURALIST_VARMINT_BONUS / 100
    if gear["reviver"]:
        bonus += NATURALIST_REVIVER_BONUS / 100
    if gear["dart"]:
        bonus += NATURALIST_DART_BONUS / 100
    if legendary and gear.get("pheromone"):
        bonus += NATURALIST_PHEROMONE_BONUS / 100
    return min(0.95, base_chance + bonus)


def consume_naturalist_gear(account, gear: dict, *, legendary=False):
    """Тратит 1 оживитель и 1 снотворную стрелу, если они использовались."""
    inventory = account.setdefault("inventory", {})
    if gear["reviver"]:
        inventory[NATURALIST_REVIVER_KEY] = max(0, int(inventory.get(NATURALIST_REVIVER_KEY, 0)) - 1)
    if gear["dart"]:
        naturalist = get_naturalist_account(account)
        if naturalist["inventory"]["tranquilizers"] > 0:
            naturalist["inventory"]["tranquilizers"] -= 1
        else:
            inventory[NATURALIST_DART_KEY] = max(
                0, int(inventory.get(NATURALIST_DART_KEY, 0)) - 1
            )
    if legendary and gear.get("pheromone"):
        naturalist = get_naturalist_account(account)
        naturalist["inventory"]["pheromones"] = max(
            0, naturalist["inventory"]["pheromones"] - 1
        )


def get_naturalist_tranq_cap(naturalist):
    return NATURALIST_TRANQ_CAP


def stamp_naturalist_samples(naturalist, samples):
    for sample_key, amount in samples.items():
        if amount > 0:
            naturalist["stamps"][sample_key] = True


def get_naturalist_sale_multiplier(naturalist):
    return 1.0


def count_naturalist_samples(naturalist):
    return sum(int(amount) for amount in naturalist.get("samples", {}).values())


def count_legendary_pelts(naturalist):
    return sum(int(amount) for amount in naturalist.get("legendary_pelts", {}).values())


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
    return f"образцы: {format_naturalist_samples_short(naturalist)}"


def has_full_naturalist_category(naturalist, region_key):
    stamps = naturalist.get("stamps", {})
    return all(stamps.get(animal_key, False) for animal_key in CATEGORIES[region_key])


def get_naturalist_category_progress(naturalist, region_key):
    stamps = naturalist.get("stamps", {})
    collected = sum(1 for animal_key in CATEGORIES[region_key] if stamps.get(animal_key, False))
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
    pheromone_mark = "✅" if gear.get("pheromone") else "❌"
    return (
        f"{varmint_mark} Варминт-винтовка (+{NATURALIST_VARMINT_BONUS}%)\n"
        f"{reviver_mark} Оживитель (+{NATURALIST_REVIVER_BONUS}%)\n"
        f"{dart_mark} Снотворные патроны (+{NATURALIST_DART_BONUS}%)\n"
        f"{pheromone_mark} Легендарные феромоны (+{NATURALIST_PHEROMONE_BONUS}%)"
    )


def build_naturalist_embed(guild, account, note=None, gear=None):
    naturalist = get_naturalist_account(account)
    role_definition = get_role_definition(NATURALIST_ROLE_KEY)
    role = find_guild_role(guild, role_definition)
    icon = get_role_icon(role_definition, role)
    sample_cooldown = get_naturalist_sample_cooldown(naturalist)
    harriet_cooldown = get_harriet_anger_cooldown(naturalist)
    sample_cooldown_text = "готово" if sample_cooldown <= 0 else format_duration(sample_cooldown)
    harriet_text = (
        "принимает посетителей"
        if harriet_cooldown <= 0
        else f"сердится ещё {format_duration(harriet_cooldown)}"
    )
    note_text = f"\n\n{note}" if note else ""

    embed = discord.Embed(
        title=f"{icon} Натуралист",
        description=(
            "Найдите случайное животное, возьмите образец и сдайте его Гарриет.\n\n"
            "🌿 Прогресс\n"
            f"├─ Образцы: **{count_naturalist_samples(naturalist)}**\n"
            f"├─ Обычная охота: **{sample_cooldown_text}**\n"
            f"└─ Гарриет: **{harriet_text}**\n\n"
            "Снаряжение для обычного поиска выдаётся вместе с профессией."
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
        status = "готово к сдаче" if collected == total else f"{collected}/{total} штампов"
        lines.append(
            f"{region['emoji']} **{region['name']}** — {status} · "
            f"{format_money(region['payout'])}"
        )
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
        lines.append(
            f"**{animal['name']}** — "
            f"сдача {format_money(animal['cash'])}"
        )
    embed = build_bot_embed(
        "Легендарное животное",
        "\n".join(lines),
        color=discord.Color.dark_green(),
    )
    if os.path.exists(NATURALIST_IMAGE_FILE):
        embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
    return embed


def build_naturalist_pelt_embed(naturalist):
    lines = []
    for animal in LEGENDARY_ANIMALS.values():
        lines.append(
            f"**{animal['name']}** — "
            f"{format_number(animal['pelt_materials'])} материалов Криппса"
        )
    embed = build_bot_embed(
        "Легендарная шкура",
        (
            "Убийство гарантированно даёт цельную шкуру, но Гарриет "
            "перестаёт иметь с вами дело на 5–7 минут.\n\n"
            + "\n".join(lines)
        ),
        color=discord.Color.dark_red(),
    )
    if os.path.exists(NATURALIST_IMAGE_FILE):
        embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
    return embed
