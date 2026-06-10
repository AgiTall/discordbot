import asyncio
import json
import math
import os
import random
from datetime import date, datetime, time, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks


CHANNELS_FILE = "channels.txt"
COMMANDS_SYNCED = False
ENV_FILE = ".env"
BOT_TOKEN = ""
ECONOMY_FILE = "economy.json"
START_GOLD_RATE = 543.45
MIN_GOLD_RATE = 50.0
DEPOSIT_DAILY_RATE = 0.03
WORK_COOLDOWN_SECONDS = 60 * 60
DEFAULT_CASH_EMOJI = "$"
DEFAULT_GOLD_EMOJI = "🟡"
DEFAULT_MAP_EMOJI = "🗺️"
DEFAULT_INVESTMENT_EMOJI = "📈"
DEFAULT_STATS_EMOJI = "👤"
TREASURE_BANNER_FILE = "image.png"
ROLE_IMAGE_FILE = "image 2.png"
ROLE_IMAGE_ATTACHMENT_NAME = "roles.png"
MOONSHINE_IMAGE_FILE = "image 3.png"
MOONSHINE_IMAGE_ATTACHMENT_NAME = "moonshine.png"
TREASURE_MAPS_PER_DROP = 1
EXCAVATION_REWARD_CHANCE = 0.15
MSK_TZ = timezone(timedelta(hours=3), "MSK")
ROLE_BASE_PRICE = 20.0
ROLE_DISCOUNT_DAYS = 7
DEALER_MIN_FILL = 10
DEALER_MAX_FILL = 35
DEALER_DELIVERY_MIN_REWARD = 500
DEALER_DELIVERY_MAX_REWARD = 625
DEALER_ROLE_KEY = "trader"
MOONSHINER_ROLE_KEY = "moonshiner"
MOONSHINE_CONDENSER_PRICE = 825.0
MOONSHINE_DISTILLER_PRICE = 875.0
DEFAULT_MOONSHINE_STAR_EMOJIS = {
    "1": "⭐",
    "2": "⭐⭐",
    "3": "⭐⭐⭐",
}
DEFAULT_MOONSHINE_SPECIAL_EMOJI = "🌟🌟🌟"
DEFAULT_MOONSHINE_BUTTON_EMOJIS = {
    "mash": "🥣",
    "special": "🌿",
    "upgrades": "⚙️",
    "delivery": "🛺",
}
CARD_RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
CARD_SUITS = ["♠", "♥", "♦", "♣"]
POKER_HAND_NAMES = {
    8: "Стрит-флеш",
    7: "Каре",
    6: "Фулл-хаус",
    5: "Флеш",
    4: "Стрит",
    3: "Сет",
    2: "Две пары",
    1: "Пара",
    0: "Старшая карта",
}
ROLE_DEFINITIONS = [
    {
        "key": "bounty_hunter",
        "name": "Охотник за головами",
        "aliases": [],
        "emoji": "🎯",
        "available": False,
        "description": (
            "Выслеживает опасные цели, берёт контракты на поимку и получает награды "
            "за точность, выдержку и холодную голову."
        ),
    },
    {
        "key": "trader",
        "name": "Торговец",
        "aliases": [],
        "emoji": "🛒",
        "available": True,
        "description": (
            "Развивает собственное дело, наполняет торговую повозку товарами и готовит "
            "поставки для будущей прибыли."
        ),
    },
    {
        "key": "moonshiner",
        "name": "Самогонщик",
        "aliases": [],
        "emoji": "🥃",
        "available": True,
        "description": (
            "Мастер тайного производства: варит крепкий товар, держит сеть поставок "
            "и знает цену хорошей репутации."
        ),
    },
    {
        "key": "naturalist",
        "name": "Натуралист",
        "aliases": [],
        "emoji": "🌿",
        "available": False,
        "description": (
            "Изучает природу, выслеживает редких животных и собирает знания там, "
            "где другие видят только дикую местность."
        ),
    },
    {
        "key": "collector",
        "name": "Коллекционер",
        "aliases": [],
        "emoji": "💎",
        "available": False,
        "description": (
            "Ищет редкие находки, собирает ценные наборы и превращает любопытство "
            "в аккуратную витрину трофеев."
        ),
    },
]

MOONSHINE_STRENGTHS = {
    "weak": {"name": "Слабый", "duration_skill": 24 * 60, "duration_no_skill": 30 * 60},
    "medium": {"name": "Средний", "duration_skill": 36 * 60, "duration_no_skill": 45 * 60},
    "strong": {"name": "Крепкий", "duration_skill": 48 * 60, "duration_no_skill": 60 * 60},
}
MOONSHINE_MASH_RECIPES = [
    {
        "key": "weak_1",
        "number": 1,
        "strength_key": "weak",
        "stars": 1,
        "required_level": 1,
        "payout": 82.50,
    },
    {
        "key": "medium_5",
        "number": 5,
        "strength_key": "medium",
        "stars": 2,
        "required_level": 2,
        "payout": 158.81,
    },
    {
        "key": "strong_9",
        "number": 9,
        "strength_key": "strong",
        "stars": 3,
        "required_level": 3,
        "payout": 247.50,
    },
]
MOONSHINE_SPECIAL_RECIPES = [
    {
        "key": "mahogany_sunrise",
        "name": "Рассвет среди магоний",
        "stars": 3,
        "ingredients": {
            "Консервированная клубника": 1,
            "Черника овальнолистная": 1,
            "Магония": 1,
        },
        "payout": 247.50,
    },
    {
        "key": "berry_apple",
        "name": "Ягодно-яблочный",
        "stars": 2,
        "ingredients": {
            "Яблоко": 1,
            "Ежевика": 1,
            "Цветок ванили": 1,
        },
        "payout": 226.87,
    },
    {
        "key": "berry_cobbler",
        "name": "Ягодный пирог",
        "stars": 2,
        "ingredients": {
            "Консервированные персики": 1,
            "Малина": 1,
            "Персик": 1,
        },
        "payout": 226.87,
    },
    {
        "key": "berry_mint",
        "name": "Ягодно-мятный",
        "stars": 1,
        "ingredients": {
            "Консервированная клубника": 1,
            "Ежевика": 1,
            "Мята": 1,
        },
        "payout": 206.25,
    },
    {
        "key": "evergreen",
        "name": "Хвойный",
        "stars": 2,
        "ingredients": {
            "Черника овальнолистная": 1,
            "Гаультерия": 1,
            "Женьшень": 1,
        },
        "payout": 226.87,
    },
    {
        "key": "poison_poppy",
        "name": "Ядовитый мак",
        "stars": 3,
        "ingredients": {
            "Пустынный мак": 1,
            "Олеандр": 1,
            "Абсент": 1,
        },
        "payout": 247.50,
    },
    {
        "key": "spiced_island",
        "name": "Пряный остров",
        "stars": 3,
        "ingredients": {
            "Консервированные абрикосы": 1,
            "Смородина": 1,
            "Карибский ром": 1,
        },
        "payout": 247.50,
    },
    {
        "key": "tropical_punch",
        "name": "Тропический пунш",
        "stars": 2,
        "ingredients": {
            "Консервированные ананасы": 1,
            "Груша": 1,
            "Цветок ванили": 1,
        },
        "payout": 226.87,
    },
    {
        "key": "wild_cider",
        "name": "Дикий сидр",
        "stars": 1,
        "ingredients": {
            "Яблоко": 1,
            "Женьшень": 1,
            "Смородина": 1,
        },
        "payout": 206.25,
    },
    {
        "key": "wild_creek",
        "name": "Дикий ручей",
        "stars": 3,
        "ingredients": {
            "Мята": 1,
            "Цветок ванили": 1,
            "Слива поручейная": 1,
        },
        "payout": 247.50,
    },
]
MOONSHINE_INGREDIENTS = sorted(
    {
        ingredient
        for recipe in MOONSHINE_SPECIAL_RECIPES
        for ingredient in recipe["ingredients"]
    }
)

# File helpers
def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        return set()
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        return {int(line.strip()) for line in f if line.strip().isdigit()}


def save_channels(channels_set):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        for channel_id in channels_set:
            f.write(f"{channel_id}\n")


def load_env_file():
    if not os.path.exists(ENV_FILE):
        return

    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def today_iso():
    return date.today().isoformat()


def today_msk_iso():
    return datetime.now(MSK_TZ).date().isoformat()


def now_local():
    return datetime.now().astimezone()


def default_economy():
    return {
        "gold_rate": START_GOLD_RATE,
        "gold_rate_date": today_iso(),
        "cash_emoji": DEFAULT_CASH_EMOJI,
        "gold_emoji": DEFAULT_GOLD_EMOJI,
        "map_emoji": DEFAULT_MAP_EMOJI,
        "investment_emoji": DEFAULT_INVESTMENT_EMOJI,
        "stats_emoji": DEFAULT_STATS_EMOJI,
        "moonshine_star_emojis": DEFAULT_MOONSHINE_STAR_EMOJIS.copy(),
        "moonshine_special_emoji": DEFAULT_MOONSHINE_SPECIAL_EMOJI,
        "moonshine_button_emojis": DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy(),
        "treasure_channel_id": None,
        "last_treasure_map_drop_date": None,
        "role_icons": {},
        "role_discounts": {},
        "users": {},
    }


def load_economy():
    if not os.path.exists(ECONOMY_FILE):
        return default_economy()

    try:
        with open(ECONOMY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"{ECONOMY_FILE} поврежён; создаётся новая экономика.")
        return default_economy()

    if not isinstance(data, dict):
        return default_economy()

    data.setdefault("gold_rate", START_GOLD_RATE)
    data.setdefault("gold_rate_date", today_iso())
    data.setdefault("cash_emoji", DEFAULT_CASH_EMOJI)
    data.setdefault("gold_emoji", DEFAULT_GOLD_EMOJI)
    data.setdefault("map_emoji", DEFAULT_MAP_EMOJI)
    data.setdefault("investment_emoji", DEFAULT_INVESTMENT_EMOJI)
    data.setdefault("stats_emoji", DEFAULT_STATS_EMOJI)
    data.setdefault("moonshine_star_emojis", DEFAULT_MOONSHINE_STAR_EMOJIS.copy())
    data.setdefault("moonshine_special_emoji", DEFAULT_MOONSHINE_SPECIAL_EMOJI)
    data.setdefault("moonshine_button_emojis", DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy())
    data.setdefault("treasure_channel_id", None)
    data.setdefault("last_treasure_map_drop_date", None)
    data.setdefault("role_icons", {})
    data.setdefault("role_discounts", {})
    data.setdefault("users", {})
    if not isinstance(data["role_icons"], dict):
        data["role_icons"] = {}
    if not isinstance(data["role_discounts"], dict):
        data["role_discounts"] = {}
    if not isinstance(data["moonshine_star_emojis"], dict):
        data["moonshine_star_emojis"] = DEFAULT_MOONSHINE_STAR_EMOJIS.copy()
    for level, emoji in DEFAULT_MOONSHINE_STAR_EMOJIS.items():
        data["moonshine_star_emojis"].setdefault(level, emoji)
    if not data["moonshine_special_emoji"]:
        data["moonshine_special_emoji"] = DEFAULT_MOONSHINE_SPECIAL_EMOJI
    if not isinstance(data["moonshine_button_emojis"], dict):
        data["moonshine_button_emojis"] = DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy()
    for key, emoji in DEFAULT_MOONSHINE_BUTTON_EMOJIS.items():
        data["moonshine_button_emojis"].setdefault(key, emoji)
    if not isinstance(data["users"], dict):
        data["users"] = {}
    return data


def save_economy():
    with open(ECONOMY_FILE, "w", encoding="utf-8") as f:
        json.dump(economy_data, f, ensure_ascii=False, indent=2)


def parse_local_datetime(value):
    if not value:
        return now_local()

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return now_local()

    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


def parse_local_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return date.today()


def format_number(value, decimals=2):
    text = f"{value:,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",")


def get_cash_emoji():
    return economy_data.get("cash_emoji") or DEFAULT_CASH_EMOJI


def get_gold_emoji():
    return economy_data.get("gold_emoji") or DEFAULT_GOLD_EMOJI


def get_map_emoji():
    return economy_data.get("map_emoji") or DEFAULT_MAP_EMOJI


def get_investment_emoji():
    return economy_data.get("investment_emoji") or DEFAULT_INVESTMENT_EMOJI


def get_stats_emoji():
    return economy_data.get("stats_emoji") or DEFAULT_STATS_EMOJI


def get_moonshine_star_emoji(level):
    emojis = economy_data.get("moonshine_star_emojis", {})
    return emojis.get(str(level)) or DEFAULT_MOONSHINE_STAR_EMOJIS[str(level)]


def get_moonshine_special_emoji():
    return economy_data.get("moonshine_special_emoji") or DEFAULT_MOONSHINE_SPECIAL_EMOJI


def get_moonshine_button_emoji(button_key):
    emojis = economy_data.get("moonshine_button_emojis", {})
    return emojis.get(button_key) or DEFAULT_MOONSHINE_BUTTON_EMOJIS[button_key]


def format_money(value):
    return f"{format_number(value)} {get_cash_emoji()} долларов"


def format_money_plain(value):
    return f"{format_number(value)} долларов"


def format_gold(value):
    return f"{format_number(value)} {get_gold_emoji()} слитков"


def format_gold_plain(value):
    return f"{format_number(value)} слитков"


def format_exchange_rate(value):
    return f"{format_number(value)} {get_cash_emoji()}"


def format_integer(value):
    return f"{int(value):,}".replace(",", " ")


def format_treasure_maps(value):
    return f"{format_integer(value)} {get_map_emoji()} карт сокровищ"


def format_treasure_maps_plain(value):
    return f"{format_integer(value)} карт сокровищ"


def format_gold_price_value(value):
    value = float(value)
    if value.is_integer():
        return format_integer(value)
    return format_number(value, 2)


def format_role_price(value):
    return f"{format_gold_price_value(value)} {get_gold_emoji()} золотых"


def format_percent(value):
    return f"{format_number(value, 1)}%"


def format_progress_percent(value):
    return f"{format_progress_bar(value)} {format_percent(value)}"


def format_collection_showcase(account):
    items = account.get("collection_showcase", [])
    if not items:
        return "пока пусто"
    return ", ".join(str(item) for item in items[:10])


def format_role_balance_sections(guild, account):
    sections = []

    for index, role_definition in enumerate(ROLE_DEFINITIONS):
        role = find_guild_role(guild, role_definition)
        icon = get_role_icon(role_definition, role)
        name = role_definition["name"]
        branch = "└─" if index == len(ROLE_DEFINITIONS) - 1 else "├─"

        if role_definition["key"] == DEALER_ROLE_KEY:
            body = f"🛒 Повозка торговца: {format_progress_percent(account['dealer_wagon'])}"
        elif role_definition["key"] == MOONSHINER_ROLE_KEY:
            moonshine = get_moonshine_account(account)
            body = (
                f"🥃 Самогон: {format_moonshine_bottles(moonshine)}; "
                f"{format_moonshine_batch_status(moonshine)}"
            )
        elif role_definition["key"] == "collector":
            body = "🖼️ Недоступен"
        else:
            body = "🔒 Недоступен"

        sections.append(f"{branch} {icon} {name}: {body}")

    return "\n".join(sections)


def format_progress_bar(value, width=10):
    percent = max(0.0, min(100.0, float(value)))
    filled = round(width * percent / 100)
    return "█" * filled + "░" * (width - filled)


def default_moonshine_data():
    return {
        "upgrade_level": 1,
        "has_condenser": False,
        "has_distiller": False,
        "skill": False,
        "bottles": 0,
        "ingredients": {},
        "batch": None,
    }


def get_moonshine_level(moonshine):
    level = 1
    if moonshine.get("has_condenser"):
        level = 2
    if moonshine.get("has_distiller"):
        level = 3

    try:
        stored_level = int(moonshine.get("upgrade_level", level))
    except (TypeError, ValueError):
        stored_level = level

    return max(1, min(3, max(level, stored_level)))


def set_moonshine_level(moonshine, level):
    level = max(1, min(3, int(level)))
    moonshine["upgrade_level"] = level
    moonshine["has_condenser"] = level >= 2
    moonshine["has_distiller"] = level >= 3


def normalize_moonshine_data(moonshine):
    if not isinstance(moonshine, dict):
        moonshine = default_moonshine_data()

    moonshine.setdefault("upgrade_level", 1)
    moonshine.setdefault("has_condenser", False)
    moonshine.setdefault("has_distiller", False)
    moonshine.setdefault("skill", False)
    moonshine.setdefault("bottles", 0)
    moonshine.setdefault("ingredients", {})
    moonshine.setdefault("batch", None)

    if not isinstance(moonshine["ingredients"], dict):
        moonshine["ingredients"] = {}

    normalized_ingredients = {}
    for ingredient, amount in moonshine["ingredients"].items():
        ingredient_name = resolve_moonshine_ingredient(ingredient)
        if ingredient_name is None:
            continue
        try:
            normalized_amount = max(0, int(amount))
        except (TypeError, ValueError):
            normalized_amount = 0
        if normalized_amount > 0:
            normalized_ingredients[ingredient_name] = normalized_amount

    moonshine["ingredients"] = normalized_ingredients
    set_moonshine_level(moonshine, get_moonshine_level(moonshine))
    try:
        moonshine["bottles"] = max(0, min(20, int(moonshine["bottles"])))
    except (TypeError, ValueError):
        moonshine["bottles"] = 0

    if not isinstance(moonshine.get("batch"), dict):
        moonshine["batch"] = None

    return moonshine


def get_moonshine_account(account):
    account["moonshine"] = normalize_moonshine_data(account.get("moonshine"))
    return account["moonshine"]


def moonshine_text_key(value):
    return " ".join(str(value).strip().split()).casefold()


def resolve_moonshine_ingredient(name):
    normalized = moonshine_text_key(name)
    for ingredient in MOONSHINE_INGREDIENTS:
        if moonshine_text_key(ingredient) == normalized:
            return ingredient
    return None


def get_moonshine_mash_recipe(recipe_key):
    for recipe in MOONSHINE_MASH_RECIPES:
        if recipe["key"] == recipe_key:
            return recipe
    return None


def get_moonshine_special_recipe(recipe_key):
    for recipe in MOONSHINE_SPECIAL_RECIPES:
        if recipe["key"] == recipe_key:
            return recipe
    return None


def get_moonshine_duration_seconds(recipe, skill=False):
    strength_key = recipe.get("strength_key")
    if strength_key is None:
        strength_key = {1: "weak", 2: "medium", 3: "strong"}[recipe["stars"]]

    strength = MOONSHINE_STRENGTHS[strength_key]
    if skill:
        return strength["duration_skill"]
    return strength["duration_no_skill"]


def get_moonshine_recipe_required_level(recipe):
    return int(recipe.get("required_level", recipe.get("stars", 1)))


def get_moonshine_recipe_name(recipe):
    if "name" in recipe:
        return recipe["name"]
    strength = MOONSHINE_STRENGTHS[recipe["strength_key"]]["name"]
    return f"{strength} самогон"


def get_moonshine_bottles(moonshine):
    batch = moonshine.get("batch")
    if not batch:
        return max(0, min(20, int(moonshine.get("bottles", 0))))

    ready_at = parse_local_datetime(batch.get("ready_at"))
    seconds_left = (ready_at - now_local()).total_seconds()
    if seconds_left <= 0:
        return 20

    duration = max(1, float(batch.get("duration_seconds", 1)))
    elapsed = max(0.0, duration - seconds_left)
    return max(0, min(19, int((elapsed / duration) * 20)))


def format_moonshine_bottles(moonshine):
    bottles = get_moonshine_bottles(moonshine)
    percent = bottles / 20 * 100
    return f"{format_progress_bar(percent)} {format_number(percent, 1)}% {bottles}/20 бутылок"


def format_minutes(seconds):
    return f"{max(1, int(seconds // 60))} мин"


def format_moonshine_ingredients(ingredients):
    if not ingredients:
        return "пусто"

    lines = [
        f"{ingredient} x{amount}"
        for ingredient, amount in sorted(ingredients.items())
        if amount > 0
    ]
    if not lines:
        return "пусто"

    text = ", ".join(lines[:12])
    if len(lines) > 12:
        text += f" и ещё {len(lines) - 12}"
    return text


def format_recipe_ingredients(recipe):
    return ", ".join(
        f"{amount}x {ingredient}" for ingredient, amount in recipe["ingredients"].items()
    )


def has_moonshine_ingredients(moonshine, recipe):
    inventory = moonshine.get("ingredients", {})
    return all(inventory.get(ingredient, 0) >= amount for ingredient, amount in recipe["ingredients"].items())


def consume_moonshine_ingredients(moonshine, recipe):
    for ingredient, amount in recipe["ingredients"].items():
        moonshine["ingredients"][ingredient] = max(
            0, moonshine["ingredients"].get(ingredient, 0) - amount
        )
        if moonshine["ingredients"][ingredient] <= 0:
            moonshine["ingredients"].pop(ingredient, None)


def start_moonshine_batch(moonshine, recipe, batch_type):
    skill = bool(moonshine.get("skill"))
    duration = get_moonshine_duration_seconds(recipe, skill=skill)
    started_at = now_local()
    ready_at = started_at + timedelta(seconds=duration)
    moonshine["bottles"] = 0
    moonshine["batch"] = {
        "type": batch_type,
        "recipe_key": recipe["key"],
        "name": get_moonshine_recipe_name(recipe),
        "stars": recipe["stars"],
        "payout": float(recipe["payout"]),
        "started_at": started_at.isoformat(timespec="seconds"),
        "ready_at": ready_at.isoformat(timespec="seconds"),
        "duration_seconds": duration,
    }
    return moonshine["batch"]


def format_moonshine_batch_status(moonshine):
    batch = moonshine.get("batch")
    if not batch:
        return "Котёл свободен"

    ready_at = parse_local_datetime(batch.get("ready_at"))
    seconds_left = (ready_at - now_local()).total_seconds()
    stars = get_moonshine_star_emoji(batch.get("stars", 1))
    if seconds_left <= 0:
        return (
            f"{batch.get('name', 'Самогон')} {stars}: готов к доставке "
            f"за {format_money(batch.get('payout', 0))}"
        )

    return (
        f"{batch.get('name', 'Самогон')} {stars}: осталось "
        f"{format_duration(seconds_left)}"
    )


def format_moonshine_short(account):
    moonshine = get_moonshine_account(account)
    return (
        f"уровень {get_moonshine_level(moonshine)}, "
        f"{format_moonshine_batch_status(moonshine)}"
    )


def grant_random_moonshine_ingredients(account):
    moonshine = get_moonshine_account(account)
    granted = {}
    for ingredient in random.sample(MOONSHINE_INGREDIENTS, k=random.randint(1, 3)):
        moonshine["ingredients"][ingredient] = moonshine["ingredients"].get(ingredient, 0) + 1
        granted[ingredient] = granted.get(ingredient, 0) + 1
    return granted


def format_balance_role_sections(guild, member, account):
    owned_rows = []
    unavailable_sections = []

    for role_definition in ROLE_DEFINITIONS:
        role = find_guild_role(guild, role_definition)
        owns_role = has_game_role(member, role_definition["key"], account)

        if owns_role:
            icon = get_role_icon(role_definition, role)
            name = role_definition["name"]
            if role_definition["key"] == DEALER_ROLE_KEY:
                wagon = account["dealer_wagon"]
                row = f"{icon} {name}: {format_progress_percent(wagon)}"
            elif role_definition["key"] == MOONSHINER_ROLE_KEY:
                moonshine = get_moonshine_account(account)
                row = (
                    f"{icon} {name}: {format_moonshine_bottles(moonshine)}\n"
                    f"   Уровень аппарата: {get_moonshine_level(moonshine)}\n"
                    f"   Статус: {format_moonshine_batch_status(moonshine)}"
                )
            else:
                row = f"{icon} {name}: {format_progress_percent(100)}"
            owned_rows.append(row)
        elif not role_definition["available"]:
            unavailable_sections.append(f"• {role_definition['name']}")

    if owned_rows:
        owned_sections = [
            f"{'└─' if index == len(owned_rows) - 1 else '├─'} {row}"
            for index, row in enumerate(owned_rows)
        ]
    else:
        owned_sections = ["└─ Нет активной профессии"]

    if not unavailable_sections:
        unavailable_sections.append("• Нет")

    return "\n".join(owned_sections), "\n".join(unavailable_sections)


def format_account(account):
    return (
        f"Деньги: **{format_money(account['cash'])}**\n"
        f"Золото: **{format_gold(account['gold'])}**\n"
        f"Вклад: **{format_money(account['deposit'])}**\n"
        f"Карты: **{format_treasure_maps(account['treasure_maps'])}**\n"
        f"Повозка торговца: **{format_percent(account['dealer_wagon'])}**\n"
        f"Самогонщик: **{format_moonshine_short(account)}**\n"
        f"Витрина коллекционных предметов: **{format_collection_showcase(account)}**"
    )


def format_duration(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def is_valid_amount(amount):
    return math.isfinite(amount) and amount > 0


def update_gold_rate():
    current_day = parse_local_date(economy_data.get("gold_rate_date", today_iso()))
    target_day = date.today()
    rate = float(economy_data.get("gold_rate", START_GOLD_RATE))

    if current_day > target_day:
        economy_data["gold_rate_date"] = today_iso()
        return rate

    while current_day < target_day:
        current_day += timedelta(days=1)
        rng = random.Random(f"gold-rate:{current_day.isoformat()}")
        change_percent = rng.uniform(-0.018, 0.022)
        new_rate = round(max(MIN_GOLD_RATE, rate * (1 + change_percent)), 2)

        if new_rate == rate:
            new_rate += 0.01 if rng.random() >= 0.5 else -0.01

        rate = round(max(MIN_GOLD_RATE, new_rate), 2)

    economy_data["gold_rate"] = rate
    economy_data["gold_rate_date"] = today_iso()
    return rate


def get_account(user_id):
    user_key = str(user_id)
    account = economy_data["users"].setdefault(
        user_key,
        {
            "cash": 0.0,
            "gold": 0.0,
            "deposit": 0.0,
            "treasure_maps": 0,
            "owned_roles": [],
            "dealer_wagon": 0.0,
            "moonshine": default_moonshine_data(),
            "collection_showcase": [],
            "deposit_updated_at": now_local().isoformat(timespec="seconds"),
            "last_work_at": None,
        },
    )

    account.setdefault("cash", 0.0)
    account.setdefault("gold", 0.0)
    account.setdefault("deposit", 0.0)
    account.setdefault("treasure_maps", 0)
    account.setdefault("owned_roles", [])
    account.setdefault("dealer_wagon", 0.0)
    account["moonshine"] = normalize_moonshine_data(account.get("moonshine"))
    account.setdefault("collection_showcase", [])
    try:
        account["treasure_maps"] = max(0, int(account["treasure_maps"]))
    except (TypeError, ValueError):
        account["treasure_maps"] = 0
    if not isinstance(account["owned_roles"], list):
        account["owned_roles"] = []
    if not isinstance(account["collection_showcase"], list):
        account["collection_showcase"] = []
    try:
        account["dealer_wagon"] = max(0.0, min(100.0, float(account["dealer_wagon"])))
    except (TypeError, ValueError):
        account["dealer_wagon"] = 0.0
    account.setdefault("deposit_updated_at", now_local().isoformat(timespec="seconds"))
    account.setdefault("last_work_at", None)
    return account


def accrue_deposit_interest(account):
    now = now_local()
    deposit = float(account.get("deposit", 0.0))
    last_update = parse_local_datetime(account.get("deposit_updated_at"))

    if deposit <= 0:
        account["deposit"] = 0.0
        account["deposit_updated_at"] = now.isoformat(timespec="seconds")
        return 0.0  

    seconds_passed = max(0.0, (now - last_update).total_seconds())
    days_passed = seconds_passed / 86400
    new_deposit = deposit * ((1 + DEPOSIT_DAILY_RATE) ** days_passed)

    account["deposit"] = new_deposit
    account["deposit_updated_at"] = now.isoformat(timespec="seconds")
    return new_deposit - deposit


def random_work_reward():
    return min(300, max(20, round(20 + (300 - 20) * (random.random() ** 2.35))))


def get_work_cooldown(account):
    last_work_at = account.get("last_work_at")
    if not last_work_at:
        return 0

    seconds_passed = (now_local() - parse_local_datetime(last_work_at)).total_seconds()
    return max(0, WORK_COOLDOWN_SECONDS - seconds_passed)


def set_non_negative(account, key, value):
    account[key] = max(0.0, float(value))


def get_role_definition(role_key):
    for role_definition in ROLE_DEFINITIONS:
        if role_definition["key"] == role_key:
            return role_definition
    return None


def get_role_definition_for_role(role):
    for role_definition in ROLE_DEFINITIONS:
        if role_name_matches(role, role_definition):
            return role_definition
    return None


def normalize_role_name(name):
    return " ".join(str(name).strip().split()).casefold()


def role_text_matches(role_text, role_definition):
    normalized_role_text = normalize_role_name(role_text)
    names = [role_definition["name"], *role_definition.get("aliases", [])]
    return normalized_role_text in {normalize_role_name(name) for name in names}


def role_name_matches(role, role_definition):
    return role_text_matches(role.name, role_definition)


def find_role_definition_by_name(role_name):
    for role_definition in ROLE_DEFINITIONS:
        if role_text_matches(role_name, role_definition):
            return role_definition
    return None


def find_guild_role(guild, role_definition):
    if guild is None:
        return None

    for role in guild.roles:
        if role_name_matches(role, role_definition):
            return role
    return None


def find_guild_role_by_name(guild, role_name):
    if guild is None:
        return None

    normalized_role_name = normalize_role_name(role_name)
    for role in guild.roles:
        if normalize_role_name(role.name) == normalized_role_name:
            return role
    return None


def resolve_configurable_role(guild, role_name):
    role_definition = find_role_definition_by_name(role_name)
    if role_definition is not None:
        return find_guild_role(guild, role_definition), role_definition

    role = find_guild_role_by_name(guild, role_name)
    if role is None:
        return None, None
    return role, get_role_definition_for_role(role)


def find_member_role(member, role_definition):
    for role in getattr(member, "roles", []):
        if role_name_matches(role, role_definition):
            return role
    return None


def get_role_icon(role_definition, role=None):
    if role is not None:
        configured_icon = economy_data.get("role_icons", {}).get(str(role.id))
        if configured_icon:
            return configured_icon
    return role_definition.get("emoji", "")


def get_role_discount(role):
    if role is None:
        return None

    discount = economy_data.get("role_discounts", {}).get(str(role.id))
    if not isinstance(discount, dict):
        return None

    expires_at = parse_local_datetime(discount.get("expires_at"))
    if expires_at <= now_local():
        economy_data["role_discounts"].pop(str(role.id), None)
        return None

    try:
        price = max(0.0, float(discount.get("price", ROLE_BASE_PRICE)))
    except (TypeError, ValueError):
        economy_data["role_discounts"].pop(str(role.id), None)
        return None

    return {"price": price, "expires_at": expires_at}


def get_role_price(role):
    discount = get_role_discount(role)
    if discount:
        return discount["price"]
    return ROLE_BASE_PRICE


def format_role_price_line(role):
    discount = get_role_discount(role)
    if not discount:
        return f"Цена: **{format_role_price(ROLE_BASE_PRICE)}**"

    expires_text = discount["expires_at"].strftime("%d.%m.%Y")
    return (
        f"Цена: ~~{format_role_price(ROLE_BASE_PRICE)}~~ "
        f"**{format_role_price(discount['price'])}**\n"
        f"Скидка действует до **{expires_text}**."
    )


def has_game_role(member, role_key, account=None):
    role_definition = get_role_definition(role_key)
    if role_definition is None:
        return False

    if account and role_key in account.get("owned_roles", []):
        return True

    return find_member_role(member, role_definition) is not None


def add_owned_role(account, role_key):
    if role_key not in account["owned_roles"]:
        account["owned_roles"].append(role_key)


def remove_expired_role_discounts():
    expired_role_ids = []
    for role_id, discount in economy_data.get("role_discounts", {}).items():
        if not isinstance(discount, dict):
            expired_role_ids.append(role_id)
            continue

        if parse_local_datetime(discount.get("expires_at")) <= now_local():
            expired_role_ids.append(role_id)

    for role_id in expired_role_ids:
        economy_data["role_discounts"].pop(role_id, None)


def get_role_command_hint(role_key):
    if role_key == DEALER_ROLE_KEY:
        return (
            "\n\nКоманды торговца:\n"
            "`/dealer` — заполнить повозку на 10–35%.\n"
            "`/dealer-delivery` — доставить полную повозку и получить 500–625 долларов."
        )
    if role_key == MOONSHINER_ROLE_KEY:
        return (
            "\n\nКоманды самогонщика:\n"
            "`/moonshine` — открыть меню предприятия, выбрать бражку, "
            "добавить особые ингредиенты, купить улучшения и отвезти повозку."
        )
    return ""


def normalize_treasure_maps(account):
    try:
        account["treasure_maps"] = max(0, int(account.get("treasure_maps", 0)))
    except (TypeError, ValueError):
        account["treasure_maps"] = 0
    return account["treasure_maps"]


def grant_treasure_maps_to_all(amount, guild=None):
    granted = 0
    player_ids = {
        user_id
        for user_id, account in economy_data["users"].items()
        if isinstance(account, dict)
    }

    if guild is not None:
        player_ids.update(str(member.id) for member in guild.members if not member.bot)

    for user_id in player_ids:
        account = get_account(user_id)

        normalize_treasure_maps(account)
        account["treasure_maps"] += amount
        granted += 1

    return granted


def build_treasure_drop_embed(granted_count, amount):
    embed = discord.Embed(
        title=f"{get_map_emoji()} Карта сокровищ",
        description="**всем игрокам выдана карта сокровищ!**",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="Получили",
        value=f"**{format_integer(granted_count)} игроков**",
        inline=True,
    )
    embed.add_field(
        name="Выдано каждому",
        value=f"**{format_treasure_maps(amount)}**",
        inline=True,
    )
    embed.add_field(name="Команда", value="`/excavation`", inline=True)
    embed.set_footer(text="Ежедневная выдача в 12:00 по МСК")

    if os.path.exists(TREASURE_BANNER_FILE):
        embed.set_image(url=f"attachment://{TREASURE_BANNER_FILE}")

    return embed


def get_treasure_banner_file():
    if not os.path.exists(TREASURE_BANNER_FILE):
        return None
    return discord.File(TREASURE_BANNER_FILE, filename=TREASURE_BANNER_FILE)


def get_role_image_file():
    if not os.path.exists(ROLE_IMAGE_FILE):
        return None
    return discord.File(ROLE_IMAGE_FILE, filename=ROLE_IMAGE_ATTACHMENT_NAME)


def get_moonshine_image_file():
    if not os.path.exists(MOONSHINE_IMAGE_FILE):
        return None
    return discord.File(MOONSHINE_IMAGE_FILE, filename=MOONSHINE_IMAGE_ATTACHMENT_NAME)


async def resolve_treasure_channel():
    channel_id = economy_data.get("treasure_channel_id")
    if not channel_id:
        return None

    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return None

    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel

    try:
        return await bot.fetch_channel(channel_id)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
        return None


async def send_treasure_drop_announcement(channel, granted_count, amount):
    embed = build_treasure_drop_embed(granted_count, amount)
    banner = get_treasure_banner_file()

    if banner:
        await channel.send(embed=embed, file=banner)
    else:
        await channel.send(embed=embed)


async def run_treasure_map_event(
    amount=TREASURE_MAPS_PER_DROP, scheduled=False, guild=None
):
    scheduled_date = today_msk_iso()
    channel = await resolve_treasure_channel()
    target_guild = guild or getattr(channel, "guild", None)

    async with economy_lock:
        if scheduled and economy_data.get("last_treasure_map_drop_date") == scheduled_date:
            return 0, None, True

        update_gold_rate()
        granted_count = grant_treasure_maps_to_all(amount, guild=target_guild)

        if scheduled:
            economy_data["last_treasure_map_drop_date"] = scheduled_date

        save_economy()

    if channel is not None:
        await send_treasure_drop_announcement(channel, granted_count, amount)

    return granted_count, channel, False


intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
active_channels = load_channels()
economy_data = load_economy()
economy_lock = asyncio.Lock()


def build_roles_embed(guild):
    embed = discord.Embed(
        title="Роли",
        description="Выберите профессию и купите доступную роль за золото.",
        color=discord.Color.gold(),
    )
    if os.path.exists(ROLE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{ROLE_IMAGE_ATTACHMENT_NAME}")

    for role_definition in ROLE_DEFINITIONS:
        role = find_guild_role(guild, role_definition)
        icon = get_role_icon(role_definition, role)
        status = "доступно" if role_definition["available"] else "пока недоступно"
        price_line = format_role_price_line(role)
        role_note = "" if role is not None else "\nDiscord-роль на сервере не найдена."
        embed.add_field(
            name=f"{icon} {role_definition['name']}",
            value=(
                f"{role_definition['description']}\n"
                f"{price_line}\n"
                f"Статус: **{status}**.{role_note}"
            ),
            inline=False,
        )

    embed.set_footer(text="Доступные роли покупаются зелёными кнопками ниже.")
    return embed


async def buy_game_role(interaction, role_key):
    role_definition = get_role_definition(role_key)
    if role_definition is None:
        await interaction.response.send_message("Эта роль не найдена.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    if not role_definition["available"]:
        await interaction.followup.send("Эта роль пока недоступна.", ephemeral=True)
        return

    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.followup.send(
            "Роли можно покупать только на сервере.", ephemeral=True
        )
        return

    member = interaction.user
    role = find_guild_role(interaction.guild, role_definition)
    if role is None:
        await interaction.followup.send(
            f"На сервере нет роли **{role_definition['name']}**. "
            "Администратор должен создать её или переименовать существующую.",
            ephemeral=True,
        )
        return

    if role not in member.roles and hasattr(role, "is_assignable") and not role.is_assignable():
        await interaction.followup.send(
            f"Я не могу выдать роль {role.mention}: она выше роли бота "
            "или управляется Discord.",
            ephemeral=True,
        )
        return

    paid_price = 0.0
    charged = False
    already_owned = False

    async with economy_lock:
        remove_expired_role_discounts()
        update_gold_rate()
        account = get_account(member.id)
        accrue_deposit_interest(account)
        already_owned = role_key in account["owned_roles"] or role in member.roles

        if already_owned:
            add_owned_role(account, role_key)
            save_economy()
        else:
            paid_price = get_role_price(role)
            if account["gold"] + 0.0001 < paid_price:
                save_economy()
                await interaction.followup.send(
                    f"Недостаточно золота. Нужно **{format_role_price(paid_price)}**, "
                    f"а у вас **{format_gold(account['gold'])}**.",
                    ephemeral=True,
                )
                return

            account["gold"] -= paid_price
            add_owned_role(account, role_key)
            charged = True
            save_economy()

    if role not in member.roles:
        try:
            await member.add_roles(role, reason="Покупка игровой роли")
        except (discord.Forbidden, discord.HTTPException) as e:
            if charged:
                async with economy_lock:
                    account = get_account(member.id)
                    account["gold"] += paid_price
                    if role_key in account["owned_roles"]:
                        account["owned_roles"].remove(role_key)
                    save_economy()

            await interaction.followup.send(
                f"Не удалось выдать роль {role.mention}. Покупка отменена: {e}",
                ephemeral=True,
            )
            return

    if already_owned:
        message = f"У вас уже есть роль {role.mention}."
    else:
        message = (
            f"Вы купили роль {role.mention} за **{format_role_price(paid_price)}**."
        )

    message += get_role_command_hint(role_key)
    await interaction.followup.send(message, ephemeral=True)


class RoleBuyButton(discord.ui.Button):
    def __init__(self, role_definition, guild):
        role = find_guild_role(guild, role_definition)
        price = get_role_price(role)
        icon = get_role_icon(role_definition, role)

        if role_definition["available"]:
            label = f"Купить за {format_gold_price_value(price)} золотых"
            style = discord.ButtonStyle.success
            disabled = False
        else:
            label = "Пока недоступно"
            style = discord.ButtonStyle.secondary
            disabled = True

        super().__init__(
            label=label,
            style=style,
            emoji=icon,
            disabled=disabled,
            custom_id=f"role_shop:{role_definition['key']}",
        )
        self.role_key = role_definition["key"]

    async def callback(self, interaction):
        await buy_game_role(interaction, self.role_key)


class RoleShopView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=600)
        for role_definition in ROLE_DEFINITIONS:
            self.add_item(RoleBuyButton(role_definition, guild))


def build_help_pages(is_admin):
    pages = []

    overview = discord.Embed(
        title="Справка бота",
        description=(
            "Бот создаёт треды, ведёт экономику, роли, карты сокровищ, "
            "повозку торговца и админ-настройки сервера."
        ),
        color=discord.Color.gold(),
    )
    overview.add_field(
        name="Страницы",
        value=(
            "**1. Обзор** — разделы справки.\n"
            "**2. Игроки** — основные команды.\n"
            "**3. Торговля и роли** — профессии, повозка и карты.\n"
            "**4. Админ-команды** — управление экономикой и настройками."
        ),
        inline=False,
    )
    overview.add_field(
        name="Быстрый старт",
        value=(
            "`/balance`, `/work`, `/roles`, `/dice`, `/poker`, `/blackjack`, "
            "`/dealer`, `/moonshine`, `/excavation`"
        ),
        inline=False,
    )
    pages.append(overview)

    economy = discord.Embed(
        title="Справка: Игроки",
        description="Команды, доступные обычным игрокам.",
        color=discord.Color.gold(),
    )
    economy.add_field(
        name="Экономика",
        value=(
            "`/balance` — показать деньги, золото, вклад, карты, повозку и витрину.\n"
            "`/work` — заработать 20–300 денег; крупные награды реже.\n"
            "`/gold-rate` — показать текущий курс золота.\n"
            "`/buy-gold amount` — купить золото за деньги.\n"
            "`/sell-gold amount` — продать золото за деньги.\n"
            "`/deposit amount` — положить деньги на вклад.\n"
            "`/withdraw amount` — снять деньги с вклада; `0` снимает всё."
        ),
        inline=False,
    )
    economy.add_field(
        name="Общение",
        value="`/send member message` — отправить личное сообщение участнику через бота.",
        inline=False,
    )
    economy.add_field(
        name="Игры",
        value=(
            "`/dice bet` — кости против бота.\n"
            "`/poker bet` — 5-карточный покер против бота.\n"
            "`/blackjack bet` — blackjack с кнопками Взять/Стоп."
        ),
        inline=False,
    )
    pages.append(economy)

    roles = discord.Embed(
        title="Справка: Торговля и Роли",
        description="Профессии, карты сокровищ и события.",
        color=discord.Color.gold(),
    )
    roles.add_field(
        name="Роли",
        value=(
            "`/roles` — список профессий с описаниями и кнопками покупки.\n"
            "`/dealer` — команда торговца: заполнить повозку на 10–35%.\n"
            "`/dealer-delivery` — доставить полную повозку и получить 500–625 долларов.\n"
            "`/moonshine` — меню самогонщика: бражка, особые ингредиенты, улучшения и доставка."
        ),
        inline=False,
    )
    roles.add_field(
        name="Карты сокровищ",
        value=(
            "`/excavation` — потратить карту и с шансом найти деньги и золото.\n"
            "Карты выдаются каждый день в **12:00 по МСК**."
        ),
        inline=False,
    )
    roles.add_field(
        name="Информация",
        value=(
            f"Курс золота обновляется раз в день.\n"
            f"Вклад растёт на **{format_number(DEPOSIT_DAILY_RATE * 100)}% в день**.\n"
            f"Эмодзи: деньги **{get_cash_emoji()}**, золото **{get_gold_emoji()}**, "
            f"карта **{get_map_emoji()}**, инвестиции **{get_investment_emoji()}**, "
            f"статистика **{get_stats_emoji()}**."
        ),
        inline=False,
    )
    pages.append(roles)

    admin = discord.Embed(
        title="Справка: Админ-команды",
        description="Команды управления серверной экономикой и настройками.",
        color=discord.Color.gold(),
    )
    if is_admin:
        admin.add_field(
            name="Треды",
            value=(
                "`/threads-on channel` — включить автоматические треды.\n"
                "`/threads-off channel` — выключить автоматические треды."
            ),
            inline=False,
        )
        admin.add_field(
            name="Балансы",
            value=(
                "`/check member` — показать баланс участника.\n"
                "`/give-money member amount` — выдать деньги.\n"
                "`/remove-money member amount` — отнять деньги.\n"
                "`/set-money member amount` — установить деньги.\n"
                "`/give-gold member amount` — выдать золото.\n"
                "`/remove-gold member amount` — отнять золото.\n"
                "`/set-gold member amount` — установить золото.\n"
                "`/set-deposit member amount` — установить вклад."
            ),
            inline=False,
        )
        admin.add_field(
            name="Карты и Повозка",
            value=(
                "`/give-map member amount` — выдать карты сокровищ.\n"
                "`/treasure-channel channel` — задать канал объявлений карт.\n"
                "`/treasure-event amount` — выдать всем карты и объявить ивент.\n"
                "`/fill-dealer percent member` — изменить заполнение повозки."
            ),
            inline=False,
        )
        admin.add_field(
            name="Самогонщик",
            value=(
                "`/give-moonshine-ingredient member ingredient amount` — выдать ингредиент.\n"
                "`/remove-moonshine-ingredient member ingredient amount` — забрать ингредиент.\n"
                "`/set-moonshine-upgrade member level` — установить уровень аппарата.\n"
                "`/set-moonshine-skill member enabled` — включить сокращённое время.\n"
                "`/finish-moonshine member` — завершить текущую партию.\n"
                "`/reset-moonshine member` — сбросить состояние самогонщика."
            ),
            inline=False,
        )
        admin.add_field(
            name="Настройки",
            value=(
                "`/set-rate rate` — установить курс золота.\n"
                "`/set-emoji currency emoji` — настроить эмодзи валют, звёзд и кнопок самогона.\n"
                "`/set-icon-roles role emoji` — задать иконку роли в `/roles`.\n"
                "`/set-discounts-roles role price` — скидка на роль на неделю.\n"
                "`/clear-discounts-roles role` — снять скидку с роли.\n"
                "`/reset-work member` — сбросить кулдаун `/work`."
            ),
            inline=False,
        )
    else:
        admin.add_field(
            name="Недоступно",
            value="Эта страница видна всем, но команды может использовать только администрация.",
            inline=False,
        )
    pages.append(admin)

    for index, page in enumerate(pages, start=1):
        page.set_footer(text=f"Страница {index}/{len(pages)}")

    return pages


class HelpPageButton(discord.ui.Button):
    def __init__(self, direction):
        label = "Назад" if direction < 0 else "Вперёд"
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.direction = direction

    async def callback(self, interaction):
        view = self.view
        view.current_page = (view.current_page + self.direction) % len(view.pages)
        await interaction.response.edit_message(
            embed=view.pages[view.current_page], view=view
        )


class HelpView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=600)
        self.pages = pages
        self.current_page = 0
        self.add_item(HelpPageButton(-1))
        self.add_item(HelpPageButton(1))


def validate_bet(amount):
    if amount is None:
        return 0.0, None
    if not math.isfinite(amount) or amount < 0:
        return 0.0, "Ставка должна быть числом от нуля и выше."
    return round(float(amount), 2), None


def build_card_deck():
    return [(rank, suit) for suit in CARD_SUITS for rank in CARD_RANKS]


def format_card(card):
    return f"{card[0]}{card[1]}"


def format_cards(cards):
    return " ".join(format_card(card) for card in cards)


def card_rank_value(rank):
    if rank == "A":
        return 14
    if rank == "K":
        return 13
    if rank == "Q":
        return 12
    if rank == "J":
        return 11
    return int(rank)


def evaluate_poker_hand(cards):
    values = sorted((card_rank_value(rank) for rank, _ in cards), reverse=True)
    suits = [suit for _, suit in cards]
    counts = {value: values.count(value) for value in set(values)}
    grouped = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    unique_values = sorted(set(values), reverse=True)
    is_flush = len(set(suits)) == 1
    is_wheel = set(values) == {14, 5, 4, 3, 2}
    is_straight = len(unique_values) == 5 and (
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
        kickers = sorted([value for value in values if value != grouped[0][0]], reverse=True)
        score = (3, [grouped[0][0], *kickers])
    elif grouped[0][1] == 2 and grouped[1][1] == 2:
        pairs = sorted([value for value, count in grouped if count == 2], reverse=True)
        kicker = max(value for value, count in grouped if count == 1)
        score = (2, [*pairs, kicker])
    elif grouped[0][1] == 2:
        pair = grouped[0][0]
        kickers = sorted([value for value in values if value != pair], reverse=True)
        score = (1, [pair, *kickers])
    else:
        score = (0, values)

    return score, POKER_HAND_NAMES[score[0]]


def blackjack_card_value(card):
    rank, _ = card
    if rank == "A":
        return 11
    if rank in {"K", "Q", "J"}:
        return 10
    return int(rank)


def blackjack_hand_value(cards):
    total = sum(blackjack_card_value(card) for card in cards)
    aces = sum(1 for rank, _ in cards if rank == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


class BlackjackView(discord.ui.View):
    def __init__(self, user_id, bet, deck, player_hand, dealer_hand):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.finished = False
        self.message = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Это не ваша партия blackjack.", ephemeral=True
            )
            return False
        return True

    def build_embed(self, result=None, reveal_dealer=False):
        dealer_cards = format_cards(self.dealer_hand)
        if not reveal_dealer and len(self.dealer_hand) >= 2:
            dealer_cards = f"{format_card(self.dealer_hand[0])} ??"

        dealer_value = blackjack_hand_value(self.dealer_hand)
        player_value = blackjack_hand_value(self.player_hand)
        embed = discord.Embed(title="Blackjack", color=discord.Color.dark_green())
        embed.add_field(
            name="Ваши карты",
            value=f"{format_cards(self.player_hand)}\nСумма: **{player_value}**",
            inline=False,
        )
        dealer_sum = dealer_value if reveal_dealer else blackjack_card_value(self.dealer_hand[0])
        embed.add_field(
            name="Карты дилера",
            value=f"{dealer_cards}\nСумма: **{dealer_sum}**",
            inline=False,
        )
        embed.add_field(name="Ставка", value=format_money(self.bet), inline=True)
        if result:
            embed.add_field(name="Итог", value=result, inline=False)
        return embed

    def disable_buttons(self):
        for item in self.children:
            item.disabled = True

    async def settle(self, outcome):
        if self.finished:
            return ""

        self.finished = True
        self.disable_buttons()

        if outcome == "blackjack":
            payout = round(self.bet * 2.5, 2)
            result = f"Blackjack! Выплата: **{format_money(payout)}**."
        elif outcome == "win":
            payout = round(self.bet * 2, 2)
            result = f"Вы выиграли. Выплата: **{format_money(payout)}**."
        elif outcome == "push":
            payout = self.bet
            result = f"Ничья. Ставка возвращена: **{format_money(payout)}**."
        elif outcome == "timeout":
            payout = self.bet
            result = f"Партия истекла по времени. Ставка возвращена: **{format_money(payout)}**."
        else:
            payout = 0.0
            result = "Вы проиграли. Ставка остаётся у дилера."

        if payout > 0:
            async with economy_lock:
                account = get_account(self.user_id)
                account["cash"] += payout
                save_economy()

        return result

    async def dealer_play(self):
        while blackjack_hand_value(self.dealer_hand) < 17 and self.deck:
            self.dealer_hand.append(self.deck.pop())

        player_value = blackjack_hand_value(self.player_hand)
        dealer_value = blackjack_hand_value(self.dealer_hand)
        if dealer_value > 21 or player_value > dealer_value:
            return "win"
        if player_value == dealer_value:
            return "push"
        return "loss"

    @discord.ui.button(label="Взять", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction, button):
        self.player_hand.append(self.deck.pop())
        if blackjack_hand_value(self.player_hand) > 21:
            result = await self.settle("loss")
            await interaction.response.edit_message(
                embed=self.build_embed(result=result, reveal_dealer=True), view=self
            )
            return

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Стоп", style=discord.ButtonStyle.secondary)
    async def stand_button(self, interaction, button):
        outcome = await self.dealer_play()
        result = await self.settle(outcome)
        await interaction.response.edit_message(
            embed=self.build_embed(result=result, reveal_dealer=True), view=self
        )

    async def on_timeout(self):
        if self.finished:
            return

        result = await self.settle("timeout")
        if self.message is not None:
            try:
                await self.message.edit(
                    embed=self.build_embed(result=result, reveal_dealer=True),
                    view=self,
                )
            except discord.HTTPException:
                pass


def build_moonshine_embed(guild, account):
    moonshine = get_moonshine_account(account)
    role_definition = get_role_definition(MOONSHINER_ROLE_KEY)
    role = find_guild_role(guild, role_definition)
    icon = get_role_icon(role_definition, role)
    level = get_moonshine_level(moonshine)
    condenser = "куплен" if moonshine.get("has_condenser") else "не куплен"
    distiller = "куплен" if moonshine.get("has_distiller") else "не куплен"
    skill = "активен" if moonshine.get("skill") else "нет"
    batch = moonshine.get("batch")
    storage = format_moonshine_ingredients(moonshine.get("ingredients", {}))
    storage_icon = "📦" if storage != "пусто" else "🫙"

    if batch:
        ready_at = parse_local_datetime(batch.get("ready_at"))
        seconds_left = (ready_at - now_local()).total_seconds()
        if seconds_left <= 0:
            progress_line = (
                f"├─ 🍾 Бутылки: {format_moonshine_bottles(moonshine)}\n"
                f"└─ 📦 Повозка: готова к отправке за {format_money(batch.get('payout', 0))}"
            )
        else:
            progress_line = (
                f"├─ 🍾 Бутылки: {format_moonshine_bottles(moonshine)}\n"
                f"└─ ⏳ Варка: осталось {format_duration(seconds_left)}"
            )
    else:
        progress_line = (
            f"├─ 🍾 Бутылки: {format_moonshine_bottles(moonshine)}\n"
            "└─ 🧊 Котёл свободен"
        )

    embed = discord.Embed(
        title=f"{icon} Предприятие самогонщика",
        description=(
            "**Марсель:** Добрый день, босс. Какой самогон будем готовить на этот раз?\n\n"
            "🥃 Производство\n"
            f"├─ 🏷️ Уровень аппарата: **{level}**\n"
            f"├─ ⭐ Доступ: **{get_moonshine_star_emoji(level)}**\n"
            f"{progress_line}\n\n"
            "⚙️ Оборудование\n"
            f"├─ 🧊 Конденсатор: **{condenser}**\n"
            f"├─ 🟠 Медный дистиллятор: **{distiller}**\n"
            f"└─ ⏱️ Навык самогонщика: **{skill}**\n\n"
            f"{storage_icon} Склад ингредиентов\n"
            f"└─ {storage}\n\n"
            "💵 Финансы\n"
            f"├─ Наличные: **{format_money(account['cash'])}**\n"
            f"├─ Конденсатор: **{format_money(MOONSHINE_CONDENSER_PRICE)}**\n"
            f"└─ Медный дистиллятор: **{format_money(MOONSHINE_DISTILLER_PRICE)}**"
        ),
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(MOONSHINE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{MOONSHINE_IMAGE_ATTACHMENT_NAME}")
    embed.set_footer(text="Клад из /excavation может принести ингредиенты для особых рецептов.")
    return embed


def build_moonshine_mash_embed(moonshine):
    level = get_moonshine_level(moonshine)
    lines = []
    for recipe in MOONSHINE_MASH_RECIPES:
        strength = MOONSHINE_STRENGTHS[recipe["strength_key"]]
        required_level = get_moonshine_recipe_required_level(recipe)
        duration = get_moonshine_duration_seconds(
            recipe, skill=bool(moonshine.get("skill"))
        )
        lock = "" if required_level <= level else " 🔒"
        lines.append(
            f"Бражка #{recipe['number']} — {strength['name']} "
            f"{get_moonshine_star_emoji(recipe['stars'])}{lock}: "
            f"{format_minutes(duration)}, выручка {format_money(recipe['payout'])}"
        )

    embed = discord.Embed(
        title="Выбрать бражку",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text="Бражка #5 открывается конденсатором, #9 — медным дистиллятором.")
    return embed


def build_moonshine_special_embed(moonshine):
    level = get_moonshine_level(moonshine)
    lines = []
    for recipe in sorted(MOONSHINE_SPECIAL_RECIPES, key=lambda item: (item["stars"], item["name"])):
        lock = "" if recipe["stars"] <= level else " 🔒"
        status = "есть" if has_moonshine_ingredients(moonshine, recipe) else "не хватает"
        lines.append(
            f"{get_moonshine_special_emoji()} **{recipe['name']}** "
            f"{get_moonshine_star_emoji(recipe['stars'])}{lock}: "
            f"основа — бражка {recipe['stars']} уровня, "
            f"выручка за доставку {format_money(recipe['payout'])}, "
            f"ингредиенты: {status}"
        )

    embed = discord.Embed(
        title="Особые ингредиенты",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    embed.set_footer(text="Особый самогон открывается по уровню доступной бражки; сумма — выручка за доставку повозки.")
    return embed


async def ensure_moonshiner(interaction):
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "Команду можно использовать только на сервере.", ephemeral=True
        )
        return None

    async with economy_lock:
        account = get_account(interaction.user.id)
        if has_game_role(interaction.user, MOONSHINER_ROLE_KEY, account):
            return account
        save_economy()

    await interaction.response.send_message(
        "Команда доступна только роли **Самогонщик**. Купить её можно через `/roles`.",
        ephemeral=True,
    )
    return None


async def deliver_moonshine_batch(interaction):
    async with economy_lock:
        account = get_account(interaction.user.id)
        moonshine = get_moonshine_account(account)
        batch = moonshine.get("batch")
        if not batch:
            save_economy()
            await interaction.response.send_message(
                "Марсель: Повозка пока пустая, босс. Сначала поставим партию.",
                ephemeral=True,
            )
            return

        ready_at = parse_local_datetime(batch.get("ready_at"))
        seconds_left = (ready_at - now_local()).total_seconds()
        if seconds_left > 0:
            save_economy()
            await interaction.response.send_message(
                f"Марсель: Самогон ещё доходит. Осталось **{format_duration(seconds_left)}**.",
                ephemeral=True,
            )
            return

        payout = float(batch.get("payout", 0.0))
        name = batch.get("name", "Самогон")
        account["cash"] += payout
        moonshine["batch"] = None
        save_economy()

    await interaction.response.send_message(
        f"{interaction.user.mention}, повозка отвезена. "
        f"**{name}** продан за **{format_money(payout)}**."
    )


class MoonshineOwnerView(discord.ui.View):
    def __init__(self, user_id, timeout=600):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Это меню открыто не для вас.", ephemeral=True
            )
            return False
        return True


class MoonshineMashSelect(discord.ui.Select):
    def __init__(self, moonshine):
        level = get_moonshine_level(moonshine)
        options = []
        for recipe in MOONSHINE_MASH_RECIPES:
            if recipe["stars"] > level:
                continue
            strength = MOONSHINE_STRENGTHS[recipe["strength_key"]]
            duration = get_moonshine_duration_seconds(
                recipe, skill=bool(moonshine.get("skill"))
            )
            options.append(
                discord.SelectOption(
                    label=f"{strength['name']} / {recipe['stars']} зв.",
                    value=recipe["key"],
                    description=(
                        f"{format_minutes(duration)} · выручка "
                        f"{format_number(recipe['payout'])}"
                    ),
                )
            )

        super().__init__(
            placeholder="Выберите бражку",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        recipe = get_moonshine_mash_recipe(self.values[0])
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            if moonshine.get("batch"):
                save_economy()
                await interaction.response.send_message(
                    "Марсель: Один котёл уже занят. Дождёмся готовности партии.",
                    ephemeral=True,
                )
                return

            if recipe["stars"] > get_moonshine_level(moonshine):
                save_economy()
                await interaction.response.send_message(
                    "Для этой бражки нужен апгрейд оборудования.",
                    ephemeral=True,
                )
                return

            batch = start_moonshine_batch(moonshine, recipe, "mash")
            save_economy()

        await interaction.response.send_message(
            f"Марсель ставит партию: **{batch['name']}**.\n"
            f"Готовность через **{format_minutes(batch['duration_seconds'])}**. "
            f"Выручка: **{format_money(batch['payout'])}**.",
            ephemeral=True,
        )


class MoonshineMashView(MoonshineOwnerView):
    def __init__(self, user_id, moonshine):
        super().__init__(user_id)
        self.add_item(MoonshineMashSelect(moonshine))


class MoonshineSpecialSelect(discord.ui.Select):
    def __init__(self, moonshine):
        level = get_moonshine_level(moonshine)
        options = []
        for recipe in sorted(MOONSHINE_SPECIAL_RECIPES, key=lambda item: (item["stars"], item["name"])):
            if recipe["stars"] > level:
                continue
            status = "готово" if has_moonshine_ingredients(moonshine, recipe) else "не хватает"
            options.append(
                discord.SelectOption(
                    label=recipe["name"],
                    value=recipe["key"],
                    description=f"{recipe['stars']} ур. бражки · выручка {format_number(recipe['payout'])} · {status}",
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="Нет доступных рецептов",
                    value="none",
                    description="Купите улучшение оборудования",
                )
            )

        super().__init__(
            placeholder="Выберите особый самогон",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "Марсель: Пока нет доступных особых рецептов.", ephemeral=True
            )
            return

        recipe = get_moonshine_special_recipe(self.values[0])
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            if moonshine.get("batch"):
                save_economy()
                await interaction.response.send_message(
                    "Марсель: Один котёл уже занят. Дождёмся готовности партии.",
                    ephemeral=True,
                )
                return

            if recipe["stars"] > get_moonshine_level(moonshine):
                save_economy()
                await interaction.response.send_message(
                    "Для этой основы нужна бражка такого же уровня. Улучшите оборудование.",
                    ephemeral=True,
                )
                return

            if not has_moonshine_ingredients(moonshine, recipe):
                missing = [
                    f"{ingredient} x{amount - moonshine['ingredients'].get(ingredient, 0)}"
                    for ingredient, amount in recipe["ingredients"].items()
                    if moonshine["ingredients"].get(ingredient, 0) < amount
                ]
                save_economy()
                await interaction.response.send_message(
                    "Не хватает ингредиентов: **" + ", ".join(missing) + "**.",
                    ephemeral=True,
                )
                return

            consume_moonshine_ingredients(moonshine, recipe)
            batch = start_moonshine_batch(moonshine, recipe, "special")
            save_economy()

        await interaction.response.send_message(
            f"Марсель добавил особые ингредиенты: **{batch['name']}**.\n"
            f"Основа: **бражка {recipe['stars']} уровня**. "
            f"Готовность через **{format_minutes(batch['duration_seconds'])}**. "
            f"Выручка: **{format_money(batch['payout'])}**.",
            ephemeral=True,
        )


class MoonshineSpecialView(MoonshineOwnerView):
    def __init__(self, user_id, moonshine):
        super().__init__(user_id)
        self.add_item(MoonshineSpecialSelect(moonshine))


class MoonshineUpgradeView(MoonshineOwnerView):
    @discord.ui.button(label="Конденсатор $825", style=discord.ButtonStyle.success)
    async def condenser_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            if moonshine.get("has_condenser"):
                save_economy()
                await interaction.response.send_message(
                    "Конденсатор уже куплен.", ephemeral=True
                )
                return

            if account["cash"] + 0.0001 < MOONSHINE_CONDENSER_PRICE:
                save_economy()
                await interaction.response.send_message(
                    f"Не хватает денег. Нужно **{format_money(MOONSHINE_CONDENSER_PRICE)}**, "
                    f"у вас **{format_money(account['cash'])}**.",
                    ephemeral=True,
                )
                return

            account["cash"] -= MOONSHINE_CONDENSER_PRICE
            moonshine["has_condenser"] = True
            set_moonshine_level(moonshine, 2)
            save_economy()

        await interaction.response.send_message(
            "Конденсатор куплен. Открыт самогон **2 уровня**.",
            ephemeral=True,
        )

    @discord.ui.button(label="Медный дистиллятор $875", style=discord.ButtonStyle.success)
    async def distiller_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            if moonshine.get("has_distiller"):
                save_economy()
                await interaction.response.send_message(
                    "Медный дистиллятор уже куплен.", ephemeral=True
                )
                return

            if not moonshine.get("has_condenser"):
                save_economy()
                await interaction.response.send_message(
                    "Сначала купите конденсатор для 2 уровня.", ephemeral=True
                )
                return

            if account["cash"] + 0.0001 < MOONSHINE_DISTILLER_PRICE:
                save_economy()
                await interaction.response.send_message(
                    f"Не хватает денег. Нужно **{format_money(MOONSHINE_DISTILLER_PRICE)}**, "
                    f"у вас **{format_money(account['cash'])}**.",
                    ephemeral=True,
                )
                return

            account["cash"] -= MOONSHINE_DISTILLER_PRICE
            moonshine["has_distiller"] = True
            set_moonshine_level(moonshine, 3)
            save_economy()

        await interaction.response.send_message(
            "Медный дистиллятор куплен. Открыт самогон **3 уровня**.",
            ephemeral=True,
        )


class MoonshineMainView(MoonshineOwnerView):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.choose_mash_button.emoji = get_moonshine_button_emoji("mash")
        self.special_button.emoji = get_moonshine_button_emoji("special")
        self.upgrades_button.emoji = get_moonshine_button_emoji("upgrades")
        self.deliver_button.emoji = get_moonshine_button_emoji("delivery")

    @discord.ui.button(label="Выбрать бражку", style=discord.ButtonStyle.primary, row=0)
    async def choose_mash_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            embed = build_moonshine_mash_embed(moonshine)
            view = MoonshineMashView(interaction.user.id, moonshine)
            save_economy()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Добавить особые ингредиенты", style=discord.ButtonStyle.primary, row=0)
    async def special_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            embed = build_moonshine_special_embed(moonshine)
            view = MoonshineSpecialView(interaction.user.id, moonshine)
            save_economy()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Купить улучшения", style=discord.ButtonStyle.secondary, row=0)
    async def upgrades_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            level = get_moonshine_level(moonshine)
            save_economy()

        embed = discord.Embed(
            title="Улучшения самогонщика",
            description=(
                f"Текущий уровень оборудования: **{level}**\n"
                f"Конденсатор: **{format_money(MOONSHINE_CONDENSER_PRICE)}** — открывает 2 уровень.\n"
                f"Медный дистиллятор: **{format_money(MOONSHINE_DISTILLER_PRICE)}** — открывает 3 уровень."
            ),
            color=discord.Color.dark_gold(),
        )
        await interaction.response.send_message(
            embed=embed,
            view=MoonshineUpgradeView(interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(label="Отвезти повозку", style=discord.ButtonStyle.success, row=0)
    async def deliver_button(self, interaction, button):
        await deliver_moonshine_batch(interaction)


@tasks.loop(time=time(hour=12, minute=0, tzinfo=MSK_TZ))
async def daily_treasure_map_event():
    try:
        granted_count, channel, skipped = await run_treasure_map_event(scheduled=True)
    except discord.HTTPException as e:
        print(f"Ежедневная выдача карт сохранена, но объявление не отправилось: {e}")
        return

    if skipped:
        return

    if channel is None:
        print(
            "Ежедневная карта сокровищ выдана, но канал объявлений не настроен "
            f"или недоступен. Игроков: {granted_count}"
        )


@daily_treasure_map_event.before_loop
async def before_daily_treasure_map_event():
    await bot.wait_until_ready()


async def sync_commands():
    """Register slash commands so they appear in Discord's input suggestions."""
    guilds = bot.guilds

    # Global sync is useful for production, but Discord can cache it for a while.
    try:
        global_commands = await bot.tree.sync()
        print(f"Глобальные команды синхронизированы: {len(global_commands)}")
    except Exception as e:
        print(f"Синхронизация глобальных команд не удалась: {e}")

    # Guild sync appears in the Discord client almost immediately.
    for guild in guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            guild_commands = await bot.tree.sync(guild=guild)
            print(
                f"Команды синхронизированы для сервера '{guild.name}': "
                f"{len(guild_commands)}"
            )
        except Exception as e:
            print(f"Синхронизация команд не удалась для сервера '{guild.name}': {e}")


@bot.event
async def on_ready():
    global COMMANDS_SYNCED

    print(f"Бот {bot.user.name} запущен!")
    if not daily_treasure_map_event.is_running():
        daily_treasure_map_event.start()

    if COMMANDS_SYNCED:
        return

    try:
        await sync_commands()
        COMMANDS_SYNCED = True
    except Exception as e:
        print(f"Command sync failed: {e}")


@bot.tree.command(
    name="threads-on",
    description="Включить автоматические треды в канале",
)
@app_commands.describe(channel="Канал, в котором бот будет создавать треды")
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def attach_channel(
    interaction: discord.Interaction, channel: discord.TextChannel
):
    channel_id = channel.id

    if channel_id in active_channels:
        await interaction.response.send_message(
            f"Автоматические треды уже включены в {channel.mention}.",
            ephemeral=True,
        )
    else:
        active_channels.add(channel_id)
        save_channels(active_channels)
        await interaction.response.send_message(
            f"Автоматические треды теперь включены в {channel.mention}.",
            ephemeral=True,
        )


@bot.tree.command(
    name="threads-off", description="Выключить автоматические треды в канале"
)
@app_commands.describe(channel="Канал, в котором бот перестанет создавать треды")
@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.has_permissions(manage_channels=True)
async def detach_channel(
    interaction: discord.Interaction, channel: discord.TextChannel
):
    channel_id = channel.id

    if channel_id in active_channels:
        active_channels.remove(channel_id)
        save_channels(active_channels)
        await interaction.response.send_message(
            f"Автоматические треды **выключены** в {channel.mention}.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            f"Автоматические треды уже были выключены в {channel.mention}.",
            ephemeral=True,
        )


# Permission error handler for thread setup commands.
@attach_channel.error
@detach_channel.error
async def slash_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        message = (
            "У вас недостаточно прав. Требуется право 'Управление каналами' "
            "для настройки этой команды."
        )
    else:
        message = f"Команда не удалась: {error}"

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="help", description="Показать возможности бота")
async def help_command(interaction: discord.Interaction):
    is_admin = False
    if isinstance(interaction.user, discord.Member):
        is_admin = interaction.user.guild_permissions.administrator

    pages = build_help_pages(is_admin)
    await interaction.response.send_message(
        embed=pages[0], view=HelpView(pages), ephemeral=True
    )


@bot.tree.command(name="roles", description="Показать игровые роли и купить доступные")
async def roles_command(interaction: discord.Interaction):
    async with economy_lock:
        remove_expired_role_discounts()
        save_economy()
        embed = build_roles_embed(interaction.guild)
        view = RoleShopView(interaction.guild)

    role_image = get_role_image_file()
    if role_image:
        await interaction.response.send_message(
            embed=embed, view=view, file=role_image, ephemeral=True
        )
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="send", description="Отправить личное сообщение участнику")
@app_commands.describe(member="Получатель сообщения", message="Текст сообщения")
async def send_private_message_command(
    interaction: discord.Interaction, member: discord.Member, message: str
):
    text = message.strip()
    if not text:
        await interaction.response.send_message(
            "Сообщение не должно быть пустым.", ephemeral=True
        )
        return

    if len(text) > 1700:
        await interaction.response.send_message(
            "Сообщение слишком длинное. Максимум 1700 символов.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    sender_name = interaction.user.display_name
    dm_text = f"Сообщение от {sender_name} ({interaction.user.mention}):\n{text}"

    try:
        await member.send(dm_text)
    except discord.Forbidden:
        await interaction.followup.send(
            f"Не удалось отправить сообщение {member.mention}: личные сообщения закрыты.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as e:
        await interaction.followup.send(
            f"Не удалось отправить сообщение {member.mention}: {e}",
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        f"Сообщение отправлено {member.mention}.", ephemeral=True
    )


@bot.tree.command(name="balance", description="Показать ваш баланс")
async def balance_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with economy_lock:
        rate = update_gold_rate()
        account = get_account(interaction.user.id)
        interest = accrue_deposit_interest(account)
        save_economy()

        cash = account["cash"]
        gold = account["gold"]
        deposit = account["deposit"]
        treasure_maps = account["treasure_maps"]
        role_sections, unavailable_role_sections = format_balance_role_sections(
            interaction.guild, interaction.user, account
        )

    description = (
        "💰 Финансы\n"
        f"├─ {get_cash_emoji()} Деньги: {format_money_plain(cash)}\n"
        f"├─ {get_gold_emoji()} Золото: {format_gold_plain(gold)}\n"
        f"└─ {get_map_emoji()} Карты: {format_treasure_maps_plain(treasure_maps)}\n\n"
        "🎭 Роли\n"
        f"{role_sections}\n"
        "\n"
        "🏦 Банк\n"
        f"├─ {get_investment_emoji()} Вклад: {format_money_plain(deposit)}\n"
        f"├─ Доход: +{format_money_plain(interest)}\n"
        f"└─ Курс: 1 {get_gold_emoji()} = {format_exchange_rate(rate)}\n\n"
        "🔒 Недоступные роли\n"
        f"{unavailable_role_sections}"
    )
    embed = discord.Embed(
        title=f"{get_stats_emoji()}Статистика",
        description=description,
        color=discord.Color.dark_gold(),
    )

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="work", description="Заработать случайную сумму денег")
async def work_command(interaction: discord.Interaction):
    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)
        cooldown = get_work_cooldown(account)

        if cooldown > 0:
            save_economy()
            message = (
                "Вы недавно работали. "
                f"Вы сможете снова работать через **{format_duration(cooldown)}**."
            )
            await interaction.response.send_message(message, ephemeral=True)
            return

        reward = random_work_reward()
        account["cash"] += reward
        account["last_work_at"] = now_local().isoformat(timespec="seconds")
        save_economy()

    await interaction.response.send_message(
        f"{interaction.user.mention}, вы поработали и получили **{format_money(reward)}**."
    )


@bot.tree.command(name="dice", description="Сыграть в кости с ботом")
@app_commands.describe(bet="Ставка деньгами. 0 — без ставки")
async def dice_command(interaction: discord.Interaction, bet: float = 0.0):
    bet, error = validate_bet(bet)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    player_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)

    async with economy_lock:
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)
        if account["cash"] + 0.0001 < bet:
            save_economy()
            await interaction.response.send_message(
                f"Недостаточно денег для ставки **{format_money(bet)}**. "
                f"У вас **{format_money(account['cash'])}**.",
                ephemeral=True,
            )
            return

        if player_roll > bot_roll:
            account["cash"] += bet
            result = f"Вы выиграли **{format_money(bet)}**."
        elif player_roll < bot_roll:
            account["cash"] -= bet
            result = f"Вы проиграли **{format_money(bet)}**."
        else:
            result = "Ничья. Ставка возвращается."

        save_economy()

    await interaction.response.send_message(
        f"🎲 {interaction.user.mention}: **{player_roll}**\n"
        f"🎲 Бот: **{bot_roll}**\n"
        f"{result}"
    )


@bot.tree.command(name="poker", description="Сыграть 5-карточный покер с ботом")
@app_commands.describe(bet="Ставка деньгами. 0 — без ставки")
async def poker_command(interaction: discord.Interaction, bet: float = 0.0):
    bet, error = validate_bet(bet)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    deck = build_card_deck()
    random.shuffle(deck)
    player_hand = [deck.pop() for _ in range(5)]
    bot_hand = [deck.pop() for _ in range(5)]
    player_score, player_name = evaluate_poker_hand(player_hand)
    bot_score, bot_name = evaluate_poker_hand(bot_hand)

    async with economy_lock:
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)
        if account["cash"] + 0.0001 < bet:
            save_economy()
            await interaction.response.send_message(
                f"Недостаточно денег для ставки **{format_money(bet)}**. "
                f"У вас **{format_money(account['cash'])}**.",
                ephemeral=True,
            )
            return

        if player_score > bot_score:
            account["cash"] += bet
            result = f"Вы выиграли **{format_money(bet)}**."
        elif player_score < bot_score:
            account["cash"] -= bet
            result = f"Вы проиграли **{format_money(bet)}**."
        else:
            result = "Ничья. Ставка возвращается."

        save_economy()

    await interaction.response.send_message(
        f"🃏 {interaction.user.mention}: **{format_cards(player_hand)}** — {player_name}\n"
        f"🃏 Бот: **{format_cards(bot_hand)}** — {bot_name}\n"
        f"{result}"
    )


@bot.tree.command(name="blackjack", description="Сыграть blackjack с дилером")
@app_commands.describe(bet="Ставка деньгами. 0 — без ставки")
async def blackjack_command(interaction: discord.Interaction, bet: float = 0.0):
    bet, error = validate_bet(bet)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    async with economy_lock:
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)
        if account["cash"] + 0.0001 < bet:
            save_economy()
            await interaction.response.send_message(
                f"Недостаточно денег для ставки **{format_money(bet)}**. "
                f"У вас **{format_money(account['cash'])}**.",
                ephemeral=True,
            )
            return

        account["cash"] -= bet
        save_economy()

    deck = build_card_deck()
    random.shuffle(deck)
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]
    view = BlackjackView(interaction.user.id, bet, deck, player_hand, dealer_hand)

    await interaction.response.defer()
    player_blackjack = blackjack_hand_value(player_hand) == 21
    dealer_blackjack = blackjack_hand_value(dealer_hand) == 21

    if player_blackjack or dealer_blackjack:
        if player_blackjack and dealer_blackjack:
            outcome = "push"
        elif player_blackjack:
            outcome = "blackjack"
        else:
            outcome = "loss"

        result = await view.settle(outcome)
        await interaction.followup.send(
            embed=view.build_embed(result=result, reveal_dealer=True), view=view
        )
        return

    view.message = await interaction.followup.send(
        embed=view.build_embed(), view=view, wait=True
    )


@bot.tree.command(name="excavation", description="Использовать карту сокровищ для раскопок")
async def excavation_command(interaction: discord.Interaction):
    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)

        if account["treasure_maps"] <= 0:
            save_economy()
            await interaction.response.send_message(
                f"У вас нет {get_map_emoji()} карт сокровищ. Дождитесь ежедневной выдачи.",
                ephemeral=True,
            )
            return

        account["treasure_maps"] -= 1
        found_treasure = random.random() < EXCAVATION_REWARD_CHANCE

        if found_treasure:
            cash_reward = random.randint(80, 200)
            gold_reward = round(random.uniform(0.5, 3.9), 2)
            ingredients_reward = grant_random_moonshine_ingredients(account)
            account["cash"] += cash_reward
            account["gold"] += gold_reward
            ingredients_text = ", ".join(
                f"{ingredient} x{amount}"
                for ingredient, amount in sorted(ingredients_reward.items())
            )
            message = (
                f"{interaction.user.mention}, вы использовали **1 {get_map_emoji()} карту** "
                f"и нашли клад: **{format_money(cash_reward)}** и "
                f"**{format_gold(gold_reward)}**!\n"
                f"Ингредиенты: **{ingredients_text}**.\n"
                f"Осталось карт: **{format_treasure_maps(account['treasure_maps'])}**."
            )
        else:
            message = (
                f"{interaction.user.mention}, вы использовали **1 {get_map_emoji()} карту**, "
                "но раскопки ничего не дали.\n"
                f"Осталось карт: **{format_treasure_maps(account['treasure_maps'])}**."
            )

        save_economy()

    await interaction.response.send_message(message)


@bot.tree.command(name="dealer", description="Торговец: заполнить повозку товарами")
async def dealer_command(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "Эту команду можно использовать только на сервере.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)

        if not has_game_role(interaction.user, DEALER_ROLE_KEY, account):
            save_economy()
            await interaction.response.send_message(
                "Команда доступна только роли **Торговец**. Купить её можно через `/roles`.",
                ephemeral=True,
            )
            return

        old_fill = account["dealer_wagon"]
        if old_fill >= 100:
            save_economy()
            await interaction.response.send_message(
                "Повозка уже заполнена на **100%**.", ephemeral=True
            )
            return

        added_fill = random.randint(DEALER_MIN_FILL, DEALER_MAX_FILL)
        account["dealer_wagon"] = min(100.0, old_fill + added_fill)
        actual_added = account["dealer_wagon"] - old_fill
        save_economy()

    await interaction.response.send_message(
        f"{interaction.user.mention}, вы загрузили повозку на "
        f"**+{format_percent(actual_added)}**.\n"
        f"Текущее заполнение: **{format_percent(account['dealer_wagon'])}**."
    )


@bot.tree.command(name="dealer-delivery", description="Торговец: доставить полную повозку")
async def dealer_delivery_command(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "Эту команду можно использовать только на сервере.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)

        if not has_game_role(interaction.user, DEALER_ROLE_KEY, account):
            save_economy()
            await interaction.response.send_message(
                "Команда доступна только роли **Торговец**. Купить её можно через `/roles`.",
                ephemeral=True,
            )
            return

        if account["dealer_wagon"] < 100:
            current_fill = account["dealer_wagon"]
            save_economy()
            await interaction.response.send_message(
                "Для доставки нужна повозка, заполненная на **100%**.\n"
                f"Сейчас заполнено: **{format_percent(current_fill)}**.",
                ephemeral=True,
            )
            return

        reward = random.randint(DEALER_DELIVERY_MIN_REWARD, DEALER_DELIVERY_MAX_REWARD)
        account["dealer_wagon"] = 0.0
        account["cash"] += reward
        save_economy()

    await interaction.response.send_message(
        f"{interaction.user.mention}, доставка завершена! Вы получили "
        f"**{format_money(reward)}**.\n"
        "Повозка снова пустая: **0,0%**."
    )


@bot.tree.command(name="moonshine", description="Самогонщик: открыть меню предприятия")
async def moonshine_command(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "Эту команду можно использовать только на сервере.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)

        if not has_game_role(interaction.user, MOONSHINER_ROLE_KEY, account):
            save_economy()
            await interaction.response.send_message(
                "Команда доступна только роли **Самогонщик**. Купить её можно через `/roles`.",
                ephemeral=True,
            )
            return

        embed = build_moonshine_embed(interaction.guild, account)
        save_economy()

    image = get_moonshine_image_file()
    view = MoonshineMainView(interaction.user.id)
    if image:
        await interaction.response.send_message(
            embed=embed, view=view, file=image, ephemeral=True
        )
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="gold-rate", description="Показать текущий курс золота")
async def gold_rate_command(interaction: discord.Interaction):
    async with economy_lock:
        rate = update_gold_rate()
        save_economy()

    await interaction.response.send_message(
        f"Текущий курс: **1 {get_gold_emoji()} = {format_money(rate)}**."
    )


@bot.tree.command(name="buy-gold", description="Купить золото за деньги")
@app_commands.describe(amount="Сколько золота купить")
async def buy_gold_command(interaction: discord.Interaction, amount: float):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Введите количество золота больше нуля.", ephemeral=True
        )
        return

    async with economy_lock:
        rate = update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)
        cost = amount * rate

        if not math.isfinite(cost):
            message = "Это количество золота слишком велико."
        elif account["cash"] + 0.0001 < cost:
            message = (
                f"Недостаточно денег. Вам нужно **{format_money(cost)}**, "
                f"но у вас **{format_money(account['cash'])}**."
            )
        else:
            account["cash"] -= cost
            account["gold"] += amount
            message = (
                f"Вы купили **{format_gold(amount)}** за **{format_money(cost)}**.\n"
                f"Деньги осталось: **{format_money(account['cash'])}**."
            )

        save_economy()

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="sell-gold", description="Продать золото за деньги")
@app_commands.describe(amount="Сколько золота продать")
async def sell_gold_command(interaction: discord.Interaction, amount: float):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Введите количество золота больше нуля.", ephemeral=True
        )
        return

    async with economy_lock:
        rate = update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)

        if account["gold"] + 0.0001 < amount:
            message = (
                f"Недостаточно золота. Вы хотите продать **{format_gold(amount)}**, "
                f"но у вас **{format_gold(account['gold'])}**."
            )
        else:
            income = amount * rate
            account["gold"] = max(0.0, account["gold"] - amount)
            account["cash"] += income
            message = (
                f"Вы продали **{format_gold(amount)}** за **{format_money(income)}**.\n"
                f"Деньги сейчас: **{format_money(account['cash'])}**."
            )

        save_economy()

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="deposit", description="Положить деньги на вклад")
@app_commands.describe(amount="Сколько положить на вклад")
async def deposit_command(interaction: discord.Interaction, amount: float):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Введите сумму больше нуля.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        interest = accrue_deposit_interest(account)

        if account["cash"] + 0.0001 < amount:
            message = (
                f"Недостаточно денег. Вы хотите положить **{format_money(amount)}**, "
                f"но у вас **{format_money(account['cash'])}**."
            )
        else:
            account["cash"] -= amount
            account["deposit"] += amount
            message = (
                f"Вы положили **{format_money(amount)}**.\n"
                f"Вклад сейчас: **{format_money(account['deposit'])}**."
            )
            if interest > 0:
                message += f"\nПроцент добавлен: **+{format_money(interest)}**."

        save_economy()

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="withdraw", description="Снять деньги с вклада")
@app_commands.describe(amount="Сколько снять. Используйте 0 или пусто, чтобы снять всё")
async def withdraw_deposit_command(
    interaction: discord.Interaction, amount: float = 0.0
):
    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        interest = accrue_deposit_interest(account)
        deposit = account["deposit"]

        if deposit <= 0:
            message = "Ваш вклад пуст."
        else:
            if amount == 0:
                amount = deposit

            if not is_valid_amount(amount):
                message = "Введите сумму больше нуля или 0, чтобы снять всё."
            elif deposit + 0.0001 < amount:
                message = (
                    f"Недостаточно средств на вкладе. Вы хотите снять "
                    f"**{format_money(amount)}**, но на вкладе **{format_money(deposit)}**."
                )
            else:
                account["deposit"] = max(0.0, deposit - amount)
                account["cash"] += amount
                message = (
                    f"Вы сняли **{format_money(amount)}**.\n"
                    f"Деньги на руках: **{format_money(account['cash'])}**."
                )
                if interest > 0:
                    message += f"\nПроцент добавлен: **+{format_money(interest)}**."

        save_economy()

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="check", description="Админ: показать баланс участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Member whose balance you want to view")
async def admin_balance_command(interaction: discord.Interaction, member: discord.Member):
    async with economy_lock:
        rate = update_gold_rate()
        account = get_account(member.id)
        interest = accrue_deposit_interest(account)
        save_economy()
        message = (
            f"Баланс для {member.mention}\n"
            f"{format_account(account)}\n"
            f"Курс: **1 {get_gold_emoji()} = {format_money(rate)}**"
        )
        if interest > 0:
            message += f"\nВклад вырос: **+{format_money(interest)}**"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="give-money", description="Админ: выдать деньги участнику")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, который получает деньги", amount="Сумма денег")
async def admin_give_cash_command(
    interaction: discord.Interaction, member: discord.Member, amount: float
):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Enter an amount greater than zero.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(member.id)
        accrue_deposit_interest(account)
        account["cash"] += amount
        save_economy()
        message = f"{member.mention} получил(а) **{format_money(amount)}**.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="remove-money", description="Админ: отнять деньги у участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, у которого забирают деньги", amount="Сумма денег")
async def admin_remove_cash_command(
    interaction: discord.Interaction, member: discord.Member, amount: float
):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Enter an amount greater than zero.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(member.id)
        accrue_deposit_interest(account)
        taken = min(account["cash"], amount)
        account["cash"] -= taken
        save_economy()
        message = f"Снято **{format_money(taken)}** с {member.mention}.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="set-money", description="Админ: установить баланс денег участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, чей баланс меняется", amount="Новый баланс денег")
async def admin_set_cash_command(
    interaction: discord.Interaction, member: discord.Member, amount: float
):
    if not math.isfinite(amount) or amount < 0:
        await interaction.response.send_message(
            "Введите сумму от нуля и выше.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(member.id)
        accrue_deposit_interest(account)
        set_non_negative(account, "cash", amount)
        save_economy()
        message = f"Баланс денег установлен для {member.mention}.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="give-gold", description="Админ: выдать золото участнику")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, который получает золото", amount="Сумма золота")
async def admin_give_gold_command(
    interaction: discord.Interaction, member: discord.Member, amount: float
):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Enter an amount greater than zero.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(member.id)
        accrue_deposit_interest(account)
        account["gold"] += amount
        save_economy()
        message = f"{member.mention} получил(а) **{format_gold(amount)}**.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="remove-gold", description="Админ: отнять золото у участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, у которого забирают золото", amount="Сумма золота")
async def admin_remove_gold_command(
    interaction: discord.Interaction, member: discord.Member, amount: float
):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Enter an amount greater than zero.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(member.id)
        accrue_deposit_interest(account)
        taken = min(account["gold"], amount)
        account["gold"] -= taken
        save_economy()
        message = f"Снято **{format_gold(taken)}** с {member.mention}.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="set-gold", description="Админ: установить баланс золота участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, чей баланс золота меняется", amount="Новый баланс золота")
async def admin_set_gold_command(
    interaction: discord.Interaction, member: discord.Member, amount: float
):
    if not math.isfinite(amount) or amount < 0:
        await interaction.response.send_message(
            "Введите сумму от нуля и выше.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(member.id)
        accrue_deposit_interest(account)
        set_non_negative(account, "gold", amount)
        save_economy()
        message = f"Баланс золота установлен для {member.mention}.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="give-map", description="Админ: выдать карты сокровищ участнику")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, который получает карты", amount="Количество карт")
async def admin_give_map_command(
    interaction: discord.Interaction, member: discord.Member, amount: int = 1
):
    if amount <= 0:
        await interaction.response.send_message(
            "Введите количество карт больше нуля.", ephemeral=True
        )
        return

    if amount > 100:
        await interaction.response.send_message(
            "За один раз можно выдать не больше 100 карт.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(member.id)
        accrue_deposit_interest(account)
        account["treasure_maps"] += amount
        save_economy()
        message = (
            f"{member.mention} получил(а) **{format_treasure_maps(amount)}**.\n"
            f"{format_account(account)}"
        )

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="set-deposit", description="Админ: установить вклад участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, чей вклад меняется", amount="Новая сумма вклада")
async def admin_set_deposit_command(
    interaction: discord.Interaction, member: discord.Member, amount: float
):
    if not math.isfinite(amount) or amount < 0:
        await interaction.response.send_message(
            "Введите сумму от нуля и выше.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(member.id)
        set_non_negative(account, "deposit", amount)
        account["deposit_updated_at"] = now_local().isoformat(timespec="seconds")
        save_economy()
        message = f"Вклад установлен для {member.mention}.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="set-rate", description="Админ: установить курс золота")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(rate="Новый курс: сколько денег стоит 1 золото")
async def admin_set_gold_rate_command(interaction: discord.Interaction, rate: float):
    if not math.isfinite(rate) or rate < MIN_GOLD_RATE:
        await interaction.response.send_message(
            f"Курс должен быть не меньше **{format_money(MIN_GOLD_RATE)}**.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        economy_data["gold_rate"] = round(rate, 2)
        economy_data["gold_rate_date"] = today_iso()
        save_economy()

    await interaction.response.send_message(
        f"Курс установлен: **1 {get_gold_emoji()} = {format_money(round(rate, 2))}**.",
        ephemeral=True,
    )


@bot.tree.command(name="treasure-channel", description="Админ: задать канал объявлений карт")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(channel="Канал, куда отправлять ежедневную выдачу карт")
async def admin_set_treasure_channel_command(
    interaction: discord.Interaction, channel: discord.TextChannel
):
    async with economy_lock:
        economy_data["treasure_channel_id"] = channel.id
        save_economy()

    await interaction.response.send_message(
        f"Канал объявлений карт сокровищ установлен: {channel.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="treasure-event", description="Админ: выдать всем карты и объявить ивент")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(amount="Сколько карт выдать каждому игроку")
async def admin_treasure_event_command(
    interaction: discord.Interaction, amount: int = TREASURE_MAPS_PER_DROP
):
    if amount <= 0:
        await interaction.response.send_message(
            "Введите количество карт больше нуля.", ephemeral=True
        )
        return

    if amount > 100:
        await interaction.response.send_message(
            "За один ивент можно выдать не больше 100 карт каждому игроку.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        granted_count, channel, _ = await run_treasure_map_event(
            amount=amount, guild=interaction.guild
        )
    except discord.HTTPException as e:
        await interaction.followup.send(
            f"Карты выданы, но объявление отправить не удалось: {e}",
            ephemeral=True,
        )
        return

    if channel is None:
        await interaction.followup.send(
            f"Ивент запущен: **{format_integer(granted_count)} игроков** получили "
            f"**{format_treasure_maps(amount)}**. Канал объявлений не задан или недоступен.",
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            f"Ивент запущен: **{format_integer(granted_count)} игроков** получили "
            f"**{format_treasure_maps(amount)}**. Объявление отправлено в {channel.mention}.",
            ephemeral=True,
        )


async def moonshine_ingredient_autocomplete(
    interaction: discord.Interaction, current: str
):
    normalized = moonshine_text_key(current)
    matches = [
        ingredient
        for ingredient in MOONSHINE_INGREDIENTS
        if normalized in moonshine_text_key(ingredient)
    ]
    return [
        app_commands.Choice(name=ingredient, value=ingredient)
        for ingredient in matches[:25]
    ]


@bot.tree.command(name="set-icon-roles", description="Админ: задать эмодзи для роли в /roles")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    role="Название роли, например Натуралист или Торговец",
    emoji="Эмодзи, символ или серверное эмодзи",
)
async def admin_set_role_icon_command(
    interaction: discord.Interaction, role: str, emoji: str
):
    emoji = emoji.strip()
    if not emoji or len(emoji) > 80:
        await interaction.response.send_message(
            "Эмодзи не должно быть пустым и не может превышать 80 символов.",
            ephemeral=True,
        )
        return

    discord_role, role_definition = resolve_configurable_role(interaction.guild, role)
    if discord_role is None:
        await interaction.response.send_message(
            f"Не нашёл роль **{role.strip()}** на сервере. Укажите название роли текстом.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        economy_data["role_icons"][str(discord_role.id)] = emoji
        save_economy()

    message = f"Иконка для роли **{discord_role.name}** установлена: **{emoji}**."
    if role_definition is None:
        message += "\nЭта роль не входит в список `/roles`, поэтому в витрине она не появится."

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="set-discounts-roles", description="Админ: скидка на роль на неделю")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    role="Название роли, например Натуралист или Торговец",
    price="Новая цена роли в золоте на 7 дней",
)
async def admin_set_role_discount_command(
    interaction: discord.Interaction, role: str, price: float
):
    if not math.isfinite(price) or price < 0:
        await interaction.response.send_message(
            "Цена должна быть числом от нуля и выше.", ephemeral=True
        )
        return

    discord_role, role_definition = resolve_configurable_role(interaction.guild, role)
    if discord_role is None:
        await interaction.response.send_message(
            f"Не нашёл роль **{role.strip()}** на сервере. Укажите название роли текстом.",
            ephemeral=True,
        )
        return

    expires_at = now_local() + timedelta(days=ROLE_DISCOUNT_DAYS)

    async with economy_lock:
        economy_data["role_discounts"][str(discord_role.id)] = {
            "price": round(float(price), 4),
            "expires_at": expires_at.isoformat(timespec="seconds"),
        }
        save_economy()

    message = (
        f"Скидка для роли **{discord_role.name}** установлена на неделю:\n"
        f"~~{format_role_price(ROLE_BASE_PRICE)}~~ **{format_role_price(price)}**\n"
        f"Действует до **{expires_at.strftime('%d.%m.%Y')}**."
    )
    if role_definition is None:
        message += "\nЭта роль не входит в список `/roles`, поэтому скидка в витрине не появится."

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="clear-discounts-roles", description="Админ: убрать скидку с роли")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(role="Название роли, например Натуралист или Торговец")
async def admin_clear_role_discount_command(
    interaction: discord.Interaction, role: str
):
    discord_role, _ = resolve_configurable_role(interaction.guild, role)
    if discord_role is None:
        await interaction.response.send_message(
            f"Не нашёл роль **{role.strip()}** на сервере. Укажите название роли текстом.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        removed = economy_data["role_discounts"].pop(str(discord_role.id), None) is not None
        save_economy()

    if removed:
        message = f"Скидка для роли **{discord_role.name}** снята."
    else:
        message = f"Для роли **{discord_role.name}** скидка не была установлена."

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="fill-dealer", description="Админ: изменить заполнение повозки")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    percent="На сколько процентов изменить повозку. Отрицательное число вычитает.",
    member="Участник, чья повозка меняется. Если не указан, меняется ваша.",
)
async def admin_fill_dealer_command(
    interaction: discord.Interaction, percent: float, member: discord.Member = None
):
    if not math.isfinite(percent):
        await interaction.response.send_message(
            "Процент должен быть обычным числом.", ephemeral=True
        )
        return

    target = member or interaction.user
    if not isinstance(target, discord.Member):
        await interaction.response.send_message(
            "Укажите участника сервера.", ephemeral=True
        )
        return

    async with economy_lock:
        account = get_account(target.id)
        old_fill = account["dealer_wagon"]
        account["dealer_wagon"] = max(0.0, min(100.0, old_fill + percent))
        new_fill = account["dealer_wagon"]
        save_economy()

    delta = new_fill - old_fill
    await interaction.response.send_message(
        f"Повозка {target.mention}: **{format_percent(old_fill)}** -> "
        f"**{format_percent(new_fill)}** "
        f"({format_percent(delta)}).",
        ephemeral=True,
    )


@bot.tree.command(
    name="give-moonshine-ingredient",
    description="Админ: выдать ингредиент самогонщика",
)
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    member="Участник, который получает ингредиент",
    ingredient="Название ингредиента",
    amount="Количество",
)
@app_commands.autocomplete(ingredient=moonshine_ingredient_autocomplete)
async def admin_give_moonshine_ingredient_command(
    interaction: discord.Interaction,
    member: discord.Member,
    ingredient: str,
    amount: int = 1,
):
    if amount <= 0:
        await interaction.response.send_message(
            "Введите количество больше нуля.", ephemeral=True
        )
        return

    if amount > 100:
        await interaction.response.send_message(
            "За один раз можно выдать не больше 100 ингредиентов.", ephemeral=True
        )
        return

    ingredient_name = resolve_moonshine_ingredient(ingredient)
    if ingredient_name is None:
        await interaction.response.send_message(
            "Не нашёл такой ингредиент. Используйте подсказки команды.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        account = get_account(member.id)
        moonshine = get_moonshine_account(account)
        moonshine["ingredients"][ingredient_name] = (
            moonshine["ingredients"].get(ingredient_name, 0) + amount
        )
        save_economy()

    await interaction.response.send_message(
        f"{member.mention} получил(а) **{ingredient_name} x{amount}**.",
        ephemeral=True,
    )


@bot.tree.command(
    name="remove-moonshine-ingredient",
    description="Админ: забрать ингредиент самогонщика",
)
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    member="Участник, у которого забирают ингредиент",
    ingredient="Название ингредиента",
    amount="Количество",
)
@app_commands.autocomplete(ingredient=moonshine_ingredient_autocomplete)
async def admin_remove_moonshine_ingredient_command(
    interaction: discord.Interaction,
    member: discord.Member,
    ingredient: str,
    amount: int = 1,
):
    if amount <= 0:
        await interaction.response.send_message(
            "Введите количество больше нуля.", ephemeral=True
        )
        return

    ingredient_name = resolve_moonshine_ingredient(ingredient)
    if ingredient_name is None:
        await interaction.response.send_message(
            "Не нашёл такой ингредиент. Используйте подсказки команды.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        account = get_account(member.id)
        moonshine = get_moonshine_account(account)
        current_amount = moonshine["ingredients"].get(ingredient_name, 0)
        taken = min(current_amount, amount)
        if taken > 0:
            moonshine["ingredients"][ingredient_name] = current_amount - taken
            if moonshine["ingredients"][ingredient_name] <= 0:
                moonshine["ingredients"].pop(ingredient_name, None)
        save_economy()

    await interaction.response.send_message(
        f"У {member.mention} забрано **{ingredient_name} x{taken}**.",
        ephemeral=True,
    )


@bot.tree.command(name="set-moonshine-upgrade", description="Админ: установить уровень аппарата")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    member="Участник, чей аппарат меняется",
    level="Уровень аппарата самогонщика",
)
@app_commands.choices(
    level=[
        app_commands.Choice(name="1 уровень", value=1),
        app_commands.Choice(name="2 уровень", value=2),
        app_commands.Choice(name="3 уровень", value=3),
    ]
)
async def admin_set_moonshine_upgrade_command(
    interaction: discord.Interaction,
    member: discord.Member,
    level: app_commands.Choice[int],
):
    async with economy_lock:
        account = get_account(member.id)
        moonshine = get_moonshine_account(account)
        set_moonshine_level(moonshine, level.value)
        save_economy()

    await interaction.response.send_message(
        f"Уровень аппарата {member.mention} установлен: **{level.value}**.",
        ephemeral=True,
    )


@bot.tree.command(name="set-moonshine-skill", description="Админ: включить или выключить навык")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    member="Участник, чей навык меняется",
    enabled="Включить сокращённое время производства",
)
async def admin_set_moonshine_skill_command(
    interaction: discord.Interaction, member: discord.Member, enabled: bool
):
    async with economy_lock:
        account = get_account(member.id)
        moonshine = get_moonshine_account(account)
        moonshine["skill"] = bool(enabled)
        save_economy()

    state = "включён" if enabled else "выключен"
    await interaction.response.send_message(
        f"Навык самогонщика для {member.mention}: **{state}**.",
        ephemeral=True,
    )


@bot.tree.command(name="finish-moonshine", description="Админ: мгновенно завершить партию")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, чья партия завершается")
async def admin_finish_moonshine_command(
    interaction: discord.Interaction, member: discord.Member
):
    async with economy_lock:
        account = get_account(member.id)
        moonshine = get_moonshine_account(account)
        batch = moonshine.get("batch")
        if not batch:
            save_economy()
            await interaction.response.send_message(
                f"У {member.mention} нет активной партии самогона.", ephemeral=True
            )
            return

        batch["ready_at"] = now_local().isoformat(timespec="seconds")
        save_economy()

    await interaction.response.send_message(
        f"Партия самогона {member.mention} теперь готова к доставке.",
        ephemeral=True,
    )


@bot.tree.command(name="reset-moonshine", description="Админ: сбросить состояние самогонщика")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, чьё состояние сбрасывается")
async def admin_reset_moonshine_command(
    interaction: discord.Interaction, member: discord.Member
):
    async with economy_lock:
        account = get_account(member.id)
        account["moonshine"] = default_moonshine_data()
        save_economy()

    await interaction.response.send_message(
        f"Состояние самогонщика сброшено для {member.mention}.",
        ephemeral=True,
    )


@bot.tree.command(name="set-emoji", description="Админ: задать эмодзи валют и инвестиций")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    currency="Валюта для настройки",
    emoji="Эмодзи, символ или серверное эмодзи, например <:gold:123456789>",
)
@app_commands.choices(
    currency=[
        app_commands.Choice(name="Деньги", value="cash"),
        app_commands.Choice(name="Золото", value="gold"),
        app_commands.Choice(name="Карта сокровищ", value="map"),
        app_commands.Choice(name="Инвестиции", value="investment"),
        app_commands.Choice(name="Статистика", value="stats"),
        app_commands.Choice(name="Самогон: 1 звезда", value="moonshine_star_1"),
        app_commands.Choice(name="Самогон: 2 звезды", value="moonshine_star_2"),
        app_commands.Choice(name="Самогон: 3 звезды", value="moonshine_star_3"),
        app_commands.Choice(name="Особый самогон", value="moonshine_special"),
        app_commands.Choice(name="Кнопка: бражка", value="moonshine_button_mash"),
        app_commands.Choice(name="Кнопка: особые ингредиенты", value="moonshine_button_special"),
        app_commands.Choice(name="Кнопка: улучшения", value="moonshine_button_upgrades"),
        app_commands.Choice(name="Кнопка: доставка", value="moonshine_button_delivery"),
    ]
)
async def admin_set_emoji_command(
    interaction: discord.Interaction, currency: app_commands.Choice[str], emoji: str
):
    emoji = emoji.strip()
    if not emoji or len(emoji) > 80:
        await interaction.response.send_message(
            "Эмодзи не должно быть пустым и не может превышать 80 символов.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        if currency.value == "cash":
            economy_data["cash_emoji"] = emoji
            message = f"Эмодзи для денег установлено: **{format_money(3)}**"
        elif currency.value == "gold":
            economy_data["gold_emoji"] = emoji
            message = f"Эмодзи для золота установлено: **{format_gold(3)}**"
        elif currency.value == "map":
            economy_data["map_emoji"] = emoji
            message = f"Эмодзи для карты установлено: **{format_treasure_maps(3)}**"
        elif currency.value == "investment":
            economy_data["investment_emoji"] = emoji
            message = (
                f"Эмодзи для инвестиций установлено: "
                f"**{get_investment_emoji()} Вклад: {format_money_plain(3)}**"
            )
        elif currency.value == "stats":
            economy_data["stats_emoji"] = emoji
            message = f"Эмодзи для статистики установлено: **{get_stats_emoji()}Статистика**"
        elif currency.value.startswith("moonshine_star_"):
            level = currency.value.rsplit("_", 1)[-1]
            economy_data["moonshine_star_emojis"][level] = emoji
            message = f"Эмодзи для самогона {level} уровня установлено: **{emoji}**"
        elif currency.value == "moonshine_special":
            economy_data["moonshine_special_emoji"] = emoji
            message = f"Эмодзи для особого самогона установлено: **{emoji}**"
        else:
            button_key = currency.value.replace("moonshine_button_", "", 1)
            economy_data["moonshine_button_emojis"][button_key] = emoji
            message = f"Эмодзи кнопки самогонщика установлено: **{emoji}**"
        save_economy()

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="reset-work", description="Админ: сбросить кулдаун /work у участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, у которого нужно сбросить кулдаун /work")
async def admin_reset_work_command(interaction: discord.Interaction, member: discord.Member):
    async with economy_lock:
        account = get_account(member.id)
        account["last_work_at"] = None
        save_economy()

    await interaction.response.send_message(
        f"Кулдаун работы сброшен для {member.mention}.", ephemeral=True
    )


@admin_balance_command.error
@admin_give_cash_command.error
@admin_remove_cash_command.error
@admin_set_cash_command.error
@admin_give_gold_command.error
@admin_remove_gold_command.error
@admin_set_gold_command.error
@admin_give_map_command.error
@admin_set_deposit_command.error
@admin_set_gold_rate_command.error
@admin_set_treasure_channel_command.error
@admin_treasure_event_command.error
@admin_set_role_icon_command.error
@admin_set_role_discount_command.error
@admin_clear_role_discount_command.error
@admin_fill_dealer_command.error
@admin_give_moonshine_ingredient_command.error
@admin_remove_moonshine_ingredient_command.error
@admin_set_moonshine_upgrade_command.error
@admin_set_moonshine_skill_command.error
@admin_finish_moonshine_command.error
@admin_reset_moonshine_command.error
@admin_set_emoji_command.error
@admin_reset_work_command.error
async def admin_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        message = "У вас недостаточно прав. Требуется роль Администратор."
    else:
        message = f"Админ-команда не удалась: {error}"

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.event
async def on_guild_join(guild):
    try:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Команды синхронизированы для нового сервера '{guild.name}': {len(synced)}")
    except Exception as e:
        print(f"Синхронизация команд не удалась для нового сервера '{guild.name}': {e}")


# Create a discussion thread for new posts in configured channels.
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    if message.channel.id in active_channels:
        if not isinstance(message.channel, discord.Thread):
            try:
                if message.thread:
                    return

                thread_name = message.content.strip()
                if not thread_name.strip():
                    if message.attachments:
                        thread_name = f"File discussion: {message.attachments[0].filename}"
                    else:
                        thread_name = f"Discussion from {message.author.display_name}"

                if len(thread_name) > 90:
                    thread_name = f"{thread_name[:87]}..."

                thread = await message.create_thread(
                    name=thread_name, auto_archive_duration=1440
                )
                await thread.send("Share your thoughts.")
            except discord.Forbidden:
                print(f"Нет прав для создания треда в канале {message.channel.id}")
            except discord.HTTPException as e:
                print(f"Создание треда не удалось: {e}")


def main():
    load_env_file()
    token = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN") or BOT_TOKEN.strip()
    if not token:
        raise RuntimeError(
            "Token not found. Set DISCORD_TOKEN in .env or in the environment."
        )

    bot.run(token)


if __name__ == "__main__":
    main()
