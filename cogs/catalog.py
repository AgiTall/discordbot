import discord
from discord import app_commands
from discord.ext import commands
import logging
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
from src.company_logic import (
    COMPANY_DEFINITIONS,
    WHEELER_RAWSON,
    add_investment,
    combined_discount_percent,
    get_company_state,
    investor_discount_percent,
    next_level_threshold,
    personal_investment,
    progress_bar,
)
from emoji_config import (
    DEFAULT_MOONSHINE_INGREDIENT_EMOJIS,
    DEFAULT_BALANCE_WEAPON_EMOJI,
    EMOJI_ADD,
    EMOJI_BOOK,
    EMOJI_EDIT,
    EMOJI_LEVEL,
    EMOJI_MEMBERS,
    EMOJI_SEARCH,
    EMOJI_PACKAGE,
    EMOJI_PAW,
    EMOJI_POTION,
    EMOJI_SHOP,
    EMOJI_SUCCESS,
    EMOJI_TROPHY,
    EMOJI_WARNING,
    EMOJI_WEAPON,
)

from bot import (
    economy_lock,
    economy_data,
    get_account,
    get_gold_emoji,
    get_cash_emoji,
    get_safe_emoji,
    get_lock_emoji,
    save_economy,
    build_balance_embed,
    format_gold,
    format_money,
    format_money_plain,
    update_gold_rate,
    now_local,
    parse_local_datetime,
    set_economy_guild_id,
    reset_economy_guild_id,
)

# ─── Дефолтные эмодзи каталога ───

DEFAULT_CATALOG_TITLE_EMOJI = EMOJI_BOOK
DEFAULT_CATALOG_COMING_SOON_EMOJI = EMOJI_WARNING
DEFAULT_CATALOG_BOUGHT_EMOJI = EMOJI_SUCCESS
DEFAULT_CATALOG_BUY_SUCCESS_EMOJI = EMOJI_SUCCESS

GUN_OIL_EMOJI = "<:kit_gun_oil:1527594712230527026>"

DEFAULT_CATALOG_CATEGORY_EMOJIS = {
    "revolvers": EMOJI_WEAPON,
    "pistols": EMOJI_WEAPON,
    "carbines": EMOJI_WEAPON,
    "rifles": EMOJI_WEAPON,
    "shotguns": EMOJI_WEAPON,
    "hunting": EMOJI_PAW,
    "ammo": EMOJI_WEAPON,
    "horses": "🐴",
    "weapon_equipment": EMOJI_WEAPON,
    "provisions": EMOJI_PACKAGE,
    "tonics": EMOJI_POTION,
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
    return DEFAULT_CATALOG_CATEGORY_EMOJIS.get(category_key, EMOJI_PACKAGE)


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
        "description": "Полностью восстанавливает состояние одного оружия до 100%. Использование: `/balance` → «Оружие».",
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


_COMPANY_LEVEL_4_ITEMS = {
    "revolver_doubleaction_gambler",
    "shotgun_doublebarrel_exotic",
}
_COMPANY_LEVEL_3_ITEMS = {
    "revolver_lemat",
    "pistol_mauser",
    "pistol_semiauto",
    "rifle_elephant",
    "sniperrifle_carcano",
    "sniperrifle_rollingblock",
    "shotgun_semiauto",
}
_COMPANY_LEVEL_2_ITEMS = {
    "revolver_schofield",
    "pistol_volcanic",
    "repeater_henry",
    "repeater_lancaster",
    "rifle_boltaction",
    "rifle_springfield",
    "shotgun_pump",
    "shotgun_repeating",
}


def _required_company_level(item_key, item_data):
    if item_key in _COMPANY_LEVEL_4_ITEMS:
        return 4
    if item_key in _COMPANY_LEVEL_3_ITEMS:
        return 3
    if item_key in _COMPANY_LEVEL_2_ITEMS:
        return 2
    if item_data.get("type") == "ammo":
        ammo_type = item_data.get("ammo_type")
        if ammo_type == "explosive":
            return 4
        if ammo_type == "express":
            return 3
        if ammo_type in {"split_point", "high_velocity"}:
            return 2
    return 1


for _item_key, _item_data in CATALOG_ITEMS.items():
    _item_data["company"] = WHEELER_RAWSON
    _item_data["required_company_level"] = _required_company_level(_item_key, _item_data)

SAFE_COOLDOWN_HOURS = 3


def get_item_emoji(item_data):
    """Получить эмодзи товара."""
    func = item_data.get("emoji_func")
    if func:
        return func()
    return item_data.get("emoji", EMOJI_PACKAGE)


def get_category_items(category_key):
    """Получить все товары для указанной категории."""
    return {
        key: item for key, item in CATALOG_ITEMS.items()
        if item["category"] == category_key
    }


def get_catalog_price(item_key, item_data, guild_data, user_id):
    """Return the live price and applied total discount for a player."""
    item_discount = guild_data.get("shop_discounts", {}).get(item_key, 0)
    investor_discount = 0
    company_id = item_data.get("company")
    # Investments are made in cash, so their perk only affects cash goods.
    if company_id and item_data.get("currency") == "cash":
        state = get_company_state(guild_data, company_id)
        investor_discount = investor_discount_percent(state, user_id)
    discount = combined_discount_percent(item_discount, investor_discount)
    price = item_data["base_price"]
    if discount:
        price = max(1, math.floor(price * (1 - discount / 100)))
    return price, discount


def is_item_unlocked(item_data, guild_data):
    company_id = item_data.get("company")
    if not company_id:
        return True
    state = get_company_state(guild_data, company_id)
    return state["level"] >= int(item_data.get("required_company_level", 1))


def build_company_embed(guild_data, user_id, notice=None):
    company_id = WHEELER_RAWSON
    definition = COMPANY_DEFINITIONS[company_id]
    state = get_company_state(guild_data, company_id)
    threshold = next_level_threshold(company_id, state["level"])
    own = personal_investment(state, user_id)
    discount = investor_discount_percent(state, user_id)

    if threshold is None:
        progress = f"{progress_bar(state['invested'], None)} **Максимальный уровень**"
    else:
        remaining = max(0, threshold - state["invested"])
        progress = (
            f"{progress_bar(state['invested'], threshold)} "
            f"**{state['invested']:,}/{threshold:,}** {get_cash_emoji()}\n"
            f"До следующего уровня: **{remaining:,}** {get_cash_emoji()}"
        )

    embed = discord.Embed(
        title=f"{EMOJI_SHOP} {definition['name']}",
        description=(
            "Инвестиции всех игроков развивают снабжение сервера и открывают "
            "новые товары в каталоге. Вложения возврату не подлежат."
            + (f"\n\n{notice}" if notice else "")
        ),
        color=discord.Color.from_rgb(139, 109, 68),
    )
    embed.add_field(name=f"{EMOJI_LEVEL} Уровень компании: {state['level']}/4", value=progress, inline=False)
    embed.add_field(
        name=f"{EMOJI_TROPHY} Ваши инвестиции",
        value=f"**{own:,}** {get_cash_emoji()} · скидка на товары за наличные: **{discount}%**",
        inline=False,
    )
    leaders = sorted(state["investors"].items(), key=lambda pair: pair[1], reverse=True)[:5]
    leaderboard = "\n".join(
        f"{index}. <@{investor_id}> — **{amount:,}** {get_cash_emoji()}"
        for index, (investor_id, amount) in enumerate(leaders, start=1)
    ) or "*Инвесторов пока нет.*"
    embed.add_field(name=f"{EMOJI_MEMBERS} Крупнейшие инвесторы", value=leaderboard, inline=False)
    embed.set_footer(text="Скидки инвестора и магазина суммируются, но не превышают 25%.")
    return embed


def build_catalog_messages(category_key, account, guild_id, user_id):
    """Создать embeds и файлы для страницы категории каталога."""
    normalize_weapon_state(account, CATALOG_ITEMS)
    cat = CATALOG_CATEGORIES[category_key]
    items = get_category_items(category_key)

    guild_data = economy_data.current()
    company_state = get_company_state(guild_data, WHEELER_RAWSON)

    cat_emoji = get_catalog_category_emoji(category_key)
    title_emoji = get_catalog_title_emoji()

    main_embed = discord.Embed(
        title=f"{title_emoji} Каталог — {cat_emoji} {cat['name']}",
        description=(
            f"{cat['description']}\n\n"
            f"{EMOJI_SHOP} Wheeler, Rawson & Co. · уровень **{company_state['level']}/4** · "
            "`/investments` для просмотра прогресса"
        ),
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
            price, discount_percent = get_catalog_price(
                item_key, item_data, guild_data, user_id
            )
            unlocked = is_item_unlocked(item_data, guild_data)

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
            if not unlocked:
                required_level = item_data.get("required_company_level", 1)
                item_description = (
                    f"{get_lock_emoji()} **Требуется {required_level}-й уровень Wheeler, Rawson & Co.**\n"
                    f"{item_description}"
                )
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
                    title=f"{get_lock_emoji() if not unlocked else item_emoji} {item_data['name']}{status}",
                    description=f"{item_description}\nЦена: {price_text}",
                    color=discord.Color.from_rgb(139, 109, 68),
                )
                filename = item_data["image"].split("/")[-1]
                files.append(discord.File(item_data["image"], filename=filename))
                item_embed.set_thumbnail(url=f"attachment://{filename}")
                embeds.append(item_embed)
            else:
                main_embed.add_field(
                    name=f"{get_lock_emoji() if not unlocked else item_emoji} {item_data['name']}{status}",
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
    def __init__(self, item_key, item_data, price, already_owned, unlocked, discount_percent=0):
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
            label=("Уже куплено" if already_owned else label) if unlocked else f"Закрыто до уровня {item_data.get('required_company_level', 1)}",
            style=discord.ButtonStyle.secondary if already_owned or not unlocked else discord.ButtonStyle.success,
            custom_id=f"catalog_buy_{item_key}",
            emoji=item_emoji,
            disabled=already_owned or not unlocked,
        )

    async def callback(self, interaction: discord.Interaction):
        async with economy_lock:
            account = get_account(interaction.user.id)
            inventory = account.setdefault("inventory", {})
            normalize_weapon_state(account, CATALOG_ITEMS)
            guild_data = economy_data.current()

            if not is_item_unlocked(self.item_data, guild_data):
                required_level = self.item_data.get("required_company_level", 1)
                await interaction.response.send_message(
                    f"Товар пока недоступен. Требуется **{required_level}-й уровень Wheeler, Rawson & Co.**",
                    ephemeral=True,
                )
                return

            # Recalculate the price inside the lock: an old catalog message must
            # not retain a stale company or administrator discount.
            live_price, _ = get_catalog_price(
                self.item_key, self.item_data, guild_data, interaction.user.id
            )
            purchase_quantity = self.item_data.get("quantity", 1)

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
                        f"Сначала купите оружие класса «{WEAPON_CLASS_NAMES[class_key]}».",
                        ephemeral=True,
                    )
                    return
                free_space = max(0, capacity - current)
                if free_space <= 0:
                    await interaction.response.send_message(
                        f"Боезапас этого класса уже полный: **{current}/{capacity}**.",
                        ephemeral=True,
                    )
                    return
                purchase_quantity = min(quantity, free_space)
                if purchase_quantity < quantity:
                    live_price = max(1, math.ceil(live_price * purchase_quantity / quantity))

            if account.get(self.item_data["currency"], 0.0) < live_price:
                currency_emoji = get_gold_emoji() if self.item_data["currency"] == "gold" else get_cash_emoji()
                await interaction.response.send_message(
                    f"Недостаточно средств. Нужно {live_price} {currency_emoji}.",
                    ephemeral=True,
                )
                return

            account[self.item_data["currency"]] -= live_price
            if self.item_data["type"] == "unique":
                inventory[self.item_key] = 1
                if weapon_class(self.item_key, self.item_data):
                    account["weapon_condition"][self.item_key] = 100.0
                    equip_weapon(account, self.item_key, CATALOG_ITEMS)
            elif self.item_data["type"] == "ammo":
                class_ammo = account["ammo"][self.item_data["ammo_class"]]
                ammo_type = self.item_data["ammo_type"]
                class_ammo[ammo_type] += purchase_quantity
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
                    f"{success_emoji} Куплено **{purchase_quantity} шт.** — "
                    f"**{self.item_data['name']}** за {live_price} {emoji}.\n"
                    f"Боезапас: **{stock}/{capacity}**."
                )
            elif self.item_data["type"] == "moonshine_ingredient":
                result = (
                    f"{success_emoji} Куплено: **{self.item_data['name']} x{self.item_data['quantity']}** "
                    f"за {live_price} {emoji}.\n"
                    f"На складе самогонщика: **{stored_ingredient} шт.**"
                )
            else:
                result = f"{success_emoji} Вы успешно купили **{self.item_data['name']}** за {live_price} {emoji}!"
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
        embeds, files = build_catalog_messages(selected, account, interaction.guild_id, interaction.user.id)
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

        for item_key, item_data in items.items():
            price, discount_percent = get_catalog_price(
                item_key, item_data, guild_data, member.id
            )
            unlocked = is_item_unlocked(item_data, guild_data)

            inventory = account.get("inventory", {})
            already_owned = (
                item_data["type"] == "unique" and inventory.get(item_key, 0) > 0
            )

            self.add_item(
                CatalogBuyButton(
                    item_key, item_data, price, already_owned, unlocked, discount_percent
                )
            )

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "Это не ваш каталог!", ephemeral=True
            )
            return False
        return True


def build_weapons_embed(account):
    normalize_weapon_state(account, CATALOG_ITEMS)
    loadout = account["weapon_loadout"]

    def weapon_line(key):
        item = CATALOG_ITEMS[key]
        condition = account["weapon_condition"].get(key, 100.0)
        effectiveness = round(condition_stat_multiplier(condition) * 100)
        return (
            f"{weapon_emoji(key)} **{item['name']}** — состояние {condition:g}% · "
            f"характеристики {effectiveness}%"
        )

    sidearms = [weapon_line(key) for key in loadout["sidearms"]]
    longarms = [weapon_line(key) for key in loadout["longarms"]]
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
    embed = discord.Embed(
        title=f"{EMOJI_WEAPON} Оружие и боезапас",
        description="Выберите оружие ниже, чтобы взять его, убрать или почистить.",
        color=discord.Color.from_rgb(139, 109, 68),
    )
    embed.add_field(
        name="Короткоствольное · максимум 2 одного класса",
        value="\n".join(sidearms) or "*Слоты пусты*",
        inline=False,
    )
    embed.add_field(
        name="Крупное оружие · максимум 2",
        value="\n".join(longarms) or "*Слоты пусты*",
        inline=False,
    )
    embed.add_field(name="Боезапас", value="\n".join(ammo_lines), inline=False)
    embed.add_field(name="Уход", value=f"{GUN_OIL_EMOJI} Оружейное масло: **{oil} шт.**", inline=False)
    return embed


class WeaponSelect(discord.ui.Select):
    def __init__(self, account, selected=None):
        owned = owned_weapon_keys(account, CATALOG_ITEMS)
        options = [
            discord.SelectOption(
                label=CATALOG_ITEMS[key]["name"][:100],
                value=key,
                emoji=weapon_emoji(key),
                default=key == selected,
            )
            for key in owned[:25]
        ]
        super().__init__(
            placeholder="Выберите купленное оружие..." if options else "У вас пока нет оружия",
            options=options or [discord.SelectOption(label="Нет купленного оружия", value="none")],
            disabled=not options,
            row=0,
        )

    async def callback(self, interaction):
        self.view.selected_weapon = self.values[0]
        await interaction.response.defer()
        await self.view.refresh(interaction)


class AmmoClassSelect(discord.ui.Select):
    def __init__(self, selected="revolver"):
        super().__init__(
            placeholder="Класс оружия для патронов",
            options=[
                discord.SelectOption(label=name.capitalize(), value=key, default=key == selected)
                for key, name in WEAPON_CLASS_NAMES.items()
            ],
            row=2,
        )

    async def callback(self, interaction):
        self.view.ammo_class = self.values[0]
        await interaction.response.defer()
        await self.view.refresh(interaction)


class AmmoTypeSelect(discord.ui.Select):
    def __init__(self, selected="normal"):
        super().__init__(
            placeholder="Тип патронов",
            options=[
                discord.SelectOption(label=name, value=key, emoji=AMMO_EMOJIS[key], default=key == selected)
                for key, name in AMMO_TYPE_NAMES.items()
            ],
            row=3,
        )

    async def callback(self, interaction):
        self.view.ammo_type = self.values[0]
        await interaction.response.defer()
        await self.view.refresh(interaction)


class WeaponManagementView(discord.ui.View):
    def __init__(self, guild_id, member, account):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.member = member
        owned = owned_weapon_keys(account, CATALOG_ITEMS)
        equipped = set(
            account.get("weapon_loadout", {}).get("sidearms", [])
            + account.get("weapon_loadout", {}).get("longarms", [])
        )
        self.selected_weapon = next((key for key in owned if key not in equipped), None)
        if self.selected_weapon is None and owned:
            self.selected_weapon = owned[0]
        self.ammo_class = "revolver"
        self.ammo_type = account.get("selected_ammo", {}).get(self.ammo_class, "normal")
        self.rebuild(account)

    def rebuild(self, account):
        self.clear_items()
        self.add_item(WeaponSelect(account, self.selected_weapon))
        equipped = self.selected_weapon in (
            account["weapon_loadout"]["sidearms"] + account["weapon_loadout"]["longarms"]
        )
        self.take_button.disabled = not self.selected_weapon or equipped
        self.remove_button.disabled = not self.selected_weapon or not equipped
        self.clean_button.disabled = not self.selected_weapon
        self.add_item(self.take_button)
        self.add_item(self.remove_button)
        self.add_item(self.clean_button)
        self.add_item(AmmoClassSelect(self.ammo_class))
        self.add_item(AmmoTypeSelect(self.ammo_type))
        self.add_item(self.load_ammo_button)

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("Это не ваше оружейное меню!", ephemeral=True)
            return False
        return True

    async def on_error(self, interaction, error, item):
        logging.error(
            "Weapon menu failed for user=%s guild=%s item=%s",
            getattr(interaction.user, "id", None),
            interaction.guild_id,
            getattr(item, "custom_id", type(item).__name__),
            exc_info=(type(error), error, error.__traceback__),
        )
        message = f"{EMOJI_WARNING} Не удалось обновить оружие. Попробуйте снова открыть `/balance`."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def refresh(self, interaction, notice=None):
        async with economy_lock:
            account = get_account(interaction.user.id)
            normalize_weapon_state(account, CATALOG_ITEMS)
            self.rebuild(account)
            save_economy()
            embed = build_weapons_embed(account)
        if notice:
            embed.description = notice
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, attachments=[], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    @discord.ui.button(label="Взять", emoji=EMOJI_SUCCESS, style=discord.ButtonStyle.success, row=1)
    async def take_button(self, interaction, button):
        await interaction.response.defer()
        async with economy_lock:
            account = get_account(interaction.user.id)
            ok, message = equip_weapon(
                account, self.selected_weapon, CATALOG_ITEMS, replace=True
            )
            if ok:
                save_economy()
                equipped = (
                    account["weapon_loadout"]["sidearms"]
                    + account["weapon_loadout"]["longarms"]
                )
                if self.selected_weapon not in equipped:
                    ok = False
                    message = "Оружие не сохранилось в активном снаряжении."
        await self.refresh(interaction, f"{EMOJI_SUCCESS if ok else EMOJI_WARNING} {message}")

    @discord.ui.button(label="Убрать", emoji="➖", style=discord.ButtonStyle.secondary, row=1)
    async def remove_button(self, interaction, button):
        await interaction.response.defer()
        async with economy_lock:
            account = get_account(interaction.user.id)
            removed = unequip_weapon(account, self.selected_weapon)
            if removed:
                save_economy()
        await self.refresh(interaction, f"{EMOJI_SUCCESS} Оружие убрано." if removed else f"{EMOJI_WARNING} Оружие уже не выбрано.")

    @discord.ui.button(label="Почистить", emoji=GUN_OIL_EMOJI, style=discord.ButtonStyle.primary, row=1)
    async def clean_button(self, interaction, button):
        await interaction.response.defer()
        async with economy_lock:
            account = get_account(interaction.user.id)
            inventory = account.setdefault("inventory", {})
            condition = account["weapon_condition"].get(self.selected_weapon, 100.0)
            if inventory.get("gun_oil", 0) <= 0:
                message = f"{EMOJI_WARNING} Нет оружейного масла. Купите его в `/catalog`."
            elif condition >= 100.0:
                message = f"{EMOJI_WARNING} Оружие уже в идеальном состоянии."
            else:
                inventory["gun_oil"] -= 1
                account["weapon_condition"][self.selected_weapon] = 100.0
                save_economy()
                message = f"{GUN_OIL_EMOJI} Оружие очищено: {condition:g}% → **100%**."
        await self.refresh(interaction, message)

    @discord.ui.button(label="Зарядить выбранные", emoji=AMMO_EMOJIS["normal"], style=discord.ButtonStyle.primary, row=4)
    async def load_ammo_button(self, interaction, button):
        await interaction.response.defer()
        async with economy_lock:
            account = get_account(interaction.user.id)
            stock = account["ammo"][self.ammo_class][self.ammo_type]
            if stock <= 0:
                message = f"{EMOJI_WARNING} Таких патронов для класса «{WEAPON_CLASS_NAMES[self.ammo_class]}» нет."
            else:
                account["selected_ammo"][self.ammo_class] = self.ammo_type
                save_economy()
                message = f"{AMMO_EMOJIS[self.ammo_type]} Заряжены **{AMMO_TYPE_NAMES[self.ammo_type]}** патроны · {stock} шт."
        await self.refresh(interaction, message)


class BalanceWeaponButtonView(discord.ui.View):
    def __init__(self, guild_id, member):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.member = member

    @discord.ui.button(label="Оружие", emoji=DEFAULT_BALANCE_WEAPON_EMOJI, style=discord.ButtonStyle.primary)
    async def weapons_button(self, interaction, button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("Это не ваш баланс!", ephemeral=True)
            return
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                normalize_weapon_state(account, CATALOG_ITEMS)
                save_economy()
                embed = build_weapons_embed(account)
                view = WeaponManagementView(interaction.guild_id, interaction.user, account)
            await interaction.response.edit_message(embed=embed, attachments=[], view=view)
        finally:
            reset_economy_guild_id(token)

    @discord.ui.button(
        label="Обмен золота",
        emoji=get_gold_emoji(),
        style=discord.ButtonStyle.success,
    )
    async def gold_exchange_button(self, interaction, button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("Это не ваш баланс!", ephemeral=True)
            return
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                rate = update_gold_rate()
                account = get_account(interaction.user.id)
                save_economy()
                embed = build_gold_exchange_embed(account, rate)
            await interaction.response.edit_message(
                embed=embed,
                view=GoldExchangeView(interaction.guild_id, interaction.user),
            )
        finally:
            reset_economy_guild_id(token)


def build_gold_exchange_embed(account, rate, notice=None):
    description = (
        f"Курс: **1 {get_gold_emoji()} = {format_money(rate)}**\n\n"
        f"{get_cash_emoji()} Наличные: **{format_money_plain(account['cash'])}**\n"
        f"{get_gold_emoji()} Золото: **{account['gold']:g}**"
    )
    if notice:
        description += f"\n\n{notice}"
    return discord.Embed(
        title=f"{get_gold_emoji()} Обмен золота",
        description=description,
        color=discord.Color.dark_gold(),
    )


class GoldExchangeModal(discord.ui.Modal):
    amount = discord.ui.TextInput(
        label="Количество золота",
        placeholder="Например: 1 или 0,5",
        min_length=1,
        max_length=20,
    )

    def __init__(self, guild_id, member, action):
        verb = "Купить" if action == "buy" else "Продать"
        super().__init__(title=f"{verb} золото")
        self.guild_id = guild_id
        self.member = member
        self.action = action

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("Это не ваше меню!", ephemeral=True)
            return
        try:
            amount = float(str(self.amount.value).strip().replace(",", "."))
        except ValueError:
            amount = 0
        if not math.isfinite(amount) or amount <= 0:
            await interaction.response.send_message(
                f"{EMOJI_WARNING} Введите положительное количество золота.",
                ephemeral=True,
            )
            return

        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                rate = update_gold_rate()
                account = get_account(interaction.user.id)
                if self.action == "buy":
                    total = amount * rate
                    if not math.isfinite(total) or account["cash"] + 0.0001 < total:
                        notice = (
                            f"{EMOJI_WARNING} Недостаточно наличных: нужно "
                            f"**{format_money(total)}**."
                        )
                    else:
                        account["cash"] -= total
                        account["gold"] += amount
                        notice = (
                            f"{EMOJI_SUCCESS} Куплено **{format_gold(amount)}** за "
                            f"**{format_money(total)}**."
                        )
                elif account["gold"] + 0.0001 < amount:
                    notice = f"{EMOJI_WARNING} На балансе недостаточно золота."
                else:
                    total = amount * rate
                    account["gold"] = max(0.0, account["gold"] - amount)
                    account["cash"] += total
                    notice = (
                        f"{EMOJI_SUCCESS} Продано **{format_gold(amount)}** за "
                        f"**{format_money(total)}**."
                    )
                save_economy()
                embed = build_gold_exchange_embed(account, rate, notice)
            await interaction.response.edit_message(
                embed=embed,
                view=GoldExchangeView(self.guild_id, self.member),
            )
        finally:
            reset_economy_guild_id(token)


class GoldExchangeView(discord.ui.View):
    def __init__(self, guild_id, member):
        super().__init__(timeout=600)
        self.guild_id = guild_id
        self.member = member

    async def interaction_check(self, interaction):
        if interaction.user.id == self.member.id:
            return True
        await interaction.response.send_message("Это не ваше меню!", ephemeral=True)
        return False

    @discord.ui.button(label="Купить", emoji=EMOJI_ADD, style=discord.ButtonStyle.success)
    async def buy_button(self, interaction, button):
        await interaction.response.send_modal(
            GoldExchangeModal(self.guild_id, self.member, "buy")
        )

    @discord.ui.button(label="Продать", emoji=EMOJI_EDIT, style=discord.ButtonStyle.primary)
    async def sell_button(self, interaction, button):
        await interaction.response.send_modal(
            GoldExchangeModal(self.guild_id, self.member, "sell")
        )

    @discord.ui.button(label="Вернуться к балансу", emoji=EMOJI_SEARCH, style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction, button):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                rate = update_gold_rate()
                account = get_account(interaction.user.id)
                embed = build_balance_embed(interaction.guild, interaction.user, account, rate)
            await interaction.response.edit_message(
                embed=embed,
                view=BalanceWeaponButtonView(self.guild_id, self.member),
            )
        finally:
            reset_economy_guild_id(token)


async def send_company_level_up_announcement(interaction, level_up):
    guild = interaction.guild
    if guild is None:
        return

    guild_data = economy_data.current()
    channel_id = guild_data.get("news_channel_id")
    if not channel_id:
        return

    try:
        channel = guild.get_channel(int(channel_id))
    except (TypeError, ValueError):
        channel = None
    if channel is None:
        logging.warning(
            "Company level-up news channel %r was not found in guild %s",
            channel_id,
            guild.id,
        )
        return

    company_name = COMPANY_DEFINITIONS[WHEELER_RAWSON]["name"]
    embed = discord.Embed(
        title=f"{EMOJI_TROPHY} Компания вышла на новый уровень!",
        description=(
            f"Благодаря инвестиции {interaction.user.mention} компания "
            f"**{company_name}** достигла **{level_up['new_level']}-го уровня**.\n"
            "В каталоге открыты новые товары."
        ),
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(
        name="Рост компании",
        value=f"**{level_up['old_level']} → {level_up['new_level']} уровень**",
        inline=True,
    )
    embed.add_field(
        name="Новая инвестиция",
        value=f"**{level_up['amount']:,}** {get_cash_emoji()}",
        inline=True,
    )
    embed.add_field(
        name="Общий фонд",
        value=f"**{level_up['invested']:,}** {get_cash_emoji()}",
        inline=True,
    )

    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as error:
        logging.warning(
            "Failed to send company level-up announcement to channel %s: %s",
            channel.id,
            error,
        )


class InvestmentAmountModal(discord.ui.Modal, title="Инвестиция в компанию"):
    amount = discord.ui.TextInput(
        label="Сумма наличными",
        placeholder="Например: 500",
        min_length=1,
        max_length=12,
    )

    def __init__(self, guild_id, member):
        super().__init__()
        self.guild_id = guild_id
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("Это не ваше меню!", ephemeral=True)
            return
        try:
            amount = int(str(self.amount.value).strip().replace(" ", ""))
        except ValueError:
            amount = 0
        if amount <= 0:
            await interaction.response.send_message(
                f"{EMOJI_WARNING} Введите положительную целую сумму.", ephemeral=True
            )
            return

        token = set_economy_guild_id(interaction.guild_id)
        try:
            level_up = None
            async with economy_lock:
                account = get_account(interaction.user.id)
                guild_data = economy_data.current()
                company_state = get_company_state(guild_data, WHEELER_RAWSON)
                if account.get("cash", 0) < amount:
                    notice = (
                        f"{EMOJI_WARNING} Недостаточно наличных. Нужно "
                        f"**{amount:,}** {get_cash_emoji()}."
                    )
                else:
                    account["cash"] -= amount
                    old_level, new_level = add_investment(
                        company_state, WHEELER_RAWSON, interaction.user.id, amount
                    )
                    save_economy()
                    notice = (
                        f"{EMOJI_SUCCESS} Вложено **{amount:,}** {get_cash_emoji()}."
                    )
                    if new_level > old_level:
                        level_up = {
                            "old_level": old_level,
                            "new_level": new_level,
                            "invested": company_state["invested"],
                            "amount": amount,
                        }
                        notice += (
                            f"\n{EMOJI_TROPHY} Компания достигла **{new_level}-го уровня** — "
                            "открыты новые товары."
                        )
                embed = build_company_embed(guild_data, interaction.user.id, notice)
            await interaction.response.edit_message(
                embed=embed,
                view=InvestmentsView(self.guild_id, self.member),
            )
            if level_up:
                await send_company_level_up_announcement(interaction, level_up)
        finally:
            reset_economy_guild_id(token)


class InvestmentsView(discord.ui.View):
    def __init__(self, guild_id, member):
        super().__init__(timeout=600)
        self.guild_id = guild_id
        self.member = member

    async def interaction_check(self, interaction):
        if interaction.user.id == self.member.id:
            return True
        await interaction.response.send_message("Это не ваше меню!", ephemeral=True)
        return False

    @discord.ui.button(label="Инвестировать", emoji=EMOJI_ADD, style=discord.ButtonStyle.success)
    async def invest_button(self, interaction, button):
        await interaction.response.send_modal(
            InvestmentAmountModal(self.guild_id, self.member)
        )

    @discord.ui.button(label="Обновить", emoji=EMOJI_LEVEL, style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction, button):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                embed = build_company_embed(economy_data.current(), interaction.user.id)
            await interaction.response.edit_message(embed=embed, view=self)
        finally:
            reset_economy_guild_id(token)


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

            embeds, files = build_catalog_messages(
                current_category, account, interaction.guild_id, interaction.user.id
            )
            view = CatalogView(interaction.guild_id, interaction.user, account, current_category)

            await interaction.response.send_message(embeds=embeds, files=files, view=view, ephemeral=True)
        finally:
            reset_economy_guild_id(token)

    @app_commands.command(name="investments", description="Открыть компании и управление инвестициями")
    async def investments_cmd(self, interaction: discord.Interaction):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            async with economy_lock:
                embed = build_company_embed(economy_data.current(), interaction.user.id)
            await interaction.response.send_message(
                embed=embed,
                view=InvestmentsView(interaction.guild_id, interaction.user),
                ephemeral=True,
            )
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
                title=f"{EMOJI_WEAPON} Оружие и боезапас",
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
            embed.set_footer(text="Управление оружием: /balance → кнопка «Оружие»")
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
                f"{EMOJI_SUCCESS if ok else EMOJI_WARNING} **{name}**: {message}", ephemeral=True
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
            message = f"{EMOJI_SUCCESS} **{name}** убрано." if removed else f"{EMOJI_WARNING} Это оружие сейчас не взято с собой."
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
                    message = f"{EMOJI_WARNING} Это оружие не куплено."
                elif inventory.get("gun_oil", 0) <= 0:
                    message = f"{EMOJI_WARNING} Нет оружейного масла. Купите его в разделе снаряжения `/catalog`."
                elif account["weapon_condition"].get(weapon, 100.0) >= 100.0:
                    message = f"{EMOJI_WARNING} Оружие уже находится в идеальном состоянии."
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
                        f"{EMOJI_WARNING} Нет патронов типа **{AMMO_TYPE_NAMES[type_key]}** "
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
    # Оружейные действия доступны из кнопки «Оружие» в /balance, поэтому не
    # засоряют список slash-команд отдельными пунктами.
    for command_name in ("weapons", "weapon-equip", "weapon-unequip", "gun-oil", "ammo-select"):
        bot.tree.remove_command(command_name)
