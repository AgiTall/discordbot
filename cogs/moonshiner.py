import discord
from discord.ext import commands
from discord import app_commands
import random
import time
import math

class MoonshinerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        import traceback
        print(f"Moonshiner Cog error: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Произошла ошибка: {error}", ephemeral=True)

MOONSHINE_IMAGE_FILE = "assets/images/moonshine.png"


MOONSHINE_IMAGE_ATTACHMENT_NAME = "moonshine.png"


MOONSHINER_ROLE_KEY = "moonshiner"


MOONSHINE_CONDENSER_PRICE = 825.0


MOONSHINE_DISTILLER_PRICE = 875.0


MOONSHINE_BATCH_COST = 50.0


DEFAULT_MOONSHINE_STAR_EMOJIS = {
    "1": "⭐",
    "2": "⭐⭐",
    "3": "⭐⭐⭐",
}


DEFAULT_MOONSHINE_SPECIAL_EMOJI = "🌟🌟🌟"


DEFAULT_MOONSHINE_CONDENSER_EMOJI = "🧊"


DEFAULT_MOONSHINE_DISTILLER_EMOJI = "🟠"


DEFAULT_MOONSHINE_BUTTON_EMOJIS = {
    "mash": "🥣",
    "special": "🌿",
    "upgrades": "⚙️",
    "delivery": "🛺",
    "refresh": "🔄",
}


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


def get_moonshine_star_emoji(level):
    emojis = economy_data.get("moonshine_star_emojis", {})
    emoji = emojis.get(str(level))
    if not emoji:
        return str(DEFAULT_MOONSHINE_STAR_EMOJIS[str(level)])
    return str(emoji)


def get_moonshine_special_emoji():
    emoji = economy_data.get("moonshine_special_emoji")
    if not emoji:
        return str(DEFAULT_MOONSHINE_SPECIAL_EMOJI)
    return str(emoji)


def get_moonshine_condenser_emoji():
    emoji = economy_data.get("moonshine_condenser_emoji")
    if not emoji:
        return str(DEFAULT_MOONSHINE_CONDENSER_EMOJI)
    return str(emoji)


def get_moonshine_distiller_emoji():
    emoji = economy_data.get("moonshine_distiller_emoji")
    if not emoji:
        return str(DEFAULT_MOONSHINE_DISTILLER_EMOJI)
    return str(emoji)


def get_moonshine_button_emoji(button_key):
    emojis = economy_data.get("moonshine_button_emojis", {})
    emoji = emojis.get(button_key)
    if not emoji:
        return str(DEFAULT_MOONSHINE_BUTTON_EMOJIS[button_key])
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
            f"**Марсель:** {random.choice(MARCEL_GREETINGS)}\n\n"
            "🥃 Производство\n"
            f"├─ 🏷️ Уровень аппарата: **{level}**\n"
            f"├─ ⭐ Доступ: **{get_moonshine_star_emoji(level)}**\n"
            f"{progress_line}\n\n"
            "⚙️ Оборудование\n"
            f"├─ {get_moonshine_condenser_emoji()} Конденсатор: **{condenser}**\n"
            f"├─ {get_moonshine_distiller_emoji()} Медный дистиллятор: **{distiller}**\n"
            f"└─ ⏱️ Навык самогонщика: **{skill}**\n\n"
            f"{storage_icon} Склад ингредиентов\n"
            f"└─ {storage}\n\n"
            "💵 Финансы\n"
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
        lock = "" if required_level <= level else " 🔒"
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
        lock = "" if stars <= level else " 🔒"
        status = "есть" if has_moonshine_ingredients(moonshine, recipe) else "не хватает"
        
        star_emoji = get_moonshine_star_emoji(stars)
        payout_str = format_money(recipe['payout'])
        
        # Разбиваем длинную строку на логические блоки для читаемости
        line = (
            f"{special_emoji} **{recipe['name']}** {star_emoji}{lock}:\n"
            f"└ Основа: бражка {stars} ур. | "
            f"Выручка: {payout_str}\n"
            f"└ Ингредиенты: **{status}**"
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
            await send_embed_response(
                interaction,
                "Повозка пустая",
                random.choice(MARCEL_EMPTY_WAGON),
                ephemeral=True,
            )
            return

        ready_at = parse_local_datetime(batch.get("ready_at"))
        seconds_left = (ready_at - now_local()).total_seconds()
        if seconds_left > 0:
            save_economy()
            await send_embed_response(
                interaction,
                "Самогон доходит",
                random.choice(MARCEL_NOT_READY).format(duration=format_duration(seconds_left)),
                ephemeral=True,
            )
            return

        payout = float(batch.get("payout", 0.0))
        name = batch.get("name", "Самогон")
        account["cash"] += payout
        moonshine["batch"] = None
        save_economy()

    embed = build_bot_embed(
        "Доставка самогона",
        f"{interaction.user.mention}, повозка отвезена. "
        f"**{name}** продан за **{format_money(payout)}**.",
        color=discord.Color.dark_gold(),
    )
    await send_loading_then_edit(
        interaction,
        "Повозка едет...",
        embed,
    )


class MoonshineOwnerView(discord.ui.View):
    def __init__(self, user_id, timeout=600):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
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
                        f"{format_number(recipe['payout'])} · запуск "
                        f"{format_number(MOONSHINE_BATCH_COST)}"
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
                await send_embed_response(
                    interaction,
                    "Котёл занят",
                    random.choice(MARCEL_BUSY),
                    ephemeral=True,
                )
                return

            if recipe["stars"] > get_moonshine_level(moonshine):
                save_economy()
                await send_embed_response(
                    interaction,
                    "Нужен апгрейд",
                    "Для этой бражки нужен апгрейд оборудования.",
                    ephemeral=True,
                )
                return

            if account["cash"] + 0.0001 < MOONSHINE_BATCH_COST:
                save_economy()
                await send_embed_response(
                    interaction,
                    "Не хватает денег",
                    f"Запуск партии стоит **{format_money(MOONSHINE_BATCH_COST)}**, "
                    f"у вас **{format_money(account['cash'])}**.",
                    ephemeral=True,
                )
                return

            account["cash"] -= MOONSHINE_BATCH_COST
            batch = start_moonshine_batch(moonshine, recipe, "mash")
            save_economy()

        embed = build_bot_embed(
            "Партия запущена",
            f"**Марсель:** {random.choice(MARCEL_MASH_START)} **{batch['name']}**.\n"
            f"Стоимость производства: **{format_money(MOONSHINE_BATCH_COST)}**.\n"
            f"Готовность через **{format_minutes(batch['duration_seconds'])}**. "
            f"Выручка: **{format_money(batch['payout'])}**.",
            color=discord.Color.dark_gold(),
        )
        await send_loading_then_edit(
            interaction,
            "Перегонка идёт...",
            embed,
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
                    description=(
                        f"{recipe['stars']} ур. бражки · "
                        f"выручка {format_number(recipe['payout'])} · {status}"
                    ),
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
            await send_embed_response(
                interaction,
                "Нет рецептов",
                "**Марсель:** Пока нет доступных особых рецептов.",
                ephemeral=True,
            )
            return

        recipe = get_moonshine_special_recipe(self.values[0])
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            batch = moonshine.get("batch")

            if not batch:
                save_economy()
                await send_embed_response(
                    interaction,
                    "Нет бражки",
                    "**Марсель:** Котёл пуст. Сначала поставьте бражку, босс.",
                    ephemeral=True,
                )
                return

            if batch.get("type") == "special":
                save_economy()
                await send_embed_response(
                    interaction,
                    "Уже особый",
                    "**Марсель:** В этот котёл мы уже добавили особые ингредиенты.",
                    ephemeral=True,
                )
                return

            bottles = get_moonshine_bottles(moonshine)
            if bottles >= 20:
                save_economy()
                await send_embed_response(
                    interaction,
                    "Самогон уже готов",
                    "**Марсель:** Самогон уже готов к продаже, поздно добавлять ингредиенты.",
                    ephemeral=True,
                )
                return

            if recipe["stars"] != batch.get("stars", 1):
                save_economy()
                await send_embed_response(
                    interaction,
                    "Не подходит",
                    f"**Марсель:** Для этого рецепта нужна бражка {recipe['stars']} ур., а в котле {batch.get('stars', 1)} ур.",
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
                await send_embed_response(
                    interaction,
                    "Не хватает ингредиентов",
                    "Не хватает ингредиентов: **" + ", ".join(missing) + "**.",
                    ephemeral=True,
                )
                return

            consume_moonshine_ingredients(moonshine, recipe)
            
            batch["type"] = "special"
            batch["recipe_key"] = recipe["key"]
            batch["name"] = get_moonshine_recipe_name(recipe)
            batch["payout"] = float(recipe["payout"])
            save_economy()

        embed = build_bot_embed(
            "Ингредиенты добавлены",
            f"**Марсель:** {random.choice(MARCEL_SPECIAL_SUCCESS)}\n\n"
            f"Основа: **бражка {recipe['stars']} уровня**.\n"
            f"Новая выручка: **{format_money(batch['payout'])}**.\n"
            f"Партия теперь называется: **{batch['name']}**.",
            color=discord.Color.dark_gold(),
        )
        await send_loading_then_edit(
            interaction,
            "Марсель колдует над котлом...",
            embed,
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
        self.refresh_button.emoji = get_moonshine_button_emoji("refresh")

    @discord.ui.button(label="Выбрать бражку", style=discord.ButtonStyle.primary, row=0)
    async def choose_mash_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            embed = build_moonshine_mash_embed(moonshine)
            view = MoonshineMashView(interaction.user.id, moonshine)
            save_economy()

        image = get_moonshine_image_file()
        if image:
            await interaction.response.send_message(
                embed=embed, view=view, file=image, ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Добавить особые ингредиенты", style=discord.ButtonStyle.primary, row=0)
    async def special_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            embed = build_moonshine_special_embed(moonshine)
            view = MoonshineSpecialView(interaction.user.id, moonshine)
            save_economy()

        image = get_moonshine_image_file()
        if image:
            await interaction.response.send_message(
                embed=embed, view=view, file=image, ephemeral=True
            )
        else:
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
        if os.path.exists(MOONSHINE_IMAGE_FILE):
            embed.set_image(url=f"attachment://{MOONSHINE_IMAGE_ATTACHMENT_NAME}")
        image = get_moonshine_image_file()
        if image:
            await interaction.response.send_message(
                embed=embed,
                view=MoonshineUpgradeView(interaction.user.id),
                file=image,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=embed,
                view=MoonshineUpgradeView(interaction.user.id),
                ephemeral=True,
            )

    @discord.ui.button(label="Отвезти повозку", style=discord.ButtonStyle.success, row=0)
    async def deliver_button(self, interaction, button):
        await deliver_moonshine_batch(interaction)

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            embed = build_moonshine_embed(interaction.guild, account)
            save_economy()

        await interaction.response.edit_message(
            embed=embed, view=MoonshineMainView(interaction.user.id)
        )


@bot.tree.command(name="moonshine", description="Самогонщик: открыть меню предприятия")
async def moonshine_command(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "Эту команду можно использовать только на сервере.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)

        if not has_game_role(interaction.user, MOONSHINER_ROLE_KEY, account):
            save_economy()
            await interaction.followup.send(
                "Команда доступна только роли **Самогонщик**. Купить её можно через `/roles`.",
                ephemeral=True,
            )
            return

        embed = build_moonshine_embed(interaction.guild, account)
        save_economy()

    image = get_moonshine_image_file()
    view = MoonshineMainView(interaction.user.id)
    if image:
        await interaction.followup.send(
            embed=embed, view=view, file=image, ephemeral=True
        )
    else:
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


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


async def setup(bot):
    await bot.add_cog(MoonshinerCog(bot))
