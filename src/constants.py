"""
src/constants.py
Все константы бота: пути к файлам, игровые параметры,
роли, сценарии работы, строки UI Марселя и т.д.
"""

import discord
from emoji_config import (
    EMOJI_ROLE_BOUNTY_HUNTER, EMOJI_ROLE_TRADER, EMOJI_ROLE_MOONSHINER,
    EMOJI_ROLE_NATURALIST, EMOJI_ROLE_MINER, EMOJI_ROLE_COLLECTOR,
)

# ──────────────────────────────────────────────────────────────
#  ФАЙЛЫ / ПУТИ
# ──────────────────────────────────────────────────────────────

CHANNELS_FILE                 = "data/channels.txt"
ECONOMY_FILE                  = "data/economy.json"
ENV_FILE                      = ".env"
ECONOMY_GLOBAL_KEY            = "global"

TREASURE_BANNER_FILE          = "assets/images/goldenmap.png"
ROLE_IMAGE_FILE               = "assets/images/roles.png"
ROLE_IMAGE_ATTACHMENT_NAME    = "roles.png"
BALANCE_IMAGE_FILE            = "assets/images/balance.png"
BALANCE_IMAGE_ATTACHMENT_NAME = "balance.png"

# ──────────────────────────────────────────────────────────────
#  ЭКОНОМИКА / КУРС ЗОЛОТА
# ──────────────────────────────────────────────────────────────

START_GOLD_RATE   = 543.45
MIN_GOLD_RATE     = 50.0

# ──────────────────────────────────────────────────────────────
#  КУЛДАУНЫ
# ──────────────────────────────────────────────────────────────

WORK_COOLDOWN_SECONDS   = 60 * 60
DEALER_COOLDOWN_SECONDS = 60 * 60

# ──────────────────────────────────────────────────────────────
#  ТОРГОВЕЦ (DEALER)
# ──────────────────────────────────────────────────────────────

DEALER_MIN_FILL             = 10
DEALER_MAX_FILL             = 35
DEALER_DELIVERY_MIN_REWARD  = 500
DEALER_DELIVERY_MAX_REWARD  = 625
DEALER_ROLE_KEY             = "trader"

# ──────────────────────────────────────────────────────────────
#  РОЛИ
# ──────────────────────────────────────────────────────────────

ROLE_BASE_PRICE    = 20.0
ROLE_DISCOUNT_DAYS = 7

# Суффикс из невидимых пробелов (Hangul Filler U+3164) для выравнивания ролей
HANGUL_FILLER            = "\u3164"
ROLE_DISPLAY_SUFFIX      = HANGUL_FILLER * 5
WILDWEST_HEADER_ROLE_NAME  = "Роли WildWest:" + ROLE_DISPLAY_SUFFIX
WILDWEST_HEADER_ROLE_COLOR = discord.Color(0x393a41)
ROLE_DISPLAY_COLOR         = discord.Color(0xefe58d)

ROLE_DEFINITIONS = [
    {
        "key":         "bounty_hunter",
        "name":        "Охотник за головами",
        "aliases":     [],
        "emoji":       EMOJI_ROLE_BOUNTY_HUNTER,
        "available":   True,
        "description": (
            "Выслеживает опасные цели, берёт контракты на поимку и получает награды "
            "за точность, выдержку и холодную голову."
        ),
    },
    {
        "key":         "trader",
        "name":        "Торговец",
        "aliases":     [],
        "emoji":       EMOJI_ROLE_TRADER,
        "available":   True,
        "description": (
            "Развивает собственное дело, наполняет торговую повозку товарами и готовит "
            "поставки для будущей прибыли."
        ),
    },
    {
        "key":         "moonshiner",
        "name":        "Самогонщик",
        "aliases":     [],
        "emoji":       EMOJI_ROLE_MOONSHINER,
        "available":   True,
        "description": (
            "Мастер тайного производства: варит крепкий товар, держит сеть поставок "
            "и знает цену хорошей репутации."
        ),
    },
    {
        "key":         "naturalist",
        "name":        "Натуралист",
        "aliases":     [],
        "emoji":       EMOJI_ROLE_NATURALIST,
        "available":   True,
        "description": (
            "Изучает природу, выслеживает редких животных и собирает знания там, "
            "где другие видят только дикую местность."
        ),
    },
    {
        "key":         "miner",
        "name":        "Шахтёр",
        "aliases":     [],
        "emoji":       EMOJI_ROLE_MINER,
        "available":   True,
        "description": (
            "Копает породу, добывает руду и драгоценные камни, переплавляет слитки "
            "и создаёт украшения у ювелира."
        ),
    },
    {
        "key":         "collector",
        "name":        "Коллекционер",
        "aliases":     [],
        "emoji":       EMOJI_ROLE_COLLECTOR,
        "available":   False,
        "description": (
            "Ищет редкие находки, собирает ценные наборы и превращает любопытство "
            "в аккуратную витрину трофеев."
        ),
    },
]

DEFAULT_ROLE_EMOJIS = {
    rd["key"]: rd["emoji"]
    for rd in ROLE_DEFINITIONS
}

# ──────────────────────────────────────────────────────────────
#  СООБЩЕНИЯ ПО УМОЛЧАНИЮ
# ──────────────────────────────────────────────────────────────

DEFAULT_CUSTOM_MESSAGES = {
    "roles_description": "Выберите профессию и купите доступную роль за золото.",
    "roles_footer":      "Доступные роли покупаются зелёными кнопками ниже.",
    "work_success":      "{mention}, {scenario} и получили **{reward}**.",
    "role_required":     "Команда доступна только роли **{role}**. Купить её можно через `/roles`.",
    "reset_prompt":      "Для полного сброса сервера введите: Я знаю что я делаю или I know what I'm doing.",
}

RESET_CONFIRMATION_PHRASES = ("Я знаю что я делаю", "I know what I'm doing")

# ──────────────────────────────────────────────────────────────
#  КАРТЫ СОКРОВИЩ
# ──────────────────────────────────────────────────────────────

TREASURE_MAPS_PER_DROP  = 1
EXCAVATION_REWARD_CHANCE = 0.15

# ──────────────────────────────────────────────────────────────
#  РАБОТА (/work)
# ──────────────────────────────────────────────────────────────

WORK_SCENARIOS = [
    "вы помогли фермеру перегнать скот",
    "вы разгрузили ящики на станции",
    "вы сопроводили дилижанс до соседнего города",
    "вы починили изгородь у ранчо",
    "вы нашли подработку у конюха",
    "вы доставили посылку старому знакомому",
]

# ──────────────────────────────────────────────────────────────
#  КАЗИНО / КАРТЫ
# ──────────────────────────────────────────────────────────────

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

# ──────────────────────────────────────────────────────────────
#  САМОГОНЩИК (UI-строки Марселя)
# ──────────────────────────────────────────────────────────────

MARCEL_GREETINGS = [
    "Добрый день, босс. Какой самогон будем готовить на этот раз?",
    "Аппараты начищены и ждут. Что варим сегодня?",
    "Всегда готов к работе, босс. Жду ваших указаний.",
    "Отличный день для новой партии, не так ли?",
    "Босс, ингредиенты на месте. Запускаем котёл?",
    "Тише едешь — крепче градус. Что сегодня на повестке?"
]

MARCEL_BUSY = [
    "**Марсель:** Один котёл уже занят. Дождёмся готовности партии.",
    "**Марсель:** Котёл пыхтит вовсю, босс. Придётся подождать.",
    "**Марсель:** Места больше нет, перегонка уже идёт.",
]

MARCEL_MASH_START = [
    "Ставлю партию, босс:",
    "Запускаю котёл. Будет готово в лучшем виде:",
    "Процесс пошёл. Отличный выбор для основы:",
    "Зажёг огонь под котлом, босс. Начинаем варить:"
]

MARCEL_SPECIAL_SUCCESS = [
    "Хороший выбор, босс. Это придаст напитку особый аромат.",
    "Отличная идея. Клиенты оторвут с руками!",
    "Добавил всё по рецепту. Запах уже изумительный.",
    "Этот рецепт — настоящая бомба, босс. Отличный выбор."
]

MARCEL_EMPTY_WAGON = [
    "**Марсель:** Повозка пока пустая, босс. Сначала поставим партию.",
    "**Марсель:** Везти нечего, бутылки ещё не наполнились.",
    "**Марсель:** Босс, лошади запряжены, но самогона нет."
]

MARCEL_NOT_READY = [
    "**Марсель:** Самогон ещё доходит. Осталось **{duration}**.",
    "**Марсель:** Ещё немного, босс. Придётся подождать **{duration}**.",
    "**Марсель:** Капли падают медленно. Ждём ещё **{duration}**."
]

# ──────────────────────────────────────────────────────────────
#  UI / EMBED
# ──────────────────────────────────────────────────────────────

BOT_EMBED_COLOR = discord.Color.gold()

# ──────────────────────────────────────────────────────────────
#  АДМИНИСТРАТИВНЫЕ КОМАНДЫ (имена)
# ──────────────────────────────────────────────────────────────

ADMIN_COMMAND_NAMES = {
    "reset-all", "delete-role", "restart-roles", "check",
    "give-money", "remove-money", "set-money",
    "give-gold", "remove-gold", "set-gold",
    "give-map", "set-rate",
    "treasure-channel", "treasure-event",
    "set-icon-roles", "set-discounts-roles", "clear-discounts-roles",
    "fill-dealer",
    "give-moonshine-ingredient", "remove-moonshine-ingredient",
    "set-moonshine-upgrade", "set-moonshine-skill",
    "finish-moonshine", "reset-moonshine",
    "set-emoji", "emoji-list", "set-message",
    "reset-work", "reset-dealer",
}

ALL_TARGET_ALIASES = {"all", "@everyone", "everyone", "все", "всем", "всех"}

# ──────────────────────────────────────────────────────────────
#  EMOJI-ТАРГЕТЫ для /set-emoji
# ──────────────────────────────────────────────────────────────

EMOJI_TARGETS = [
    ("Деньги", "cash"),
    ("Золото", "gold"),
    ("Карта сокровищ", "map"),
    ("Статистика", "stats"),
    ("Самогон: 1 звезда", "moonshine_star_1"),
    ("Самогон: 2 звезды", "moonshine_star_2"),
    ("Самогон: 3 звезды", "moonshine_star_3"),
    ("Особый самогон", "moonshine_special"),
    ("Самогон: Конденсатор", "moonshine_condenser"),
    ("Самогон: Медный дистиллятор", "moonshine_distiller"),
    ("Кнопка: бражка", "moonshine_button_mash"),
    ("Кнопка: особые ингредиенты", "moonshine_button_special"),
    ("Кнопка: улучшения", "moonshine_button_upgrades"),
    ("Кнопка: доставка", "moonshine_button_delivery"),
    ("Кнопка: обновить самогон", "moonshine_button_refresh"),
    ("Интерфейс: производство", "moonshine_ui_prod"),
    ("Интерфейс: уровень аппарата", "moonshine_ui_lvl"),
    ("Интерфейс: доступ", "moonshine_ui_access"),
    ("Интерфейс: бутылки", "moonshine_ui_bottles"),
    ("Интерфейс: повозка", "moonshine_ui_wagon"),
    ("Интерфейс: варка", "moonshine_ui_brewing"),
    ("Интерфейс: котёл", "moonshine_ui_kettle"),
    ("Интерфейс: оборудование", "moonshine_ui_equip"),
    ("Интерфейс: навык самогонщика", "moonshine_ui_skill"),
    ("Интерфейс: склад полон", "moonshine_ui_stor_full"),
    ("Интерфейс: склад пуст", "moonshine_ui_stor_empty"),
    ("Интерфейс: финансы", "moonshine_ui_finance"),
    ("Баланс: финансы", "balance_ui_finance"),
    ("Баланс: роли", "balance_ui_roles"),
    ("Баланс: экономика", "balance_ui_economy"),
    ("Баланс: фракция", "balance_ui_gang"),
    ("Натуралист: взять образец", "naturalist_button_sample"),
    ("Натуралист: сдать образцы", "naturalist_button_sell"),
    ("Натуралист: справочник", "naturalist_button_collection"),
    ("Натуралист: легендарка", "naturalist_button_legendary"),
    ("Натуралист: магазин", "naturalist_button_shop"),
    ("Натуралист: обновить", "naturalist_button_refresh"),
    ("Охотник: лёгкий контракт", "bounty_button_easy"),
    ("Охотник: опасный контракт", "bounty_button_medium"),
    ("Охотник: легендарная цель", "bounty_button_hard"),
    ("Охотник: засада", "bounty_button_ambush"),
    ("Охотник: погоня", "bounty_button_chase"),
    ("Охотник: переговоры", "bounty_button_negotiate"),
    ("Роль: охотник за головами", "role_icon_bounty_hunter"),
    ("Роль: торговец", "role_icon_trader"),
    ("Роль: самогонщик", "role_icon_moonshiner"),
    ("Роль: натуралист", "role_icon_naturalist"),
    ("Роль: коллекционер", "role_icon_collector"),
    ("Каталог: заголовок", "catalog_title"),
    ("Каталог: скоро в продаже", "catalog_coming_soon"),
    ("Каталог: куплено", "catalog_bought"),
    ("Каталог: покупка", "catalog_buy_success"),
    ("Каталог: оружие", "catalog_cat_weapons"),
    ("Каталог: охота и рыбалка", "catalog_cat_hunting"),
    ("Каталог: боеприпасы", "catalog_cat_ammo"),
    ("Каталог: лошади и сбруя", "catalog_cat_horses"),
    ("Каталог: оружейное снаряжение", "catalog_cat_weapon_equipment"),
    ("Каталог: провиант", "catalog_cat_provisions"),
    ("Каталог: тоники", "catalog_cat_tonics"),
]
