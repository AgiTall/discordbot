import discord
from discord import app_commands
from discord.ext import commands
import math
from datetime import datetime, timedelta
from typing import Literal, Optional

from src.weapon_system import (
    AMMO_EMOJIS,
    AMMO_TYPE_NAMES,
    WEAPON_CLASS_NAMES,
    ammo_capacity,
    ammo_total,
    condition_stat_multiplier,
    equip_weapon,
    normalize_weapon_state,
    owned_weapon_keys,
    unequip_weapon,
    weapon_class,
    WEAPON_EMOJI_IDS,
    weapon_emoji,
)
from src.moonshiner_logic import add_moonshine_ingredient, get_moonshine_account
from emoji_config import DEFAULT_MOONSHINE_INGREDIENT_EMOJIS

from bot import (
    economy_lock,
    economy_data,
    get_account,
    get_gold_emoji,
    get_cash_emoji,
    get_safe_emoji,
    save_economy,
    format_money_plain,
    now_local,
    parse_local_datetime,
    set_economy_guild_id,
    reset_economy_guild_id,
)

# ─── Дефолтные эмодзи каталога ───

DEFAULT_CATALOG_TITLE_EMOJI = "📖"
DEFAULT_CATALOG_COMING_SOON_EMOJI = "🔜"
DEFAULT_CATALOG_BOUGHT_EMOJI = "✅"
DEFAULT_CATALOG_BUY_SUCCESS_EMOJI = "✅"

GUN_OIL_EMOJI = "<:kit_gun_oil:1527594712230527026>"

DEFAULT_CATALOG_CATEGORY_EMOJIS = {
    "revolvers": "🔫",
    "pistols": "🔫",
    "carbines": "💥",
    "rifles": "🎯",
    "shotguns": "💥",
    "hunting": "🎣",
    "ammo": "💥",
    "horses": "🐴",
    "weapon_equipment": "⚔️",
    "provisions": "🍖",
    "tonics": "🧪",
}

# ─── Геттеры эмодзи каталога ───


def get_catalog_emoji(key, default=None):
    """Получить кастомный эмодзи каталога из economy_data."""
    val = economy_data.get(f"catalog_{key}")
    if val:
        return str(val)
    return str(default) if default else ""


def get_catalog_title_emoji():
    return get_catalog_emoji("title", DEFAULT_CATALOG_TITLE_EMOJI)


def get_catalog_coming_soon_emoji():
    return get_catalog_emoji("coming_soon", DEFAULT_CATALOG_COMING_SOON_EMOJI)


def get_catalog_bought_emoji():
    return get_catalog_emoji("bought", DEFAULT_CATALOG_BOUGHT_EMOJI)


def get_catalog_buy_success_emoji():
    return get_catalog_emoji("buy_success", DEFAULT_CATALOG_BUY_SUCCESS_EMOJI)


def get_catalog_category_emoji(category_key):
    """Получить эмодзи категории каталога."""
    # Пробуем кастомный из economy_data
    val = economy_data.get(f"catalog_cat_{category_key}")
    if val:
        return str(val)
    if category_key.startswith("ammo_"):
        return AMMO_EMOJIS["normal"]
    return DEFAULT_CATALOG_CATEGORY_EMOJIS.get(category_key, "📦")


# ─── Категории каталога (в стиле Wheeler, Rawson & Co.) ───

CATALOG_CATEGORIES = {
    "revolvers": {
        "name": "Револьверы",
        "description": "Классические шестизарядные револьверы для Дикого Запада.",
    },
    "pistols": {
        "name": "Пистолеты",
        "description": "Современные самозарядные и рычажные пистолеты.",
    },
    "carbines": {
        "name": "Карабины",
        "description": "Многозарядные винтовки рычажного действия (Repeater).",
    },
    "rifles": {
        "name": "Винтовки",
        "description": "Мощные дальнобойные винтовки и снайперское оружие.",
    },
    "shotguns": {
        "name": "Дробовики",
        "description": "Смертоносное оружие для ближнего боя.",
    },
    "hunting": {
        "name": "Охота и рыбалка",
        "description": "Снаряжение для охотника и рыбака.",
    },
    "ammo_revolver": {"name": "Патроны · револьвер", "description": "Лимит 200 на каждый из двух взятых револьверов."},
    "ammo_pistol": {"name": "Патроны · пистолет", "description": "Лимит 100 на каждый из двух взятых пистолетов."},
    "ammo_repeater": {"name": "Патроны · карабин", "description": "Общий лимит карабинных патронов — 200."},
    "ammo_rifle": {"name": "Патроны · винтовка", "description": "Общий лимит винтовочных патронов — 100."},
    "ammo_shotgun": {"name": "Патроны · дробовик", "description": "Общий лимит дробовых патронов — 60."},
    "horses": {
        "name": "Лошади и сбруя",
        "description": "Лошади, сёдла, уздечки и аксессуары для ваших скакунов.",
    },
    "weapon_equipment": {
        "name": "Оружейное снаряжение",
        "description": "Кобуры, ремни, патронташи и улучшения для оружия.",
    },
    "provisions": {
        "name": "Провиант",
        "description": "Консервы и фрукты для особых рецептов самогонщика.",
    },
    "tonics": {
        "name": "Тоники",
        "description": "Лечебные и укрепляющие тоники, эликсиры.",
    },
}

# ─── Товары каталога ───
# Каждый товар привязан к категории через ключ category.
# type: "unique" — покупается один раз (как сейф), "consumable" — можно покупать много раз.

CATALOG_ITEMS = {
    # === Оружейное снаряжение ===
    "safe": {
        "name": "Сейф",
        "description": "Надёжно хранит деньги и золото от грабителей.",
        "base_price": 30,
        "currency": "gold",
        "emoji_func": get_safe_emoji,
        "category": "weapon_equipment",
        "type": "unique",
    },
    "gun_oil": {
        "name": "Оружейное масло",
        "description": "Полностью восстанавливает состояние одного оружия до 100%. Использование: `/gun-oil`.",
        "base_price": 12,
        "currency": "cash",
        "emoji": GUN_OIL_EMOJI,
        "category": "weapon_equipment",
        "type": "consumable",
    },
    # === Револьверы ===
    "revolver_cattleman": {
        "name": "Револьвер Cattleman",
        "description": "Классический шестизарядный револьвер. Надёжный и проверенный временем.",
        "base_price": 50,
        "currency": "cash",
        "emoji_func": None,
        "category": "revolvers",
        "type": "unique",
        "image": "ref/guns/weapon_revolver_cattleman.png"
    },
    "revolver_doubleaction": {
        "name": "Револьвер Double-Action",
        "description": "Скорострельный револьвер двойного действия. Идеально для стрельбы от бедра.",
        "base_price": 65,
        "currency": "cash",
        "emoji_func": None,
        "category": "revolvers",
        "type": "unique",
        "image": "ref/guns/weapon_revolver_doubleaction.png"
    },
    "revolver_doubleaction_gambler": {
        "name": "Револьвер Игрока",
        "description": "Изящный револьвер двойного действия с уникальной гравировкой.",
        "base_price": 15,
        "currency": "gold",
        "emoji_func": None,
        "category": "revolvers",
        "type": "unique",
        "image": "ref/guns/weapon_revolver_doubleaction_gambler.png"
    },
    "revolver_lemat": {
        "name": "Револьвер LeMat",
        "description": "Тяжёлый 9-зарядный револьвер с дополнительным стволом для дроби.",
        "base_price": 100,
        "currency": "cash",
        "emoji_func": None,
        "category": "revolvers",
        "type": "unique",
        "image": "ref/guns/weapon_revolver_lemat.png"
    },
    "revolver_schofield": {
        "name": "Револьвер Schofield",
        "description": "Мощный револьвер с переломной рамкой для быстрой перезарядки.",
        "base_price": 84,
        "currency": "cash",
        "emoji_func": None,
        "category": "revolvers",
        "type": "unique",
        "image": "ref/guns/weapon_revolver_schofield.png"
    },
    
    # === Пистолеты ===
    "pistol_mauser": {
        "name": "Пистолет Mauser",
        "description": "Современный пистолет с высокой скорострельностью и большим магазином.",
        "base_price": 150,
        "currency": "cash",
        "emoji_func": None,
        "category": "pistols",
        "type": "unique",
        "image": "ref/guns/weapon_pistol_mauser.png"
    },
    "pistol_semiauto": {
        "name": "Полуавтоматический пистолет",
        "description": "Пистолет нового поколения с отличным темпом стрельбы.",
        "base_price": 135,
        "currency": "cash",
        "emoji_func": None,
        "category": "pistols",
        "type": "unique",
        "image": "ref/guns/weapon_pistol_semiauto.png"
    },
    "pistol_volcanic": {
        "name": "Пистолет Volcanic",
        "description": "Оружие рычажного действия. Медленное, но очень мощное.",
        "base_price": 120,
        "currency": "cash",
        "emoji_func": None,
        "category": "pistols",
        "type": "unique",
        "image": "ref/guns/weapon_pistol_volcanic.png"
    },
    
    # === Карабины ===
    "repeater_carbine": {
        "name": "Карабин Repeater",
        "description": "Надёжный многозарядный карабин. Стандартное оружие многих.",
        "base_price": 90,
        "currency": "cash",
        "emoji_func": None,
        "category": "carbines",
        "type": "unique",
        "image": "ref/guns/weapon_repeater_carbine.png"
    },
    "repeater_henry": {
        "name": "Карабин Litchfield (Henry)",
        "description": "Тяжёлый карабин с высокой убойной силой, но медленной перезарядкой.",
        "base_price": 110,
        "currency": "cash",
        "emoji_func": None,
        "category": "carbines",
        "type": "unique",
        "image": "ref/guns/weapon_repeater_henry.png"
    },
    "repeater_lancaster": {
        "name": "Карабин Lancaster",
        "description": "Самый сбалансированный карабин с отличной скоростью и точностью.",
        "base_price": 135,
        "currency": "cash",
        "emoji_func": None,
        "category": "carbines",
        "type": "unique",
        "image": "ref/guns/weapon_repeater_lancaster.png"
    },
    
    # === Винтовки ===
    "rifle_boltaction": {
        "name": "Болтовая винтовка",
        "description": "Мощная и точная винтовка с продольно-скользящим затвором.",
        "base_price": 150,
        "currency": "cash",
        "emoji_func": None,
        "category": "rifles",
        "type": "unique",
        "image": "ref/guns/weapon_rifle_boltaction.png"
    },
    "rifle_elephant": {
        "name": "Слонобой",
        "description": "Невероятно мощное оружие для охоты на самых крупных хищников.",
        "base_price": 180,
        "currency": "cash",
        "emoji_func": None,
        "category": "rifles",
        "type": "unique",
        "image": "ref/guns/weapon_rifle_elephant.png"
    },
    "rifle_springfield": {
        "name": "Винтовка Springfield",
        "description": "Однозарядная винтовка с высокой убойной силой.",
        "base_price": 120,
        "currency": "cash",
        "emoji_func": None,
        "category": "rifles",
        "type": "unique",
        "image": "ref/guns/weapon_rifle_springfield.png"
    },
    "rifle_varmint": {
        "name": "Варминт-винтовка",
        "description": "Мелкокалиберная винтовка для охоты на мелкую дичь.",
        "base_price": 72,
        "currency": "cash",
        "emoji_func": None,
        "category": "rifles",
        "type": "unique",
        "image": "ref/guns/weapon_rifle_varmint.png"
    },
    "sniperrifle_carcano": {
        "name": "Винтовка Carcano",
        "description": "Дальнобойная снайперская винтовка со скользящим затвором.",
        "base_price": 190,
        "currency": "cash",
        "emoji_func": None,
        "category": "rifles",
        "type": "unique",
        "image": "ref/guns/weapon_sniperrifle_carcano.png"
    },
    "sniperrifle_rollingblock": {
        "name": "Винтовка Rolling Block",
        "description": "Классическая однозарядная снайперская винтовка.",
        "base_price": 175,
        "currency": "cash",
        "emoji_func": None,
        "category": "rifles",
        "type": "unique",
        "image": "ref/guns/weapon_sniperrifle_rollingblock.png"
    },
    
    # === Дробовики ===
    "shotgun_doublebarrel": {
        "name": "Двуствольный дробовик",
        "description": "Классическая двустволка. Смертоносна на ближней дистанции.",
        "base_price": 80,
        "currency": "cash",
        "emoji_func": None,
        "category": "shotguns",
        "type": "unique",
        "image": "ref/guns/weapon_shotgun_doublebarrel.png"
    },
    "shotgun_doublebarrel_exotic": {
        "name": "Редкий дробовик",
        "description": "Уникальный двуствольный дробовик с гравировками.",
        "base_price": 20,
        "currency": "gold",
        "emoji_func": None,
        "category": "shotguns",
        "type": "unique",
        "image": "ref/guns/weapon_shotgun_doublebarrel_exotic.png"
    },
    "shotgun_pump": {
        "name": "Помповый дробовик",
        "description": "Современный помповый дробовик, надёжный выбор.",
        "base_price": 130,
        "currency": "cash",
        "emoji_func": None,
        "category": "shotguns",
        "type": "unique",
        "image": "ref/guns/weapon_shotgun_pump.png"
    },
    "shotgun_repeating": {
        "name": "Дробовик рычажного действия",
        "description": "Многозарядный дробовик с механизмом как у карабина.",
        "base_price": 145,
        "currency": "cash",
        "emoji_func": None,
        "category": "shotguns",
        "type": "unique",
        "image": "ref/guns/weapon_shotgun_repeating.png"
    },
    "shotgun_sawedoff": {
        "name": "Обрез дробовика",
        "description": "Укороченный дробовик, который можно носить в кобуре.",
        "base_price": 75,
        "currency": "cash",
        "emoji_func": None,
        "category": "shotguns",
        "type": "unique",
        "image": "ref/guns/weapon_shotgun_sawedoff.png"
    },
    "shotgun_semiauto": {
        "name": "Полуавтоматический дробовик",
        "description": "Самый скорострельный дробовик, выкашивает врагов за секунды.",
        "base_price": 160,
        "currency": "cash",
        "emoji_func": None,
        "category": "shotguns",
        "type": "unique",
        "image": "ref/guns/weapon_shotgun_semiauto.png"
    },
    # === Охота и рыбалка (заготовки) ===
    # Боеприпасы добавляются ниже из единой таблицы, чтобы цены и пачки не расходились.
    # === Лошади и сбруя (заготовки) ===
    # === Провиант (заготовки) ===
    # === Тоники (заготовки) ===
}

for _weapon_key in WEAPON_EMOJI_IDS:
    if _weapon_key in CATALOG_ITEMS:
        CATALOG_ITEMS[_weapon_key]["emoji"] = weapon_emoji(_weapon_key)

_AMMO_CLASS_SETTINGS = {
    "revolver": {"category": "ammo_revolver", "box": 20, "price": 8, "types": tuple(AMMO_TYPE_NAMES)},
    "pistol": {"category": "ammo_pistol", "box": 20, "price": 10, "types": tuple(AMMO_TYPE_NAMES)},
    "repeater": {"category": "ammo_repeater", "box": 30, "price": 12, "types": tuple(AMMO_TYPE_NAMES)},
    "rifle": {"category": "ammo_rifle", "box": 20, "price": 14, "types": tuple(AMMO_TYPE_NAMES)},
    # Для дробовика не продаём бессмысленные «скоростные» и «с надрезом».
    "shotgun": {"category": "ammo_shotgun", "box": 12, "price": 12, "types": ("normal", "explosive")},
}
_AMMO_PRICE_MULTIPLIERS = {
    "normal": 1.0, "split_point": 1.25, "high_velocity": 1.5,
    "express": 1.75, "explosive": 2.5,
}
for _class_key, _settings in _AMMO_CLASS_SETTINGS.items():
    for _ammo_type, _ammo_name in AMMO_TYPE_NAMES.items():
        if _ammo_type not in _settings["types"]:
            continue
        _item_key = f"ammo_{_class_key}_{_ammo_type}"
        CATALOG_ITEMS[_item_key] = {
            "name": f"{_ammo_name.capitalize()} · {WEAPON_CLASS_NAMES[_class_key]}",
            "description": f"Коробка: {_settings['box']} шт.",
            "base_price": math.ceil(_settings["price"] * _AMMO_PRICE_MULTIPLIERS[_ammo_type]),
            "currency": "cash",
            "emoji": AMMO_EMOJIS[_ammo_type],
            "category": _settings["category"],
            "type": "ammo",
            "ammo_class": _class_key,
            "ammo_type": _ammo_type,
            "quantity": _settings["box"],
        }

_MOONSHINE_PROVISIONS = {
    "provision_canned_strawberries": ("Консервированная клубника", 4),
    "provision_canned_peaches": ("Консервированные персики", 5),
    "provision_canned_apricots": ("Консервированные абрикосы", 5),
    "provision_canned_pineapple": ("Консервированные ананасы", 6),
    "provision_apple": ("Яблоко", 2),
    "provision_peach": ("Персик", 2),
    "provision_pear": ("Груша", 2),
}
for _item_key, (_ingredient_name, _price) in _MOONSHINE_PROVISIONS.items():
    CATALOG_ITEMS[_item_key] = {
        "name": _ingredient_name,
        "description": "Ингредиент для особых рецептов Марселя · 1 шт.",
        "base_price": _price,
        "currency": "cash",
        "emoji": DEFAULT_MOONSHINE_INGREDIENT_EMOJIS[_ingredient_name],
        "category": "provisions",
        "type": "moonshine_ingredient",
        "ingredient": _ingredient_name,
        "quantity": 1,
    }

SAFE_COOLDOWN_HOURS = 3


def get_item_emoji(item_data):
    """Получить эмодзи товара."""
    func = item_data.get("emoji_func")
    if func:
        return func()
    return item_data.get("emoji", "📦")


def get_category_items(category_key):
    """Получить все товары для указанной категории."""
    return {
        key: item for key, item in CATALOG_ITEMS.items()
        if item["category"] == category_key
    }


def build_catalog_messages(category_key, account, guild_id):
    """Создать embeds и файлы для страницы категории каталога."""
    normalize_weapon_state(account, CATALOG_ITEMS)
    cat = CATALOG_CATEGORIES[category_key]
    items = get_category_items(category_key)

    guild_data = economy_data.current()
    discounts = guild_data.get("shop_discounts", {})

    cat_emoji = get_catalog_category_emoji(category_key)
    title_emoji = get_catalog_title_emoji()

    main_embed = discord.Embed(
        title=f"{title_emoji} Каталог — {cat_emoji} {cat['name']}",
        description=cat["description"],
        color=discord.Color.from_rgb(139, 109, 68),  # Тёплый коричневый, стиль RDR2
    )

    embeds = [main_embed]
    files = []

    if not items:
        coming_soon = get_catalog_coming_soon_emoji()
        main_embed.add_field(
            name=f"{coming_soon} Скоро в продаже",
            value="*Товары этой категории пока не завезли. Следите за обновлениями!*",
            inline=False,
        )
    else:
        for item_key, item_data in items.items():
            discount_percent = discounts.get(item_key, 0)
            price = item_data["base_price"]
            if discount_percent > 0:
                price = math.floor(price * (1 - discount_percent / 100))

            emoji = get_gold_emoji() if item_data["currency"] == "gold" else get_cash_emoji()
            item_emoji = get_item_emoji(item_data)
            price_text = f"**{price}** {emoji}"
            if discount_percent > 0:
                price_text += f" *(Скидка {discount_percent}%)*"

            # Показать статус владения для unique товаров
            status = ""
            if item_data["type"] == "unique":
                inventory = account.get("inventory", {})
                if inventory.get(item_key, 0) > 0:
                    bought_emoji = get_catalog_bought_emoji()
                    status = f" {bought_emoji} *Куплено*"

            item_description = item_data["description"]
            if item_data["type"] == "ammo":
                class_key = item_data["ammo_class"]
                current = ammo_total(account, class_key)
                capacity = ammo_capacity(account, class_key, CATALOG_ITEMS)
                item_description += f"\nБоезапас класса: **{current}/{capacity}**."
            elif item_data["type"] == "moonshine_ingredient":
                moonshine = get_moonshine_account(account)
                stored = moonshine["ingredients"].get(item_data["ingredient"], 0)
                item_description += f"\nНа складе самогонщика: **{stored} шт.**"

            if "image" in item_data:
                item_embed = discord.Embed(
                    title=f"{item_emoji} {item_data['name']}{status}",
                    description=f"{item_description}\nЦена: {price_text}",
                    color=discord.Color.from_rgb(139, 109, 68),
                )
                filename = item_data["image"].split("/")[-1]
                files.append(discord.File(item_data["image"], filename=filename))
                item_embed.set_thumbnail(url=f"attachment://{filename}")
                embeds.append(item_embed)
            else:
                main_embed.add_field(
                    name=f"{item_emoji} {item_data['name']}{status}",
                    value=f"{item_description}\nЦена: {price_text}",
                    inline=False,
                )

    # Навигация — столбиком
    nav_lines = []
    for key, c in CATALOG_CATEGORIES.items():
        c_emoji = get_catalog_category_emoji(key)
        marker = "▸ " if key == category_key else "  "
        nav_lines.append(f"{marker}{c_emoji} {c['name']}")
    
    # Discord footers are plain text and show custom emoji markup literally.
    # Embed fields support custom emojis, so navigation belongs here.
    embeds[-1].add_field(
        name="Разделы каталога",
        value="\n".join(nav_lines),
        inline=False,
    )
    embeds[-1].set_footer(text="Wheeler, Rawson & Co.")

    return embeds, files


# ─── Кнопки покупки ───

def _russian_plural(value, one, few, many):
    """Return a Russian noun form for an integer catalog price."""
    amount = abs(int(value))
    if amount % 100 in range(11, 15):
        return many
    if amount % 10 == 1:
        return one
    if amount % 10 in range(2, 5):
        return few
    return many


def _button_price_text(price, currency):
    amount = f"{price:g}" if isinstance(price, float) else str(price)
    if currency == "gold":
        unit = _russian_plural(price, "слиток золота", "слитка золота", "слитков золота")
    else:
        unit = _russian_plural(price, "доллар", "доллара", "долларов")
    return f"{amount} {unit}"


class CatalogBuyButton(discord.ui.Button):
    def __init__(self, item_key, item_data, price, already_owned, discount_percent=0):
        self.item_key = item_key
        self.item_data = item_data
        self.price = price

        # Discord does not render custom-emoji markup inside a button label.
        # Keep prices as readable Russian text; use the product icon separately.
        label = f"Купить {item_data['name']} — {_button_price_text(price, item_data['currency'])}"
        if discount_percent > 0:
            label += f" [-{discount_percent}%]"

        item_emoji = get_item_emoji(item_data)

        super().__init__(
            label="Уже куплено" if already_owned else label,
            style=discord.ButtonStyle.secondary if already_owned else discord.ButtonStyle.success,
            custom_id=f"catalog_buy_{item_key}",
            emoji=item_emoji,
            disabled=already_owned,
        )

    async def callback(self, interaction: discord.Interaction):
        async with economy_lock:
            account = get_account(interaction.user.id)
            inventory = account.setdefault("inventory", {})
            normalize_weapon_state(account, CATALOG_ITEMS)

            if self.item_data["type"] == "unique" and inventory.get(self.item_key, 0) > 0:
                await interaction.response.send_message(
                    f"У вас уже есть {self.item_data['name']}!", ephemeral=True
                )
                return

            if self.item_data["type"] == "ammo":
                class_key = self.item_data["ammo_class"]
                capacity = ammo_capacity(account, class_key, CATALOG_ITEMS)
                current = ammo_total(account, class_key)
                quantity = self.item_data["quantity"]
                if capacity <= 0:
                    await interaction.response.send_message(
                        f"Сначала возьмите с собой {WEAPON_CLASS_NAMES[class_key]} через `/weapon-equip`.",
                        ephemeral=True,
                    )
                    return
                if current + quantity > capacity:
                    await interaction.response.send_message(
                        f"Коробка не помещается: сейчас **{current}/{capacity}**, в коробке **{quantity}** шт.",
                        ephemeral=True,
                    )
                    return

            if account.get(self.item_data["currency"], 0.0) < self.price:
                currency_emoji = get_gold_emoji() if self.item_data["currency"] == "gold" else get_cash_emoji()
                await interaction.response.send_message(
                    f"Недостаточно средств. Нужно {self.price} {currency_emoji}.",
                    ephemeral=True,
                )
                return

            account[self.item_data["currency"]] -= self.price
            if self.item_data["type"] == "unique":
                inventory[self.item_key] = 1
                if weapon_class(self.item_key, self.item_data):
                    account["weapon_condition"][self.item_key] = 100.0
                    equip_weapon(account, self.item_key, CATALOG_ITEMS)
            elif self.item_data["type"] == "ammo":
                class_ammo = account["ammo"][self.item_data["ammo_class"]]
                ammo_type = self.item_data["ammo_type"]
                class_ammo[ammo_type] += self.item_data["quantity"]
            elif self.item_data["type"] == "moonshine_ingredient":
                stored_ingredient = add_moonshine_ingredient(
                    account, self.item_data["ingredient"], self.item_data["quantity"]
                )
            else:
                inventory[self.item_key] = inventory.get(self.item_key, 0) + 1
            save_economy()

            emoji = get_gold_emoji() if self.item_data["currency"] == "gold" else get_cash_emoji()
            success_emoji = get_catalog_buy_success_emoji()
            if self.item_data["type"] == "ammo":
                class_key = self.item_data["ammo_class"]
                stock = ammo_total(account, class_key)
                capacity = ammo_capacity(account, class_key, CATALOG_ITEMS)
                result = (
                    f"{success_emoji} Куплено **{self.item_data['quantity']} шт.** — "
                    f"**{self.item_data['name']}** за {self.price} {emoji}.\n"
                    f"Боезапас: **{stock}/{capacity}**."
                )
            elif self.item_data["type"] == "moonshine_ingredient":
                result = (
                    f"{success_emoji} Куплено: **{self.item_data['name']} x{self.item_data['quantity']}** "
                    f"за {self.price} {emoji}.\n"
                    f"На складе самогонщика: **{stored_ingredient} шт.**"
                )
            else:
                result = f"{success_emoji} Вы успешно купили **{self.item_data['name']}** за {self.price} {emoji}!"
            await interaction.response.send_message(result, ephemeral=True)

            # Обновить кнопку если unique
            if self.item_data["type"] == "unique":
                self.disabled = True
                self.label = "Уже куплено"
                self.style = discord.ButtonStyle.secondary
                await interaction.message.edit(view=self.view)


# ─── Селектор категорий ───

class CatalogCategorySelect(discord.ui.Select):
    def __init__(self, current_category):
        options = []
        for key, cat in CATALOG_CATEGORIES.items():
            cat_emoji = get_catalog_category_emoji(key)
            options.append(
                discord.SelectOption(
                    label=cat["name"],
                    value=key,
                    emoji=cat_emoji,
                    description=cat["description"][:100],
                    default=(key == current_category),
                )
            )
        super().__init__(
            placeholder="Выберите раздел каталога...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        account = get_account(interaction.user.id)
        embeds, files = build_catalog_messages(selected, account, interaction.guild_id)
        view = CatalogView(interaction.guild_id, interaction.user, account, selected)
        await interaction.response.edit_message(embeds=embeds, attachments=files, view=view)


# ─── Главный View каталога ───

class CatalogView(discord.ui.View):
    def __init__(self, guild_id, member, account, current_category="revolvers"):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.member = member
        self.account = account
        self.current_category = current_category
        normalize_weapon_state(account, CATALOG_ITEMS)

        # Селектор категорий
        self.add_item(CatalogCategorySelect(current_category))

        # Кнопки покупки для текущей категории
        items = get_category_items(current_category)
        guild_data = economy_data.current()
        discounts = guild_data.get("shop_discounts", {})

        for item_key, item_data in items.items():
            discount_percent = discounts.get(item_key, 0)
            price = item_data["base_price"]
            if discount_percent > 0:
                price = math.floor(price * (1 - discount_percent / 100))

            inventory = account.get("inventory", {})
            already_owned = (
                item_data["type"] == "unique" and inventory.get(item_key, 0) > 0
            )

            self.add_item(
                CatalogBuyButton(item_key, item_data, price, already_owned, discount_percent)
            )

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "Это не ваш каталог!", ephemeral=True
            )
            return False
        return True


# ─── Cog ───

class CatalogCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="catalog", description="Открыть каталог товаров Wheeler, Rawson & Co.")
    async def catalog_cmd(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            account = get_account(interaction.user.id)
            current_category = "revolvers"  # Начинаем с револьверов

            embeds, files = build_catalog_messages(current_category, account, interaction.guild_id)
            view = CatalogView(interaction.guild_id, interaction.user, account, current_category)

            await interaction.response.send_message(embeds=embeds, files=files, view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="weapons", description="Показать оружие, боезапас и активное снаряжение")
    async def weapons_cmd(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                normalize_weapon_state(account, CATALOG_ITEMS)
                loadout = account["weapon_loadout"]

                def weapon_line(key):
                    item = CATALOG_ITEMS[key]
                    condition = account["weapon_condition"].get(key, 100.0)
                    effectiveness = round(condition_stat_multiplier(condition) * 100)
                    return f"• **{item['name']}** — состояние {condition:g}% · характеристики {effectiveness}%"

                sidearm_lines = [weapon_line(key) for key in loadout["sidearms"]]
                longarm_lines = [weapon_line(key) for key in loadout["longarms"]]
                ammo_lines = []
                for class_key, class_name in WEAPON_CLASS_NAMES.items():
                    capacity = ammo_capacity(account, class_key, CATALOG_ITEMS)
                    current = ammo_total(account, class_key)
                    selected = account["selected_ammo"][class_key]
                    ammo_lines.append(
                        f"• {class_name.capitalize()}: **{current}/{capacity}** · "
                        f"заряжены: {AMMO_TYPE_NAMES[selected]}"
                    )
                oil = int(account.get("inventory", {}).get("gun_oil", 0) or 0)
                save_economy()

            embed = discord.Embed(
                title="🔫 Оружие и боезапас",
                description=(
                    "Состояние снижает характеристики оружия вплоть до 60% от исходных. "
                    "Оружейное масло полностью очищает выбранное оружие."
                ),
                color=discord.Color.from_rgb(139, 109, 68),
            )
            embed.add_field(
                name="Короткоствольное · максимум 2 одного класса",
                value="\n".join(sidearm_lines) or "*Слоты пусты*",
                inline=False,
            )
            embed.add_field(
                name="Крупное оружие · максимум 2",
                value="\n".join(longarm_lines) or "*Слоты пусты*",
                inline=False,
            )
            embed.add_field(name="Боезапас", value="\n".join(ammo_lines), inline=False)
            embed.add_field(name="Уход", value=f"{GUN_OIL_EMOJI} Оружейное масло: **{oil} шт.**", inline=False)
            embed.set_footer(text="/weapon-equip · /weapon-unequip · /ammo-select · /gun-oil")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="weapon-equip", description="Взять купленное оружие с собой")
    @app_commands.describe(weapon="Ключ или название купленного оружия")
    async def weapon_equip_cmd(self, interaction: discord.Interaction, weapon: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                normalize_weapon_state(account, CATALOG_ITEMS)
                ok, message = equip_weapon(account, weapon, CATALOG_ITEMS)
                if ok:
                    save_economy()
                name = CATALOG_ITEMS.get(weapon, {}).get("name", weapon)
            await interaction.response.send_message(
                f"{'✅' if ok else '⚠️'} **{name}**: {message}", ephemeral=True
            )
        finally:
            reset_economy_guild_id(token)

    @weapon_equip_cmd.autocomplete("weapon")
    async def weapon_equip_autocomplete(self, interaction: discord.Interaction, current: str):
        account = get_account(interaction.user.id)
        normalize_weapon_state(account, CATALOG_ITEMS)
        current = current.casefold()
        return [
            app_commands.Choice(name=CATALOG_ITEMS[key]["name"], value=key)
            for key in owned_weapon_keys(account, CATALOG_ITEMS)
            if current in CATALOG_ITEMS[key]["name"].casefold() or current in key.casefold()
        ][:25]

    @app_commands.command(name="weapon-unequip", description="Убрать оружие из активного снаряжения")
    @app_commands.describe(weapon="Оружие, которое нужно убрать")
    async def weapon_unequip_cmd(self, interaction: discord.Interaction, weapon: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                normalize_weapon_state(account, CATALOG_ITEMS)
                removed = unequip_weapon(account, weapon)
                if removed:
                    save_economy()
                name = CATALOG_ITEMS.get(weapon, {}).get("name", weapon)
            message = f"✅ **{name}** убрано." if removed else "⚠️ Это оружие сейчас не взято с собой."
            await interaction.response.send_message(message, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @weapon_unequip_cmd.autocomplete("weapon")
    async def weapon_unequip_autocomplete(self, interaction: discord.Interaction, current: str):
        account = get_account(interaction.user.id)
        normalize_weapon_state(account, CATALOG_ITEMS)
        equipped = account["weapon_loadout"]["sidearms"] + account["weapon_loadout"]["longarms"]
        current = current.casefold()
        return [
            app_commands.Choice(name=CATALOG_ITEMS[key]["name"], value=key)
            for key in equipped
            if current in CATALOG_ITEMS[key]["name"].casefold() or current in key.casefold()
        ][:25]

    @app_commands.command(name="gun-oil", description="Восстановить состояние оружия до 100%")
    @app_commands.describe(weapon="Купленное оружие для чистки")
    async def gun_oil_cmd(self, interaction: discord.Interaction, weapon: str):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                normalize_weapon_state(account, CATALOG_ITEMS)
                inventory = account.setdefault("inventory", {})
                if weapon not in owned_weapon_keys(account, CATALOG_ITEMS):
                    message = "⚠️ Это оружие не куплено."
                elif inventory.get("gun_oil", 0) <= 0:
                    message = f"⚠️ Нет оружейного масла. Купите его в разделе снаряжения `/catalog`."
                elif account["weapon_condition"].get(weapon, 100.0) >= 100.0:
                    message = "⚠️ Оружие уже находится в идеальном состоянии."
                else:
                    old_condition = account["weapon_condition"][weapon]
                    inventory["gun_oil"] -= 1
                    account["weapon_condition"][weapon] = 100.0
                    save_economy()
                    name = CATALOG_ITEMS[weapon]["name"]
                    message = f"{GUN_OIL_EMOJI} **{name}** очищено: {old_condition:g}% → **100%**."
            await interaction.response.send_message(message, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @gun_oil_cmd.autocomplete("weapon")
    async def gun_oil_autocomplete(self, interaction: discord.Interaction, current: str):
        account = get_account(interaction.user.id)
        normalize_weapon_state(account, CATALOG_ITEMS)
        current = current.casefold()
        return [
            app_commands.Choice(name=CATALOG_ITEMS[key]["name"], value=key)
            for key in owned_weapon_keys(account, CATALOG_ITEMS)
            if current in CATALOG_ITEMS[key]["name"].casefold() or current in key.casefold()
        ][:25]

    @app_commands.command(name="ammo-select", description="Выбрать тип патронов для класса оружия")
    @app_commands.choices(
        weapon_class_name=[
            app_commands.Choice(name="Револьвер", value="revolver"),
            app_commands.Choice(name="Пистолет", value="pistol"),
            app_commands.Choice(name="Карабин", value="repeater"),
            app_commands.Choice(name="Винтовка", value="rifle"),
            app_commands.Choice(name="Дробовик", value="shotgun"),
        ],
        ammo_type=[
            app_commands.Choice(name="Обычные", value="normal"),
            app_commands.Choice(name="С надрезом", value="split_point"),
            app_commands.Choice(name="Скоростные", value="high_velocity"),
            app_commands.Choice(name="Экспресс", value="express"),
            app_commands.Choice(name="Разрывные экспресс", value="explosive"),
        ],
    )
    async def ammo_select_cmd(
        self,
        interaction: discord.Interaction,
        weapon_class_name: app_commands.Choice[str],
        ammo_type: app_commands.Choice[str],
    ):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                normalize_weapon_state(account, CATALOG_ITEMS)
                class_key = weapon_class_name.value
                type_key = ammo_type.value
                stock = account["ammo"][class_key][type_key]
                if stock <= 0:
                    message = (
                        f"⚠️ Нет патронов типа **{AMMO_TYPE_NAMES[type_key]}** "
                        f"для класса «{WEAPON_CLASS_NAMES[class_key]}»."
                    )
                else:
                    account["selected_ammo"][class_key] = type_key
                    save_economy()
                    message = (
                        f"{AMMO_EMOJIS[type_key]} Для класса «{WEAPON_CLASS_NAMES[class_key]}» "
                        f"заряжены **{AMMO_TYPE_NAMES[type_key]}** патроны · {stock} шт."
                    )
            await interaction.response.send_message(message, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(
        name="set-discount-shop",
        description="Установить скидку на товар в каталоге",
    )
    @app_commands.default_permissions(administrator=True)
    async def set_discount_cmd(
        self, interaction: discord.Interaction, item: str, discount: int
    ):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if item not in CATALOG_ITEMS:
                items_list = ", ".join(CATALOG_ITEMS.keys())
                await interaction.response.send_message(
                    f"Товар не найден. Доступные товары: {items_list}",
                    ephemeral=True,
                )
                return

            if discount < 0 or discount > 100:
                await interaction.response.send_message(
                    "Скидка должна быть от 0 до 100.", ephemeral=True
                )
                return

            async with economy_lock:
                guild_data = economy_data.current()
                discounts = guild_data.setdefault("shop_discounts", {})
                if discount == 0:
                    if item in discounts:
                        del discounts[item]
                else:
                    discounts[item] = discount
                save_economy()

            await interaction.response.send_message(
                f"Скидка на **{CATALOG_ITEMS[item]['name']}** установлена: {discount}%",
                ephemeral=True,
            )
        finally:
            reset_economy_guild_id(token)

    # ── SAFE MECHANICS (перенесено из shop.py) ──

    @app_commands.command(
        name="safe-money", description="Положить деньги или золото в сейф"
    )
    async def safe_money_cmd(
        self,
        interaction: discord.Interaction,
        currency: Literal["Деньги", "Золото"],
        amount: float,
    ):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message(
                    "Сумма должна быть больше нуля.", ephemeral=True
                )
                return

            async with economy_lock:
                account = get_account(interaction.user.id)
                inventory = account.get("inventory", {})

                if inventory.get("safe", 0) <= 0:
                    await interaction.response.send_message(
                        "У вас нет сейфа! Вы можете купить его в `/catalog`.",
                        ephemeral=True,
                    )
                    return

                curr_key = "cash" if currency == "Деньги" else "gold"
                safe_key = "safe_cash" if currency == "Деньги" else "safe_gold"

                balance = account.get(curr_key, 0.0)
                if balance < amount:
                    await interaction.response.send_message(
                        f"Недостаточно средств. У вас {format_money_plain(balance)} {currency.lower()}.",
                        ephemeral=True,
                    )
                    return

                account[curr_key] -= amount
                account.setdefault(safe_key, 0.0)
                account[safe_key] += amount
                save_economy()

                emoji = (
                    get_cash_emoji() if currency == "Деньги" else get_gold_emoji()
                )
                await interaction.response.send_message(
                    f"Вы положили {amount} {emoji} в сейф. Теперь в сейфе: {account[safe_key]} {emoji}."
                )
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(
        name="safe-take-money",
        description="Взять деньги или золото из сейфа (кулдаун 3 часа)",
    )
    async def safe_take_money_cmd(
        self,
        interaction: discord.Interaction,
        currency: Literal["Деньги", "Золото"],
        amount: float,
    ):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            if amount <= 0:
                await interaction.response.send_message(
                    "Сумма должна быть больше нуля.", ephemeral=True
                )
                return

            async with economy_lock:
                account = get_account(interaction.user.id)
                inventory = account.get("inventory", {})

                if inventory.get("safe", 0) <= 0:
                    await interaction.response.send_message(
                        "У вас нет сейфа!", ephemeral=True
                    )
                    return

                # Check cooldown
                cooldowns = account.setdefault("cooldowns", {})
                last_withdraw = cooldowns.get("safe_withdraw_at")
                if last_withdraw:
                    last_time = parse_local_datetime(last_withdraw)
                    now = now_local()
                    diff = (now - last_time).total_seconds()
                    if diff < SAFE_COOLDOWN_HOURS * 3600:
                        remaining = int(SAFE_COOLDOWN_HOURS * 3600 - diff)
                        hours, remainder = divmod(remaining, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        await interaction.response.send_message(
                            f"Сейф заблокирован! Вы сможете открыть его через **{hours} ч. {minutes} м.**",
                            ephemeral=True,
                        )
                        return

                safe_key = "safe_cash" if currency == "Деньги" else "safe_gold"
                curr_key = "cash" if currency == "Деньги" else "gold"

                safe_balance = account.get(safe_key, 0.0)
                if safe_balance < amount:
                    await interaction.response.send_message(
                        f"В сейфе недостаточно средств. Там лежит {format_money_plain(safe_balance)} {currency.lower()}.",
                        ephemeral=True,
                    )
                    return

                account[safe_key] -= amount
                account[curr_key] += amount
                cooldowns["safe_withdraw_at"] = now_local().isoformat(
                    timespec="seconds"
                )
                save_economy()

                emoji = (
                    get_cash_emoji() if currency == "Деньги" else get_gold_emoji()
                )
                await interaction.response.send_message(
                    f"Вы забрали {amount} {emoji} из сейфа."
                )
        finally:
            reset_economy_guild_id(token)


async def setup(bot):
    await bot.add_cog(CatalogCog(bot))
