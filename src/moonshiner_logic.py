import time
import math
import random
import json
import os
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from emoji_config import *


MOONSHINE_IMAGE_FILE = "assets/images/moonshine.png"


MOONSHINE_IMAGE_ATTACHMENT_NAME = "moonshine.png"


MOONSHINER_ROLE_KEY = "moonshiner"


MOONSHINE_CONDENSER_PRICE = 825.0


MOONSHINE_DISTILLER_PRICE = 875.0


MOONSHINE_BATCH_COST = 30.0


def _economy_data():
    """Return injected bot state without importing bot.py recursively."""
    data = globals().get("economy_data")
    return data if data is not None else {}


MOONSHINE_STRENGTHS = {
    "weak":   {"name": "Слабый",   "duration_skill": 24 * 60, "duration_no_skill": 30 * 60},
    "medium": {"name": "Средний",  "duration_skill": 36 * 60, "duration_no_skill": 45 * 60},
    "strong": {"name": "Крепкий",  "duration_skill": 48 * 60, "duration_no_skill": 60 * 60},
}

# Обычные бражки: 1⭐=110$, 2⭐=147$, 3⭐=165$
MOONSHINE_MASH_RECIPES = [
    {"key": "weak_1",   "number": 1, "strength_key": "weak",   "stars": 1, "required_level": 1, "payout": 110.0},
    {"key": "medium_5", "number": 5, "strength_key": "medium", "stars": 2, "required_level": 2, "payout": 147.0},
    {"key": "strong_9", "number": 9, "strength_key": "strong", "stars": 3, "required_level": 3, "payout": 165.0},
]

# Особые рецепты — на ~50% дороже обычной бражки того же уровня
# 1⭐=165$, 2⭐=220$, 3⭐=248$
MOONSHINE_SPECIAL_RECIPES = [
    {"key": "mahogany_sunrise", "name": "Рассвет среди магоний",  "stars": 3,
     "ingredients": {"Консервированная клубника": 1, "Черника овальнолистная": 1, "Магония": 1}, "payout": 248.0},
    {"key": "berry_apple",      "name": "Ягодно-яблочный",        "stars": 2,
     "ingredients": {"Яблоко": 1, "Ежевика": 1, "Цветок ванили": 1},                             "payout": 220.0},
    {"key": "berry_cobbler",    "name": "Ягодный пирог",          "stars": 2,
     "ingredients": {"Консервированные персики": 1, "Малина": 1, "Персик": 1},                   "payout": 220.0},
    {"key": "berry_mint",       "name": "Ягодно-мятный",          "stars": 1,
     "ingredients": {"Консервированная клубника": 1, "Ежевика": 1, "Мята": 1},                   "payout": 165.0},
    {"key": "evergreen",        "name": "Хвойный",                "stars": 2,
     "ingredients": {"Черника овальнолистная": 1, "Гаультерия": 1, "Женьшень": 1},               "payout": 220.0},
    {"key": "poison_poppy",     "name": "Ядовитый мак",           "stars": 3,
     "ingredients": {"Пустынный мак": 1, "Олеандр": 1, "Абсент": 1},                             "payout": 248.0},
    {"key": "spiced_island",    "name": "Пряный остров",          "stars": 3,
     "ingredients": {"Консервированные абрикосы": 1, "Смородина": 1, "Карибский ром": 1},        "payout": 248.0},
    {"key": "tropical_punch",   "name": "Тропический пунш",       "stars": 2,
     "ingredients": {"Консервированные ананасы": 1, "Груша": 1, "Цветок ванили": 1},             "payout": 220.0},
    {"key": "wild_cider",       "name": "Дикий сидр",             "stars": 1,
     "ingredients": {"Яблоко": 1, "Женьшень": 1, "Смородина": 1},                                "payout": 165.0},
    {"key": "wild_creek",       "name": "Дикий ручей",            "stars": 3,
     "ingredients": {"Мята": 1, "Цветок ванили": 1, "Слива поручейная": 1},                      "payout": 248.0},
]


MOONSHINE_INGREDIENTS = sorted(
    {
        ingredient
        for recipe in MOONSHINE_SPECIAL_RECIPES
        for ingredient in recipe["ingredients"]
    }
)


def get_moonshine_star_emoji(level):
    emojis = _economy_data().get("moonshine_star_emojis", {})
    emoji = emojis.get(str(level))
    if not emoji:
        return str(DEFAULT_MOONSHINE_STAR_EMOJIS[str(level)])
    return str(emoji)


def get_moonshine_special_emoji():
    emoji = _economy_data().get("moonshine_special_emoji")
    if not emoji:
        return str(DEFAULT_MOONSHINE_SPECIAL_EMOJI)
    return str(emoji)


def get_moonshine_condenser_emoji():
    emoji = _economy_data().get("moonshine_condenser_emoji")
    if not emoji:
        return str(DEFAULT_MOONSHINE_CONDENSER_EMOJI)
    return str(emoji)


def get_moonshine_distiller_emoji():
    emoji = _economy_data().get("moonshine_distiller_emoji")
    if not emoji:
        return str(DEFAULT_MOONSHINE_DISTILLER_EMOJI)
    return str(emoji)


def get_moonshine_button_emoji(button_key):
    emojis = _economy_data().get("moonshine_button_emojis", {})
    emoji = emojis.get(button_key)
    if not emoji:
        return str(DEFAULT_MOONSHINE_BUTTON_EMOJIS[button_key])
    return str(emoji)


def get_moonshine_ui_emoji(key, default_value):
    emoji = _economy_data().get(key)
    if not emoji:
        return default_value
    return str(emoji)


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
    else:
        batch = moonshine["batch"]
        try:
            stars = max(1, min(3, int(batch.get("stars", 1))))
            duration = max(1, int(float(batch.get("duration_seconds", 1))))
            payout = float(batch.get("payout", 0.0))
            cost = float(batch.get("cost", MOONSHINE_BATCH_COST))
            if not math.isfinite(payout) or not math.isfinite(cost):
                raise ValueError("non-finite moonshine amount")
        except (TypeError, ValueError, OverflowError):
            # A partially written legacy batch must not break every future
            # interaction. Reset only the corrupted batch, keeping upgrades
            # and ingredients intact.
            moonshine["batch"] = None
        else:
            now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
            batch["type"] = "special" if batch.get("type") == "special" else "mash"
            batch["name"] = str(batch.get("name") or "Самогон")[:100]
            batch["stars"] = stars
            batch["duration_seconds"] = duration
            batch["payout"] = max(0.0, payout)
            batch["cost"] = max(0.0, cost)
            for timestamp_key in ("started_at", "ready_at"):
                value = batch.get(timestamp_key)
                try:
                    datetime.fromisoformat(value)
                except (TypeError, ValueError):
                    batch[timestamp_key] = now_iso

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


def add_moonshine_ingredient(account, ingredient, amount=1):
    """Add a validated recipe ingredient to the moonshiner's shared storage."""
    ingredient_name = resolve_moonshine_ingredient(ingredient)
    if ingredient_name is None:
        raise ValueError("unknown moonshine ingredient")
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        raise ValueError("ingredient amount must be an integer") from None
    if amount <= 0:
        raise ValueError("ingredient amount must be positive")
    moonshine = get_moonshine_account(account)
    ingredients = moonshine["ingredients"]
    ingredients[ingredient_name] = ingredients.get(ingredient_name, 0) + amount
    return ingredients[ingredient_name]


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

    try:
        ready_at = parse_local_datetime(batch.get("ready_at"))
    except (TypeError, ValueError, OverflowError):
        return 20
    seconds_left = (ready_at - now_local()).total_seconds()
    if seconds_left <= 0:
        return 20

    duration = max(1, float(batch.get("duration_seconds", 1)))
    elapsed = max(0.0, duration - seconds_left)
    return max(0, min(19, int((elapsed / duration) * 20)))


def format_moonshine_bottles(moonshine):
    bottles = get_moonshine_bottles(moonshine)
    bottle_emoji = get_moonshine_ui_emoji("moonshine_ui_bottles", DEFAULT_MOONSHINE_BOTTLES_EMOJI)
    percent = (bottles / 20.0) * 100
    bars = int((bottles / 20.0) * 10)
    
    # Иконки для полосы прогресса
    filled_block = "▓"
    empty_block = "░"
    
    progress = filled_block * bars + empty_block * (10 - bars)
    return f"{progress} {percent:.1f}% {bottles}/20 бутылок"


def get_ingredient_emoji(ingredient_name):
    emojis = _economy_data().get("moonshine_ingredient_emojis", {})
    emoji = emojis.get(ingredient_name)
    if not emoji:
        return str(DEFAULT_MOONSHINE_INGREDIENT_EMOJIS.get(ingredient_name, "🌿"))
    return str(emoji)

def format_moonshine_ingredients(ingredients):
    if not ingredients:
        return "пусто"

    lines = [
        f"{get_ingredient_emoji(ingredient)} {ingredient} x{amount}"
        for ingredient, amount in sorted(ingredients.items())
        if amount > 0
    ]
    if not lines:
        return "пусто"

    text = ", ".join(lines[:12])
    if len(lines) > 12:
        text += f" и ещё {len(lines) - 12}"
    return text


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
        "cost": MOONSHINE_BATCH_COST,
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


def get_moonshine_image_file():
    if not os.path.exists(MOONSHINE_IMAGE_FILE):
        return None
    return discord.File(MOONSHINE_IMAGE_FILE, filename=MOONSHINE_IMAGE_ATTACHMENT_NAME)


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
    stor_full = get_moonshine_ui_emoji("moonshine_ui_stor_full", DEFAULT_MOONSHINE_STOR_FULL_EMOJI)
    stor_empty = get_moonshine_ui_emoji("moonshine_ui_stor_empty", DEFAULT_MOONSHINE_STOR_EMPTY_EMOJI)
    storage_icon = stor_full if storage != "пусто" else stor_empty
    
    b_emoji = get_moonshine_ui_emoji("moonshine_ui_bottles", DEFAULT_MOONSHINE_BOTTLES_EMOJI)
    w_emoji = get_moonshine_ui_emoji("moonshine_ui_wagon", DEFAULT_MOONSHINE_WAGON_EMOJI)
    br_emoji = get_moonshine_ui_emoji("moonshine_ui_brewing", DEFAULT_MOONSHINE_BREWING_EMOJI)
    k_emoji = get_moonshine_ui_emoji("moonshine_ui_kettle", DEFAULT_MOONSHINE_KETTLE_EMOJI)

    if batch:
        ready_at = parse_local_datetime(batch.get("ready_at"))
        seconds_left = (ready_at - now_local()).total_seconds()
        if seconds_left <= 0:
            progress_line = (
                f"├─ {b_emoji} Бутылки: {format_moonshine_bottles(moonshine)}\n"
                f"└─ {w_emoji} Повозка: готова к отправке за {format_money(batch.get('payout', 0))}"
            )
        else:
            progress_line = (
                f"├─ {b_emoji} Бутылки: {format_moonshine_bottles(moonshine)}\n"
                f"└─ {br_emoji} Варка: осталось {format_duration(seconds_left)}"
            )
    else:
        progress_line = (
            f"├─ {b_emoji} Бутылки: {format_moonshine_bottles(moonshine)}\n"
            f"└─ {k_emoji} Котёл свободен"
        )

    prod_emoji = get_moonshine_ui_emoji("moonshine_ui_prod", DEFAULT_MOONSHINE_PROD_EMOJI)
    lvl_emoji = get_moonshine_ui_emoji("moonshine_ui_lvl", DEFAULT_MOONSHINE_LVL_EMOJI)
    acc_emoji = get_moonshine_ui_emoji("moonshine_ui_access", DEFAULT_MOONSHINE_ACCESS_EMOJI)
    eq_emoji = get_moonshine_ui_emoji("moonshine_ui_equip", DEFAULT_MOONSHINE_EQUIP_EMOJI)
    sk_emoji = get_moonshine_ui_emoji("moonshine_ui_skill", DEFAULT_MOONSHINE_SKILL_EMOJI)
    fin_emoji = get_moonshine_ui_emoji("moonshine_ui_finance", DEFAULT_MOONSHINE_FINANCE_EMOJI)

    embed = discord.Embed(
        title=f"{icon} Предприятие самогонщика",
        description=(
            f"**Марсель:** {random.choice(MARCEL_GREETINGS)}\n\n"
            f"{prod_emoji} Производство\n"
            f"├─ {lvl_emoji} Уровень аппарата: **{level}**\n"
            f"├─ {acc_emoji} Доступ: **{get_moonshine_star_emoji(level)}**\n"
            f"{progress_line}\n\n"
            f"{eq_emoji} Оборудование\n"
            f"├─ {get_moonshine_condenser_emoji()} Конденсатор: **{condenser}**\n"
            f"├─ {get_moonshine_distiller_emoji()} Медный дистиллятор: **{distiller}**\n"
            f"└─ {sk_emoji} Навык самогонщика: **{skill}**\n\n"
            f"{storage_icon} Склад ингредиентов\n"
            f"└─ {storage}\n\n"
            f"{fin_emoji} Финансы\n"
            f"├─ Наличные: **{format_money(account['cash'])}**\n"
            f"├─ Стоимость производства: **{format_money(MOONSHINE_BATCH_COST)}**\n"
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
        from bot import get_lock_emoji
        lock = "" if required_level <= level else f" {get_lock_emoji()}"
        lines.append(
            f"Бражка {strength['name']} —  "
            f"{get_moonshine_star_emoji(recipe['stars'])}{lock}: "
            f"{format_minutes(duration)}, запуск {format_money(MOONSHINE_BATCH_COST)}, "
            f"выручка {format_money(recipe['payout'])}"
        )

    embed = discord.Embed(
        title="Выбрать бражку",
        description="\n".join(lines),
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(MOONSHINE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{MOONSHINE_IMAGE_ATTACHMENT_NAME}")
    embed.set_footer(text="Бражка #5 открывается конденсатором, #9 — медным дистиллятором.")
    return embed


def build_moonshine_special_embed(moonshine):
    level = get_moonshine_level(moonshine)
    cost_str = format_money(MOONSHINE_BATCH_COST)
    
    # Выносим эмодзи, чтобы не вызывать функцию в цикле сотни раз
    special_emoji = get_moonshine_special_emoji()
    
    # Сортируем рецепты заранее
    sorted_recipes = sorted(
        MOONSHINE_SPECIAL_RECIPES, 
        key=lambda item: (item["stars"], item["name"])
    )
    
    lines = []
    for recipe in sorted_recipes:
        stars = recipe["stars"]
        
        # Понятные и лаконичные тернарные операторы
        from bot import get_lock_emoji
        lock = "" if stars <= level else f" {get_lock_emoji()}"
        status = "есть" if has_moonshine_ingredients(moonshine, recipe) else "не хватает"
        
        star_emoji = get_moonshine_star_emoji(stars)
        payout_str = format_money(recipe['payout'])
        
        ingredients_reqs = []
        for ing_name, amount in recipe["ingredients"].items():
            ing_emoji = get_ingredient_emoji(ing_name)
            ingredients_reqs.append(f"{ing_emoji} x{amount}")
        req_str = ", ".join(ingredients_reqs)
        
        # Разбиваем длинную строку на логические блоки для читаемости
        line = (
            f"{special_emoji} **{recipe['name']}** {star_emoji}{lock}:\n"
            f"└ Основа: бражка {stars} ур. | "
            f"Выручка: {payout_str}\n"
            f"└ Ингредиенты: {req_str} (**{status}**)"
        )
        lines.append(line)


    embed = discord.Embed(
        title="Особые ингредиенты",
        description=fit_embed_description(lines),
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(MOONSHINE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{MOONSHINE_IMAGE_ATTACHMENT_NAME}")
    embed.set_footer(text="Особый самогон открывается по уровню доступной бражки; сумма — выручка за доставку повозки.")
    return embed

