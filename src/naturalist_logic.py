import time
import math
import random
import json
import discord
from discord import app_commands
from src.xp_utils import *

NATURALIST_IMAGE_FILE = "assets/images/naturalist.png"


NATURALIST_IMAGE_ATTACHMENT_NAME = "naturalist.png"


DEFAULT_NATURALIST_BUTTON_EMOJIS = {
    "sample": "🔬",
    "sell": "<:money:1518183921903472701>",
    "collection": "📖",
    "legendary": "🐾",
    "shop": "🧪",
    "refresh": "<:update:1518269540012789860>",
}


NATURALIST_ROLE_KEY = "naturalist"


NATURALIST_MAX_LEVEL = 20


NATURALIST_SAMPLE_COOLDOWN_SECONDS = 5 * 60


NATURALIST_LEGENDARY_COOLDOWN_SECONDS = 60 * 60


NATURALIST_TRANQ_PRICE = 5.0


NATURALIST_START_TRANQS = 50


NATURALIST_BASE_TRANQ_CAP = 200


NATURALIST_UPGRADED_TRANQ_CAP = 250


NATURALIST_REGIONS = {
    "forest": {"name": "Лес", "emoji": "🌲"},
    "mountains": {"name": "Горы", "emoji": "⛰️"},
    "wetlands": {"name": "Болота", "emoji": "💧"},
    "desert": {"name": "Пустыня", "emoji": "🏜️"},
}

ANIMALS = {
    "rabbit": {"name": "Кролик", "region": "forest", "shots": 1, "chance": 0.88, "cash": 2.5, "xp": 25},
    "deer": {"name": "Олень", "region": "forest", "shots": 2, "chance": 0.78, "cash": 4.0, "xp": 45},
    "fox": {"name": "Лиса", "region": "forest", "shots": 2, "chance": 0.72, "cash": 4.5, "xp": 50},
    "wolf": {"name": "Волк", "region": "forest", "shots": 3, "chance": 0.60, "cash": 6.0, "xp": 75},
    "bighorn": {"name": "Горный баран", "region": "mountains", "shots": 2, "chance": 0.70, "cash": 4.5, "xp": 55},
    "eagle": {"name": "Орёл", "region": "mountains", "shots": 1, "chance": 0.62, "cash": 5.0, "xp": 65},
    "moose": {"name": "Лось", "region": "mountains", "shots": 5, "chance": 0.48, "cash": 9.0, "xp": 105},
    "bear": {"name": "Медведь", "region": "mountains", "shots": 5, "chance": 0.42, "cash": 10.0, "xp": 120},
    "beaver": {"name": "Бобр", "region": "wetlands", "shots": 2, "chance": 0.74, "cash": 4.0, "xp": 45},
    "frog": {"name": "Лягушка", "region": "wetlands", "shots": 1, "chance": 0.86, "cash": 2.0, "xp": 20},
    "boar": {"name": "Кабан", "region": "wetlands", "shots": 2, "chance": 0.66, "cash": 5.0, "xp": 65},
    "alligator": {"name": "Аллигатор", "region": "wetlands", "shots": 5, "chance": 0.45, "cash": 9.5, "xp": 115},
    "coyote": {"name": "Койот", "region": "desert", "shots": 2, "chance": 0.73, "cash": 4.0, "xp": 45},
    "snake": {"name": "Гремучая змея", "region": "desert", "shots": 1, "chance": 0.68, "cash": 3.5, "xp": 40},
    "pronghorn": {"name": "Вилорог", "region": "desert", "shots": 2, "chance": 0.76, "cash": 4.0, "xp": 45},
    "cougar": {"name": "Пума", "region": "desert", "shots": 3, "chance": 0.55, "cash": 7.0, "xp": 85},
}
CATEGORIES = {
    region_key: [
        animal_key
        for animal_key, animal in ANIMALS.items()
        if animal["region"] == region_key
    ]
    for region_key in NATURALIST_REGIONS
}
LEGENDARY_ANIMALS = {
    "legendary_buck": {"name": "Легендарный олень", "required_level": 5, "cash": 60.0, "gold": 1.0, "xp": 260},
    "legendary_wolf": {"name": "Легендарный волк", "required_level": 8, "cash": 75.0, "gold": 1.2, "xp": 320},
    "legendary_bear": {"name": "Легендарный медведь", "required_level": 12, "cash": 95.0, "gold": 1.5, "xp": 420},
    "legendary_cougar": {"name": "Легендарная пума", "required_level": 16, "cash": 120.0, "gold": 2.0, "xp": 560},
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
        "inventory": {"tranquilizers": NATURALIST_START_TRANQS},
        "last_sample_at": None,
        "legendary_cooldown_until": None,
    }


def get_naturalist_tranq_cap(naturalist):
    return (
        NATURALIST_UPGRADED_TRANQ_CAP
        if int(naturalist.get("level", 1)) >= 3
        else NATURALIST_BASE_TRANQ_CAP
    )


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

    inventory = naturalist.get("inventory", {})
    if not isinstance(inventory, dict):
        inventory = {}
    try:
        tranquilizers = max(0, int(inventory.get("tranquilizers", NATURALIST_START_TRANQS)))
    except (TypeError, ValueError):
        tranquilizers = NATURALIST_START_TRANQS
    naturalist["inventory"] = {
        "tranquilizers": min(tranquilizers, get_naturalist_tranq_cap(naturalist))
    }
    naturalist.setdefault("last_sample_at", None)
    naturalist.setdefault("legendary_cooldown_until", None)
    return naturalist


def get_naturalist_account(account):
    account["naturalist"] = normalize_naturalist_data(account.get("naturalist"))
    return account["naturalist"]


def naturalist_sample_cooldown_seconds(naturalist):
    cooldown = NATURALIST_SAMPLE_COOLDOWN_SECONDS
    if naturalist.get("level", 1) >= 10:
        cooldown = int(cooldown * 0.8)
    return cooldown


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


def get_naturalist_success_chance(naturalist, base_chance):
    level = int(naturalist.get("level", 1))
    bonus = level * 0.01
    if level >= 5:
        bonus += 0.05
    if level >= 15:
        bonus += 0.10
    return min(0.95, base_chance + bonus)


def get_naturalist_sale_multiplier(naturalist):
    return 1.05 if naturalist.get("level", 1) >= 20 else 1.0


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
    tranqs = naturalist["inventory"]["tranquilizers"]
    cap = get_naturalist_tranq_cap(naturalist)
    return (
        f"уровень {naturalist['level']}, опыт {naturalist['xp']}/{needed}, "
        f"транквилизаторы {tranqs}/{cap}, образцы: {format_naturalist_samples_short(naturalist)}"
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


def build_naturalist_embed(guild, account, note=None):
    naturalist = get_naturalist_account(account)
    role_definition = get_role_definition(NATURALIST_ROLE_KEY)
    role = find_guild_role(guild, role_definition)
    icon = get_role_icon(role_definition, role)
    needed = xp_for_next_level(naturalist["level"], 180)
    tranqs = naturalist["inventory"]["tranquilizers"]
    tranq_cap = get_naturalist_tranq_cap(naturalist)
    sample_cooldown = get_naturalist_sample_cooldown(naturalist)
    legendary_cooldown = get_naturalist_legendary_cooldown(naturalist)
    sample_cooldown_text = "готово" if sample_cooldown <= 0 else format_duration(sample_cooldown)
    legendary_text = (
        "доступно"
        if naturalist["level"] >= 5 and legendary_cooldown <= 0
        else "с 5 уровня"
        if naturalist["level"] < 5
        else format_duration(legendary_cooldown)
    )
    note_text = f"\n\n{note}" if note else ""
    embed = discord.Embed(
        title=f"{icon} Натуралист",
        description=(
            "Собирайте образцы, сдавайте их Гарриет и закрывайте категории справочника.\n\n"
            "🌿 Прогресс\n"
            f"├─ Уровень: **{naturalist['level']}/{NATURALIST_MAX_LEVEL}**\n"
            f"├─ Опыт: **{naturalist['xp']}/{needed}**\n"
            f"├─ Транквилизаторы: **{tranqs}/{tranq_cap}**\n"
            f"├─ Образцы: **{count_naturalist_samples(naturalist)}**\n"
            f"├─ Обычная охота: **{sample_cooldown_text}**\n"
            f"└─ Легендарка: **{legendary_text}**"
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
        lock = "" if naturalist["level"] >= animal["required_level"] else " 🔒"
        lines.append(
            f"**{animal['name']}**{lock} — с {animal['required_level']} ур., "
            f"10 патр., сдача {format_money(animal['cash'])} + {format_gold(animal['gold'])}"
        )
    embed = build_bot_embed(
        "Легендарное животное",
        "\n".join(lines),
        color=discord.Color.dark_green(),
    )
    if os.path.exists(NATURALIST_IMAGE_FILE):
        embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
    return embed


def build_naturalist_shop_embed(account, naturalist):
    tranqs = naturalist["inventory"]["tranquilizers"]
    cap = get_naturalist_tranq_cap(naturalist)
    return build_bot_embed(
        "Магазин натуралиста",
        (
            f"Транквилизатор: **{format_money(NATURALIST_TRANQ_PRICE)}** за штуку.\n"
            f"Инвентарь: **{tranqs}/{cap}**\n"
            f"Наличные: **{format_money(account['cash'])}**"
        ),
        color=discord.Color.dark_green(),
    )

