from src.naturalist_logic import *
from src.bounty_logic import *
from src.moonshiner_logic import *
from emoji_config import *
import os
import logging

# Загружаем .env ДО всех остальных импортов, чтобы переменные были доступны
# при инициализации модулей (например, web_routes считывает DISCORD_CLIENT_ID на уровне модуля)
def _bootstrap_load_env(env_file=".env"):
    if not os.path.exists(env_file):
        return
    with open(env_file, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _value = _line.split("=", 1)
            os.environ[_key.strip()] = _value.strip().strip('"').strip("'")

_bootstrap_load_env()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
import json
import signal
import psycopg2
import psycopg2.extras
import random
import math
import asyncio
import re
from contextvars import ContextVar
from flask import Flask, request, jsonify
from threading import Thread
from datetime import date, datetime, time, timedelta, timezone
import discord


from discord import app_commands
from discord.ext import commands, tasks
from discord import PartialEmoji
import src.leveling as leveling
import src.web_routes as web_routes
from src.config import config
COMMANDS_SYNCED = False
ENV_FILE = ".env"
BOT_TOKEN = config.get("token", "") or ""
BOT_VERSION = config.get("version", "v0.0.0")
ECONOMY_FILE = "data/economy.json"
ECONOMY_GLOBAL_KEY = "global"
START_GOLD_RATE = 543.45

# Web server for uptime probe and static dashboard
app = Flask(__name__, static_folder="docs", static_url_path="")

@app.route("/")
def index():
    # Отдаем главную страницу сайта по умолчанию
    return app.send_static_file("index.html")

@app.route("/<path:path>")
def serve_static(path):
    # Отдаем остальные файлы (команды, стили, картинки)
    return app.send_static_file(path)

@app.route("/health")
def _healthcheck():
    logging.info("Healthcheck request")
    return "OK", 200


def get_leveling_db():
    cog = bot.get_cog("LevelingCog")
    return cog.db if cog else None


def run_web():
    try:
        web_routes.register_web_routes(app, lambda: bot, economy_data, get_leveling_db)
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port)
    except Exception:
        return
MIN_GOLD_RATE = 50.0
WORK_COOLDOWN_SECONDS = 60 * 60
DEALER_COOLDOWN_SECONDS = 60 * 60
TREASURE_BANNER_FILE = "assets/images/goldenmap.png"
ROLE_IMAGE_FILE = "assets/images/roles.png"
ROLE_IMAGE_ATTACHMENT_NAME = "roles.png"
BALANCE_IMAGE_FILE = "assets/images/balance.png"
BALANCE_IMAGE_ATTACHMENT_NAME = "balance.png"
COLLECTOR_IMAGE_FILE = "assets/images/collector.png"
COLLECTOR_IMAGE_ATTACHMENT_NAME = "collector.png"
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
DEFAULT_CUSTOM_MESSAGES = {
    "roles_description": "Выберите профессию и купите доступную роль за золото.",
    "roles_footer": "Доступные роли покупаются зелёными кнопками ниже.",
    "work_success": "{mention}, {scenario} и получили **{reward}**.",
    "role_required": "Команда доступна только роли **{role}**. Купить её можно через `/roles`.",
    "reset_prompt": "Для полного сброса сервера введите: Я знаю что я делаю или I know what I'm doing.",
}
CARD_RANKS = ["A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2"]
CARD_SUITS = ["♠", "♥", "♦", "♣"]
BOT_EMBED_COLOR = discord.Color.gold()
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
        "emoji": EMOJI_ROLE_BOUNTY_HUNTER,
        "available": True,
        "description": (
            "Выслеживает опасные цели, берёт контракты на поимку и получает награды "
            "за точность, выдержку и холодную голову."
        ),
    },
    {
        "key": "trader",
        "name": "Торговец",
        "aliases": [],
        "emoji": EMOJI_ROLE_TRADER,
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
        "emoji": EMOJI_ROLE_MOONSHINER,
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
        "emoji": EMOJI_ROLE_NATURALIST,
        "available": True,
        "description": (
            "Изучает природу, выслеживает редких животных и собирает знания там, "
            "где другие видят только дикую местность."
        ),
    },
    {
        "key": "miner",
        "name": "Шахтёр",
        "aliases": [],
        "emoji": EMOJI_ROLE_MINER,
        "available": True,
        "description": (
            "Копает породу, добывает руду и драгоценные камни, переплавляет слитки "
            "и создаёт украшения у ювелира."
        ),
    },
    {
        "key": "collector",
        "name": "Коллекционер",
        "aliases": [],
        "emoji": EMOJI_ROLE_COLLECTOR,
        "available": False,
        "description": (
            "Ищет редкие находки, собирает ценные наборы и превращает любопытство "
            "в аккуратную витрину трофеев."
        ),
    },
]

DEFAULT_ROLE_EMOJIS = {
    role_definition["key"]: role_definition["emoji"]
    for role_definition in ROLE_DEFINITIONS
}

# Суффикс из невидимых пробелов (Hangul Filler U+3164) для визуального выравнивания ролей столбиком
HANGUL_FILLER = "\u3164"
ROLE_DISPLAY_SUFFIX = HANGUL_FILLER * 5
WILDWEST_HEADER_ROLE_NAME = "Роли WildWest:" + ROLE_DISPLAY_SUFFIX
WILDWEST_HEADER_ROLE_COLOR = discord.Color(0x393a41)
ROLE_DISPLAY_COLOR = discord.Color(0xefe58d)




def get_guild_thread_channel_ids(guild_id):
    data = economy_data.guild_data(guild_id)
    channel_ids = set()
    for raw_id in data.get("thread_channel_ids") or []:
        try:
            channel_ids.add(int(raw_id))
        except (TypeError, ValueError):
            continue
    return channel_ids


def set_guild_thread_channel_ids(guild_id, channel_ids):
    data = economy_data.guild_data(guild_id)
    data["thread_channel_ids"] = sorted({int(c) for c in channel_ids})
    save_economy()


def format_welcome_message(template, member):
    text = template or "Добро пожаловать, {mention}!"
    return (
        text.replace("{mention}", member.mention)
        .replace("{user}", member.display_name)
        .replace("{server}", member.guild.name)
        .replace("{count}", str(member.guild.member_count or "?"))
    )


async def send_guild_log(guild, event_key, description, color=discord.Color.dark_grey()):
    token = set_economy_guild_id(guild.id)
    try:
        data = economy_data.current()
        if not data.get("logs_channel_id"):
            return
        log_flags = {
            "join": "log_join",
            "leave": "log_leave",
            "ban": "log_ban",
            "unban": "log_ban",
            "delete": "log_delete",
            "edit": "log_edit",
            "voice_join": "log_voice",
            "voice_leave": "log_voice",
            "command": "log_commands",
        }
        flag = log_flags.get(event_key)
        if flag and not data.get(flag):
            return
        channel = guild.get_channel(int(data["logs_channel_id"]))
        if not channel:
            return
        titles = {
            "join": "Участник присоединился",
            "leave": "Участник вышел",
            "ban": "Участник забанен",
            "unban": "Участник разбанен",
            "delete": "Сообщение удалено",
            "edit": "Сообщение изменено",
            "voice_join": "Вход в голосовой канал",
            "voice_leave": "Выход из голосового канала",
            "command": "Команда использована",
        }
        embed = discord.Embed(
            title=titles.get(event_key, "Событие"),
            description=description,
            color=color,
            timestamp=now_local(),
        )
        await channel.send(embed=embed)
    except Exception as e:
        logging.error(f"Failed to send guild log: {e}")
    finally:
        reset_economy_guild_id(token)


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
            os.environ[key] = value


def today_iso():
    return now_local().date().isoformat()


def today_msk_iso():
    return datetime.now(MSK_TZ).date().isoformat()


def now_local():
    return datetime.now(timezone.utc)


def default_economy():
    return {
        "gold_rate": START_GOLD_RATE,
        "gold_rate_date": today_iso(),
        "cash_emoji": DEFAULT_CASH_EMOJI,
        "gold_emoji": DEFAULT_GOLD_EMOJI,
        "map_emoji": DEFAULT_MAP_EMOJI,
        "stats_emoji": DEFAULT_STATS_EMOJI,
        "safe_emoji": DEFAULT_SAFE_EMOJI,
        "lock_emoji": DEFAULT_LOCK_EMOJI,
        "moonshine_star_emojis": DEFAULT_MOONSHINE_STAR_EMOJIS.copy(),
        "moonshine_special_emoji": DEFAULT_MOONSHINE_SPECIAL_EMOJI,
        "moonshine_button_emojis": DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy(),
        "moonshine_ingredient_emojis": DEFAULT_MOONSHINE_INGREDIENT_EMOJIS.copy(),
        "naturalist_button_emojis": DEFAULT_NATURALIST_BUTTON_EMOJIS.copy(),
        "bounty_button_emojis": DEFAULT_BOUNTY_BUTTON_EMOJIS.copy(),
        "role_key_icons": DEFAULT_ROLE_EMOJIS.copy(),
        "custom_messages": DEFAULT_CUSTOM_MESSAGES.copy(),
        "treasure_dig_emoji": DEFAULT_TREASURE_DIG_EMOJI,
        "treasure_found_emoji": DEFAULT_TREASURE_FOUND_EMOJI,
        "treasure_extra_emoji": DEFAULT_TREASURE_EXTRA_EMOJI,
        "treasure_channel_id": None,
        "news_channel_id": None,
        "thread_channel_ids": [],
        "welcome_enabled": False,
        "welcome_channel_id": None,
        "welcome_role_id": None,
        "welcome_message": "Добро пожаловать на сервер, {mention}! 🎉",
        "farewell_enabled": False,
        "farewell_message": "{user} покинул сервер. До свидания!",
        "logs_channel_id": None,
        "log_join": True,
        "log_leave": True,
        "log_ban": True,
        "log_delete": False,
        "log_edit": False,
        "log_voice": False,
        "log_commands": False,
        "last_treasure_map_drop_date": None,
        "role_icons": {},
        "role_discounts": {},
        "users": {},
    }


def normalize_economy_data(data):
    # If input is not a dict, replace it immediately with defaults
    if not isinstance(data, dict):
        data = default_economy()

    # Ensure gold_emoji is always a non-empty string
    gold = data.get("gold_emoji", DEFAULT_GOLD_EMOJI)
    if gold is None:
        gold = DEFAULT_GOLD_EMOJI
    try:
        gold = str(gold)
    except Exception:
        gold = DEFAULT_GOLD_EMOJI
    if not gold:
        gold = DEFAULT_GOLD_EMOJI
    data["gold_emoji"] = gold

    # Now continue normal defaults and normalization
    data.setdefault("gold_rate", START_GOLD_RATE)
    data.setdefault("gold_rate_date", today_iso())
    data.setdefault("cash_emoji", DEFAULT_CASH_EMOJI)
    # other defaults
    data.setdefault("map_emoji", DEFAULT_MAP_EMOJI)
    data.setdefault("stats_emoji", DEFAULT_STATS_EMOJI)
    data.setdefault("safe_emoji", DEFAULT_SAFE_EMOJI)
    data.setdefault("lock_emoji", DEFAULT_LOCK_EMOJI)
    data.setdefault("moonshine_star_emojis", DEFAULT_MOONSHINE_STAR_EMOJIS.copy())
    data.setdefault("moonshine_special_emoji", DEFAULT_MOONSHINE_SPECIAL_EMOJI)
    data.setdefault("moonshine_condenser_emoji", DEFAULT_MOONSHINE_CONDENSER_EMOJI)
    data.setdefault("moonshine_distiller_emoji", DEFAULT_MOONSHINE_DISTILLER_EMOJI)
    data.setdefault("moonshine_button_emojis", DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy())
    data.setdefault("moonshine_ingredient_emojis", DEFAULT_MOONSHINE_INGREDIENT_EMOJIS.copy())
    data.setdefault("naturalist_button_emojis", DEFAULT_NATURALIST_BUTTON_EMOJIS.copy())
    data.setdefault("bounty_button_emojis", DEFAULT_BOUNTY_BUTTON_EMOJIS.copy())
    data.setdefault("role_key_icons", DEFAULT_ROLE_EMOJIS.copy())
    data.setdefault("custom_messages", DEFAULT_CUSTOM_MESSAGES.copy())
    data.setdefault("treasure_dig_emoji", DEFAULT_TREASURE_DIG_EMOJI)
    data.setdefault("treasure_found_emoji", DEFAULT_TREASURE_FOUND_EMOJI)
    data.setdefault("treasure_extra_emoji", DEFAULT_TREASURE_EXTRA_EMOJI)
    data.setdefault("treasure_channel_id", None)
    data.setdefault("news_channel_id", None)
    data.setdefault("thread_channel_ids", [])
    data.setdefault("welcome_enabled", False)
    data.setdefault("welcome_channel_id", None)
    data.setdefault("welcome_role_id", None)
    data.setdefault("welcome_message", "Добро пожаловать на сервер, {mention}! 🎉")
    data.setdefault("farewell_enabled", False)
    data.setdefault("farewell_message", "{user} покинул сервер. До свидания!")
    data.setdefault("logs_channel_id", None)
    data.setdefault("log_join", True)
    data.setdefault("log_leave", True)
    data.setdefault("log_ban", True)
    data.setdefault("log_delete", False)
    data.setdefault("log_edit", False)
    data.setdefault("log_voice", False)
    data.setdefault("log_commands", False)
    data.setdefault("last_treasure_map_drop_date", None)
    data.setdefault("role_icons", {})
    data.setdefault("role_discounts", {})
    data.setdefault("users", {})

    if not isinstance(data["role_icons"], dict):
        data["role_icons"] = {}
    if not isinstance(data["role_discounts"], dict):
        data["role_discounts"] = {}
    if not isinstance(data["role_key_icons"], dict):
        data["role_key_icons"] = DEFAULT_ROLE_EMOJIS.copy()
    for role_key, emoji in DEFAULT_ROLE_EMOJIS.items():
        data["role_key_icons"].setdefault(role_key, emoji)
    if not isinstance(data["custom_messages"], dict):
        data["custom_messages"] = DEFAULT_CUSTOM_MESSAGES.copy()
    for key, message in DEFAULT_CUSTOM_MESSAGES.items():
        data["custom_messages"].setdefault(key, message)
    if not isinstance(data["moonshine_star_emojis"], dict):
        data["moonshine_star_emojis"] = DEFAULT_MOONSHINE_STAR_EMOJIS.copy()
    for level, emoji in DEFAULT_MOONSHINE_STAR_EMOJIS.items():
        data["moonshine_star_emojis"].setdefault(level, emoji)
    for level in ("1", "2", "3"):
        if not data["moonshine_star_emojis"].get(level):
            data["moonshine_star_emojis"][level] = DEFAULT_MOONSHINE_STAR_EMOJIS[level]
    if not data.get("moonshine_special_emoji"):
        data["moonshine_special_emoji"] = DEFAULT_MOONSHINE_SPECIAL_EMOJI
    if not data.get("moonshine_condenser_emoji"):
        data["moonshine_condenser_emoji"] = DEFAULT_MOONSHINE_CONDENSER_EMOJI
    if not data.get("moonshine_distiller_emoji"):
        data["moonshine_distiller_emoji"] = DEFAULT_MOONSHINE_DISTILLER_EMOJI

    if not isinstance(data.get("moonshine_ingredient_emojis"), dict):
        data["moonshine_ingredient_emojis"] = DEFAULT_MOONSHINE_INGREDIENT_EMOJIS.copy()
    for ingredient, emoji in DEFAULT_MOONSHINE_INGREDIENT_EMOJIS.items():
        data["moonshine_ingredient_emojis"].setdefault(ingredient, emoji)
        
    data.setdefault("moonshine_ui_prod", DEFAULT_MOONSHINE_PROD_EMOJI)
    data.setdefault("moonshine_ui_lvl", DEFAULT_MOONSHINE_LVL_EMOJI)
    data.setdefault("moonshine_ui_access", DEFAULT_MOONSHINE_ACCESS_EMOJI)
    data.setdefault("moonshine_ui_bottles", DEFAULT_MOONSHINE_BOTTLES_EMOJI)
    data.setdefault("moonshine_ui_wagon", DEFAULT_MOONSHINE_WAGON_EMOJI)
    data.setdefault("moonshine_ui_brewing", DEFAULT_MOONSHINE_BREWING_EMOJI)
    data.setdefault("moonshine_ui_kettle", DEFAULT_MOONSHINE_KETTLE_EMOJI)
    data.setdefault("moonshine_ui_equip", DEFAULT_MOONSHINE_EQUIP_EMOJI)
    data.setdefault("moonshine_ui_skill", DEFAULT_MOONSHINE_SKILL_EMOJI)
    data.setdefault("moonshine_ui_stor_full", DEFAULT_MOONSHINE_STOR_FULL_EMOJI)
    data.setdefault("moonshine_ui_stor_empty", DEFAULT_MOONSHINE_STOR_EMPTY_EMOJI)
    data.setdefault("moonshine_ui_finance", DEFAULT_MOONSHINE_FINANCE_EMOJI)
    
    data.setdefault("balance_ui_finance", DEFAULT_BALANCE_FINANCE_EMOJI)
    data.setdefault("balance_ui_roles", DEFAULT_BALANCE_ROLES_EMOJI)
    data.setdefault("balance_ui_economy", DEFAULT_BALANCE_ECONOMY_EMOJI)
    data.setdefault("balance_ui_gang", DEFAULT_BALANCE_GANG_EMOJI)

    if not isinstance(data["moonshine_button_emojis"], dict):
        data["moonshine_button_emojis"] = DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy()
    for key, emoji in DEFAULT_MOONSHINE_BUTTON_EMOJIS.items():
        data["moonshine_button_emojis"].setdefault(key, emoji)
    if not isinstance(data["naturalist_button_emojis"], dict):
        data["naturalist_button_emojis"] = DEFAULT_NATURALIST_BUTTON_EMOJIS.copy()
    for key, emoji in DEFAULT_NATURALIST_BUTTON_EMOJIS.items():
        data["naturalist_button_emojis"].setdefault(key, emoji)
    if not isinstance(data["bounty_button_emojis"], dict):
        data["bounty_button_emojis"] = DEFAULT_BOUNTY_BUTTON_EMOJIS.copy()
    for key, emoji in DEFAULT_BOUNTY_BUTTON_EMOJIS.items():
        data["bounty_button_emojis"].setdefault(key, emoji)
    if not isinstance(data["users"], dict):
        data["users"] = {}
    if not isinstance(data.get("thread_channel_ids"), list):
        data["thread_channel_ids"] = []

    return data

def load_economy():
    if not os.path.exists(ECONOMY_FILE):
        return {"version": 2, "guilds": {ECONOMY_GLOBAL_KEY: default_economy()}}

    try:
        with open(ECONOMY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        logging.info(f"{ECONOMY_FILE} поврежён; создаётся новая экономика.")
        return {"version": 2, "guilds": {ECONOMY_GLOBAL_KEY: default_economy()}}

    if not isinstance(data, dict):
        return {"version": 2, "guilds": {ECONOMY_GLOBAL_KEY: default_economy()}}

    if isinstance(data.get("guilds"), dict):
        guilds = {}
        for guild_id, guild_data in data["guilds"].items():
            guilds[str(guild_id)] = normalize_economy_data(guild_data)
        guilds.setdefault(ECONOMY_GLOBAL_KEY, default_economy())
        return {"version": 2, "guilds": guilds}

    legacy_data = normalize_economy_data(data)
    return {"version": 2, "guilds": {ECONOMY_GLOBAL_KEY: legacy_data}}


current_economy_guild_id = ContextVar("current_economy_guild_id", default=None)


def set_economy_guild_id(guild_id):
    return current_economy_guild_id.set(str(guild_id) if guild_id else ECONOMY_GLOBAL_KEY)


def reset_economy_guild_id(token):
    current_economy_guild_id.reset(token)


def get_current_economy_key():
    return current_economy_guild_id.get() or ECONOMY_GLOBAL_KEY


def with_economy_context(func):
    async def wrapper(interaction, *args, **kwargs):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            return await func(interaction, *args, **kwargs)
        finally:
            reset_economy_guild_id(token)
    return wrapper


def _normalize_db_url_for_psycopg2(url):
    """Нормализует DATABASE_URL для psycopg2 (убирает +asyncpg и другие SQLAlchemy-префиксы)."""
    if not url:
        return url
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgres://", "postgresql://")
    return url


class EconomyStore:
    def __init__(self, db_url=None):
        if db_url is None:
            db_url = os.environ.get("DATABASE_URL")
        self.db_url = _normalize_db_url_for_psycopg2(db_url)
        self._connect()
        self._init_tables()
        self.guild_cache = {}

    def _connect(self):
        """Создать (или пересоздать) соединение с PostgreSQL."""
        self.conn = psycopg2.connect(self.db_url, cursor_factory=psycopg2.extras.DictCursor)
        self.conn.autocommit = True

    def _ensure_conn(self):
        """Проверить что соединение живое, переподключиться если нет."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception:
            logging.warning("EconomyStore: соединение разорвано, переподключаемся...")
            try:
                self.conn.close()
            except Exception:
                pass
            self._connect()

    def _init_tables(self):
        """Создать таблицы economy_guilds / economy_users и мигрировать данные из старых таблиц."""
        with self.conn.cursor() as cursor:
            # Создаём новые таблицы с уникальными именами
            cursor.execute("CREATE TABLE IF NOT EXISTS economy_guilds (guild_id TEXT PRIMARY KEY, data TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS economy_users (guild_id TEXT, user_id TEXT, data TEXT, PRIMARY KEY(guild_id, user_id))")

            # --- Миграция из старой таблицы guilds (если в ней есть колонка data TEXT) ---
            try:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'guilds' AND column_name = 'data'
                """)
                if cursor.fetchone():
                    # Старая таблица guilds с колонкой data существует — мигрируем
                    cursor.execute("SELECT COUNT(*) FROM economy_guilds")
                    new_count = cursor.fetchone()[0]
                    if new_count == 0:
                        cursor.execute("""
                            INSERT INTO economy_guilds (guild_id, data)
                            SELECT guild_id, data FROM guilds
                            ON CONFLICT (guild_id) DO NOTHING
                        """)
                        migrated = cursor.rowcount
                        if migrated > 0:
                            logging.info(f"EconomyStore: мигрировано {migrated} гильдий из старой таблицы 'guilds' → 'economy_guilds'")
            except Exception as e:
                logging.debug(f"EconomyStore: миграция guilds пропущена: {e}")

            # --- Миграция из старой таблицы users (если в ней есть колонка data TEXT) ---
            try:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'data'
                """)
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*) FROM economy_users")
                    new_count = cursor.fetchone()[0]
                    if new_count == 0:
                        cursor.execute("""
                            INSERT INTO economy_users (guild_id, user_id, data)
                            SELECT guild_id, user_id, data FROM users
                            WHERE data IS NOT NULL
                            ON CONFLICT (guild_id, user_id) DO NOTHING
                        """)
                        migrated = cursor.rowcount
                        if migrated > 0:
                            logging.info(f"EconomyStore: мигрировано {migrated} пользователей из старой таблицы 'users' → 'economy_users'")
            except Exception as e:
                logging.debug(f"EconomyStore: миграция users пропущена: {e}")

    def _load_guild(self, guild_id):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT data FROM economy_guilds WHERE guild_id = %s", (str(guild_id),))
            row = cursor.fetchone()
            if row:
                data = json.loads(row["data"])
            else:
                data = default_economy()
            
            # Load users
            cursor.execute("SELECT user_id, data FROM economy_users WHERE guild_id = %s", (str(guild_id),))
            users = {}
            for u_row in cursor:
                users[u_row["user_id"]] = json.loads(u_row["data"])
            
            data["users"] = users
            return normalize_economy_data(data)

    def current(self):
        guild_id = get_current_economy_key()
        if guild_id not in self.guild_cache:
            self.guild_cache[guild_id] = self._load_guild(guild_id)
        return self.guild_cache[guild_id]

    def guild_data(self, guild_id):
        guild_key = str(guild_id) if guild_id else ECONOMY_GLOBAL_KEY
        if guild_key not in self.guild_cache:
            self.guild_cache[guild_key] = self._load_guild(guild_key)
        return self.guild_cache[guild_key]

    def reset_current(self):
        guild_id = get_current_economy_key()
        # Удаляем данные игроков из БД сразу, чтобы сброс был атомарным.
        # Без этого: кэш сбрасывается, игроки создают новые пустые аккаунты,
        # save_all() перезаписывает старые записи нулями — данные теряются.
        self._delete_guild_users_from_db(guild_id)
        self.guild_cache[guild_id] = default_economy()
        self.save_all()

    def reset_guild(self, guild_id):
        guild_key = str(guild_id) if guild_id else ECONOMY_GLOBAL_KEY
        self._delete_guild_users_from_db(guild_key)
        self.guild_cache[guild_key] = default_economy()
        self.save_all()

    def _delete_guild_users_from_db(self, guild_key):
        """Полностью удаляет всех игроков гильдии из БД — вызывается только при явном сбросе."""
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM economy_users WHERE guild_id = %s", (str(guild_key),))

    def configured_treasure_guild_ids(self):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT guild_id FROM economy_guilds")
            rows = cursor.fetchall()
        for row in rows:
            g_id = row["guild_id"]
            if g_id not in self.guild_cache:
                self.guild_cache[g_id] = self._load_guild(g_id)
        return [
            g_id for g_id, g_data in self.guild_cache.items()
            if g_id != ECONOMY_GLOBAL_KEY and g_data.get("treasure_channel_id")
        ]

    def to_json(self):
        return {} # Deprecated

    def get(self, key, default=None): return self.current().get(key, default)
    def setdefault(self, key, default=None): return self.current().setdefault(key, default)
    def pop(self, key, default=None): return self.current().pop(key, default)
    def __getitem__(self, key): return self.current()[key]
    def __setitem__(self, key, value): self.current()[key] = value
    def __contains__(self, key): return key in self.current()

    def save_all(self):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            for guild_id, data in self.guild_cache.items():
                data_copy = dict(data)
                users = data_copy.pop("users", {})
                cursor.execute(
                    "INSERT INTO economy_guilds (guild_id, data) VALUES (%s, %s) ON CONFLICT (guild_id) DO UPDATE SET data = EXCLUDED.data", 
                    (str(guild_id), json.dumps(data_copy, ensure_ascii=False))
                )
                for user_id, user_data in users.items():
                    cursor.execute(
                        "INSERT INTO economy_users (guild_id, user_id, data) VALUES (%s, %s, %s) ON CONFLICT (guild_id, user_id) DO UPDATE SET data = EXCLUDED.data",
                        (str(guild_id), str(user_id), json.dumps(user_data, ensure_ascii=False))
                    )

def save_economy():
    economy_data.save_all()


def parse_local_datetime(value):
    if not value:
        return now_local()

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return now_local()

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_local_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return now_local().date()


def format_number(value, decimals=2):
    text = f"{value:,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",")


def get_cash_emoji():
    emoji = economy_data.get("cash_emoji")
    if not emoji:
        return DEFAULT_CASH_EMOJI
    return str(emoji)


def get_gold_emoji():
    emoji = economy_data.get("gold_emoji")
    if not emoji:
        return DEFAULT_GOLD_EMOJI
    return str(emoji)

def get_map_emoji():
    emoji = economy_data.get("map_emoji")
    if not emoji:
        return str(DEFAULT_MAP_EMOJI)
    return str(emoji)


def get_stats_emoji():
    emoji = economy_data.get("stats_emoji")
    if not emoji:
        return str(DEFAULT_STATS_EMOJI)
    return str(emoji)


def get_safe_emoji():
    emoji = economy_data.get("safe_emoji")
    if not emoji:
        return str(DEFAULT_SAFE_EMOJI)
    return str(emoji)


def get_lock_emoji():
    emoji = economy_data.get("lock_emoji")
    if not emoji:
        return str(DEFAULT_LOCK_EMOJI)
    return str(emoji)












def debug_gold_info():
    """Return tuple (economy_key, stored_value, resolved_string) for debugging."""
    key = get_current_economy_key()
    stored = economy_data.get("gold_emoji")
    resolved = get_gold_emoji()
    return key, stored, resolved






def get_custom_message(message_key):
    messages = economy_data.get("custom_messages", {})
    msg = messages.get(message_key)
    if not msg:
        return DEFAULT_CUSTOM_MESSAGES[message_key]
    return msg


def format_money(value):
    return f"{format_number(value)} {get_cash_emoji()}"


def format_money_plain(value):
    return f"{format_number(value)}"


def format_gold(value):
    return f"{format_number(value)} {get_gold_emoji()}"


def format_gold_plain(value):
    return f"{format_number(value)}"


def format_exchange_rate(value):
    return f"{format_number(value)} {get_cash_emoji()}"



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
    return f"{format_gold_price_value(value)} {get_gold_emoji()}"


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
            body = f"{get_lock_emoji()} Недоступен"

        sections.append(f"{branch} {icon} {name}: {body}")

    return "\n".join(sections)


def format_progress_bar(value, width=10):
    percent = max(0.0, min(100.0, float(value)))
    filled = round(width * percent / 100)
    return "█" * filled + "░" * (width - filled)






























def format_minutes(seconds):
    return f"{max(1, int(seconds // 60))} мин"




def fit_embed_description(lines, limit=3900):
    description = ""
    hidden_count = 0
    for line in lines:
        next_description = f"{description}\n{line}" if description else line
        if len(next_description) > limit:
            hidden_count += 1
            continue
        description = next_description
    if hidden_count:
        suffix = f"\n…и ещё {hidden_count} строк. Уточните выбор через меню ниже."
        if len(description) + len(suffix) <= 4096:
            description += suffix
    return description


def format_recipe_ingredients(recipe):
    return ", ".join(
        f"{amount}x {ingredient}" for ingredient, amount in recipe["ingredients"].items()
    )














from src.xp_utils import *






























def format_sample_name(sample_key):
    if sample_key in ANIMALS:
        return ANIMALS[sample_key]["name"]
    if sample_key in LEGENDARY_ANIMALS:
        return LEGENDARY_ANIMALS[sample_key]["name"]
    return sample_key












def format_balance_role_sections(guild, member, account):
    rows = []

    for index, role_definition in enumerate(ROLE_DEFINITIONS):
        role = find_guild_role(guild, role_definition)
        owns_role = has_game_role(member, role_definition["key"], account)
        icon = get_role_icon(role_definition, role)
        name = role_definition["name"]
        role_key = role_definition["key"]
        branch = "└─" if index == len(ROLE_DEFINITIONS) - 1 else "├─"

        if owns_role:
            if role_key == DEALER_ROLE_KEY:
                wagon = account["dealer_wagon"]
                status = f"повозка {format_progress_percent(wagon)}"
            elif role_key == MOONSHINER_ROLE_KEY:
                moonshine = get_moonshine_account(account)
                status = (
                    f"ур. {get_moonshine_level(moonshine)}, "
                    f"бутылки {get_moonshine_bottles(moonshine)}/20, "
                    f"{format_moonshine_batch_status(moonshine)}"
                )
            elif role_key == BOUNTY_ROLE_KEY:
                bounty = get_bounty_account(account)
                status = (
                    f"ур. {bounty['level']}, поймано {format_integer(bounty['captures'])}, "
                    f"сбежало {format_integer(bounty['escaped'])}"
                )
            elif role_key == NATURALIST_ROLE_KEY:
                naturalist = get_naturalist_account(account)
                status = (
                    f"ур. {naturalist['level']}, "
                    f"образцов {format_integer(count_naturalist_samples(naturalist))}"
                )
            elif role_key == "miner":
                status = format_balance_miner_status(guild, member)
            elif role_key == "collector":
                status = f"витрина: {format_collection_showcase(account)}"
            else:
                status = "доступ открыт"
            rows.append(f"{branch} ✅ {icon} **{name}** — {status}")
        else:
            lock_reason = (
                f"не куплено · {format_role_price(get_role_price(role))} · `/roles`"
                if role_definition.get("available")
                else "пока недоступно на сервере"
            )
            rows.append(
                f"{branch} {get_lock_emoji()} {icon} **{name}** — {lock_reason}"
            )

    return "\n".join(rows)


def format_balance_miner_status(guild, member):
    """Read the miner snapshot from its dedicated persistent store."""
    miner_cog = bot.get_cog("MinerCog")
    if miner_cog is None or guild is None:
        return "доступ открыт · `/mine`"
    try:
        player = miner_cog.db.get_player(str(guild.id), str(member.id))
        depth = max(0, int(player.get("current_depth", 0)))
        total = max(0, int(player.get("total_mined", 0)))
        durability = max(0, int(player.get("pickaxe_durability", 0)))
    except Exception:
        logging.exception(
            "Failed to read miner balance snapshot for guild=%s user=%s",
            getattr(guild, "id", None),
            getattr(member, "id", None),
        )
        return "доступ открыт · `/mine`"
    return (
        f"глубина {depth} м, добыто {total}, прочность кирки {durability} · `/mine`"
    )


def format_balance_gang_section(member, account):
    gang_emoji = economy_data.get("balance_ui_gang", DEFAULT_BALANCE_GANG_EMOJI)
    gang_name = account.get("gang_name")
    guild_data = economy_data.current()
    gangs = guild_data.get("gangs", {})
    gang = gangs.get(gang_name) if isinstance(gangs, dict) and gang_name else None

    if not isinstance(gang, dict):
        return (
            f"{gang_emoji} Банда\n"
            f"└─ {get_lock_emoji()} Вы не состоите в банде · "
            "`/gang-create` или приглашение лидера"
        )

    is_leader = str(gang.get("leader")) == str(member.id)
    role_name = (
        gang.get("leader_role_name", "Лидер")
        if is_leader
        else gang.get("member_role_name", "Участник")
    )
    members = gang.get("members", [])
    members_count = len(members) if isinstance(members, list) else 0
    try:
        gang_cash = float(gang.get("cash", 0.0))
    except (TypeError, ValueError):
        gang_cash = 0.0
    try:
        gang_gold = float(gang.get("gold", 0.0))
    except (TypeError, ValueError):
        gang_gold = 0.0
    try:
        gang_level = max(1, int(gang.get("level", 1)))
    except (TypeError, ValueError):
        gang_level = 1
    try:
        gang_influence = max(0, int(gang.get("influence", 0)))
    except (TypeError, ValueError):
        gang_influence = 0

    return (
        f"{gang_emoji} Банда\n"
        f"├─ **{gang_name}** [#{gang.get('id', '?')}] · {role_name}\n"
        f"├─ Уровень: **{gang_level}** · влияние: **{gang_influence}**\n"
        f"├─ Участников: **{members_count}**\n"
        f"├─ Общак: **{format_money_plain(gang_cash)} {get_cash_emoji()} / "
        f"{format_gold_plain(gang_gold)} {get_gold_emoji()}**\n"
        "└─ Управление: `/gang`"
    )


def format_balance_property_section(account):
    inventory = account.get("inventory", {})
    if not isinstance(inventory, dict):
        inventory = {}
    owned_items = [
        (str(item), amount)
        for item, amount in inventory.items()
        if item != "safe" and isinstance(amount, (int, float)) and amount > 0
    ]
    total_items = sum(int(amount) for _, amount in owned_items)
    showcase = account.get("collection_showcase", [])
    if not isinstance(showcase, list):
        showcase = []
    showcase_text = ", ".join(str(item) for item in showcase[:3]) or "пусто"
    if len(showcase) > 3:
        showcase_text += f" и ещё {len(showcase) - 3}"

    return (
        "🎒 Имущество\n"
        f"├─ Каталог: **{len(owned_items)} видов / {total_items} предметов** · `/catalog`\n"
        f"└─ Витрина: **{showcase_text}**"
    )


def format_account(account):
    return (
        f"Деньги: **{format_money(account['cash'])}**\n"
        f"Золото: **{format_gold(account['gold'])}**\n"

        f"Карты: **{format_treasure_maps(account['treasure_maps'])}**\n"
        f"Повозка торговца: **{format_percent(account['dealer_wagon'])}**\n"
        f"Самогонщик: **{format_moonshine_short(account)}**\n"
        f"Витрина коллекционных предметов: **{format_collection_showcase(account)}**"
    )


def format_duration(seconds):
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    parts = []
    if days:
        parts.append(f"{days} д")
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    if seconds or not parts:
        parts.append(f"{seconds} сек")
    return " ".join(parts[:2])


def is_valid_amount(amount):
    return math.isfinite(amount) and amount > 0


def update_gold_rate():
    current_day = parse_local_date(economy_data.get("gold_rate_date", today_iso()))
    target_day = now_local().date()
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
            "treasure_maps": 0,
            "owned_roles": [],
            "dealer_wagon": 0.0,
            "last_dealer_at": None,
            "bounty": default_bounty_data(),
            "moonshine": default_moonshine_data(),
            "naturalist": default_naturalist_data(),
            "collection_showcase": [],
            "last_work_at": None,
        },
    )

    # --- Ensure numeric fields are valid floats (fix corrupted data)
    try:
        account["cash"] = float(account.get("cash", 0.0))
    except (TypeError, ValueError):
        account["cash"] = 0.0

    try:
        account["gold"] = float(account.get("gold", 0.0))
    except (TypeError, ValueError):
        account["gold"] = 0.0

    account.setdefault("cash", 0.0)
    account.setdefault("gold", 0.0)
    account.setdefault("treasure_maps", 0)
    account.setdefault("owned_roles", [])
    account.setdefault("dealer_wagon", 0.0)
    account.setdefault("last_dealer_at", None)
    account["bounty"] = normalize_bounty_data(account.get("bounty"))
    account["moonshine"] = normalize_moonshine_data(account.get("moonshine"))
    account["naturalist"] = normalize_naturalist_data(account.get("naturalist"))
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
    account.setdefault("last_work_at", None)
    return account




def random_work_reward():
    return min(300, max(20, round(20 + (300 - 20) * (random.random() ** 2.35))))


WORK_SCENARIOS = [
    "вы помогли фермеру перегнать скот",
    "вы разгрузили ящики на станции",
    "вы сопроводили дилижанс до соседнего города",
    "вы починили изгородь у ранчо",
    "вы нашли подработку у конюха",
    "вы доставили посылку старому знакомому",
]


def random_work_scenario():
    return random.choice(WORK_SCENARIOS)


def get_work_cooldown(account):
    last_work_at = account.get("last_work_at")
    if not last_work_at:
        return 0

    seconds_passed = (now_local() - parse_local_datetime(last_work_at)).total_seconds()
    return max(0, WORK_COOLDOWN_SECONDS - seconds_passed)


def get_dealer_cooldown(account):
    last_dealer_at = account.get("last_dealer_at")
    if not last_dealer_at:
        return 0

    seconds_passed = (now_local() - parse_local_datetime(last_dealer_at)).total_seconds()
    return max(0, DEALER_COOLDOWN_SECONDS - seconds_passed)


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
    stripped = str(name).strip(HANGUL_FILLER).strip()
    return " ".join(stripped.split()).casefold()


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


def get_role_display_name(role_definition):
    """Возвращает отображаемое имя роли с суффиксом-выравнивателем для Discord."""
    return role_definition["name"] + ROLE_DISPLAY_SUFFIX


async def ensure_guild_roles(guild: discord.Guild) -> dict:
    """Создаёт/обновляет игровые роли и заголовочную роль 'Роли WildWest:' на сервере.

    Возвращает dict: {'created': [...], 'updated': [...], 'skipped': [...], 'errors': [...]}.
    """
    created = []
    updated = []
    skipped = []
    errors = []
    game_roles = []

    for role_definition in ROLE_DEFINITIONS:
        display_name = get_role_display_name(role_definition)
        role = find_guild_role(guild, role_definition)

        if role is None:
            try:
                role = await guild.create_role(
                    name=display_name,
                    color=ROLE_DISPLAY_COLOR,
                    reason="WildWest bot: создание игровой роли",
                )
                created.append(display_name)
            except (discord.Forbidden, discord.HTTPException) as e:
                errors.append(f"'{display_name}': {e}")
                continue
        else:
            needs_edit = role.name != display_name or role.color != ROLE_DISPLAY_COLOR
            if needs_edit:
                try:
                    await role.edit(
                        name=display_name,
                        color=ROLE_DISPLAY_COLOR,
                        reason="WildWest bot: обновление игровой роли",
                    )
                    updated.append(display_name)
                except (discord.Forbidden, discord.HTTPException) as e:
                    errors.append(f"'{display_name}': {e}")
            else:
                skipped.append(display_name)

        game_roles.append(role)

    # Найти или создать заголовочную роль "Роли WildWest:"
    header_role = discord.utils.find(
        lambda r: normalize_role_name(r.name) == normalize_role_name(WILDWEST_HEADER_ROLE_NAME),
        guild.roles,
    )
    if header_role is None:
        try:
            header_role = await guild.create_role(
                name=WILDWEST_HEADER_ROLE_NAME,
                color=WILDWEST_HEADER_ROLE_COLOR,
                reason="WildWest bot: создание заголовочной роли",
            )
            created.append(WILDWEST_HEADER_ROLE_NAME)
        except (discord.Forbidden, discord.HTTPException) as e:
            errors.append(f"'{WILDWEST_HEADER_ROLE_NAME}': {e}")
            header_role = None
    else:
        needs_edit = (
            header_role.name != WILDWEST_HEADER_ROLE_NAME
            or header_role.color != WILDWEST_HEADER_ROLE_COLOR
        )
        if needs_edit:
            try:
                await header_role.edit(
                    name=WILDWEST_HEADER_ROLE_NAME,
                    color=WILDWEST_HEADER_ROLE_COLOR,
                    reason="WildWest bot: обновление заголовочной роли",
                )
                updated.append(WILDWEST_HEADER_ROLE_NAME)
            except (discord.Forbidden, discord.HTTPException) as e:
                errors.append(f"'{WILDWEST_HEADER_ROLE_NAME}': {e}")
        else:
            skipped.append(WILDWEST_HEADER_ROLE_NAME)

    # Разместить заголовочную роль выше всех игровых ролей
    if header_role is not None and game_roles:
        try:
            max_pos = max(r.position for r in game_roles)
            if header_role.position <= max_pos:
                await guild.edit_role_positions(
                    positions={header_role: max_pos + 1},
                    reason="WildWest bot: позиционирование заголовочной роли",
                )
        except (discord.Forbidden, discord.HTTPException):
            pass

    # Выдать заголовочную роль всем участникам (не ботам), у кого её ещё нет
    assigned_count = 0
    if header_role is not None:
        for member in guild.members:
            if member.bot:
                continue
            if header_role not in member.roles:
                try:
                    await member.add_roles(header_role, reason="WildWest bot: выдача заголовочной роли")
                    assigned_count += 1
                except (discord.Forbidden, discord.HTTPException):
                    pass

    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors, "assigned": assigned_count}


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
    role_key_icons = economy_data.get("role_key_icons", {})
    configured_role_icon = role_key_icons.get(role_definition["key"])
    if configured_role_icon:
        return configured_role_icon
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

    expires_text = discount["expires_at"].astimezone(MSK_TZ).strftime("%d.%m.%Y")
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
            "`/dealer` — заполнить повозку на 10–35% раз в час.\n"
            "`/dealer-delivery` — доставить полную повозку и получить 500–625."
        )
    if role_key == MOONSHINER_ROLE_KEY:
        return (
            "\n\nКоманды самогонщика:\n"
            "`/moonshine` — открыть меню предприятия, выбрать бражку за 50, "
            "добавить особые ингредиенты, купить улучшения и отвезти повозку."
        )
    if role_key == "miner":
        return (
            "\n\nКоманды шахтёра:\n"
            "`/mine` — копать один куб породы (лимит 3 в день).\n"
            "`/mine-status` — глубина, инвентарь, состояние кирки.\n"
            "`/mine-buy` — купить расходники и кирки.\n"
            "`/mine-sell` — продать руду, слитки и находки.\n"
            "`/mine-smelt` — переплавить руду у кузнеца.\n"
            "`/mine-forge` — создать украшение у ювелира."
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
        title="Посылка на почте",
        description=(
            'Вам на почту пришёл документ с подписью **"от старого приятеля"**. '
            "Открывая конверт, вы находите в нём карту сокровищ!\n\n"
            "Используйте `/excavation`, чтобы отправиться на раскопки."
        ),
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


def get_balance_image_file():
    if not os.path.exists(BALANCE_IMAGE_FILE):
        return None
    return discord.File(BALANCE_IMAGE_FILE, filename=BALANCE_IMAGE_ATTACHMENT_NAME)








def build_bot_embed(title, description, color=BOT_EMBED_COLOR):
    return discord.Embed(
        title=title,
        description=description,
        color=color,
    )


async def send_embed_response(
    interaction,
    title,
    description,
    *,
    ephemeral=False,
    color=BOT_EMBED_COLOR,
    view=None,
    file=None,
):
    embed = build_bot_embed(title, description, color=color)
    
    # Динамически собираем параметры
    kwargs = {"embed": embed, "ephemeral": ephemeral}
    if view is not None:
        kwargs["view"] = view
    if file is not None:
        kwargs["file"] = file
        
    if interaction.response.is_done():
        await interaction.followup.send(**kwargs)
    else:
        await interaction.response.send_message(**kwargs)


async def send_interaction_response(interaction, *args, **kwargs):
    """Reply safely whether a component was already deferred or not."""
    if interaction.response.is_done():
        return await interaction.followup.send(*args, **kwargs)
    return await interaction.response.send_message(*args, **kwargs)


async def send_embed_followup(
    interaction,
    title,
    description,
    *,
    ephemeral=False,
    color=BOT_EMBED_COLOR,
    view=None,
    wait=False,
):
    embed = build_bot_embed(title, description, color=color)
    
    kwargs = {"embed": embed, "ephemeral": ephemeral, "wait": wait}
    if view is not None:
        kwargs["view"] = view
        
    return await interaction.followup.send(**kwargs)


async def send_loading_then_edit(
    interaction,
    loading_text,
    embed,
    *,
    view=None,
    file=None,
    ephemeral=False,
    delay=2,
):
    loading_embed = build_bot_embed(
        "Ожидание",
        f":hourglass_flowing_sand: {loading_text}",
        color=discord.Color.dark_gold(),
    )
    
    # Защита при отправке загрузочного сообщения
    send_kwargs = {"embed": loading_embed, "ephemeral": ephemeral}
    if file is not None:
        send_kwargs["file"] = file
        
    if interaction.response.is_done():
        # The interaction was acknowledged before synchronous PostgreSQL I/O.
        # Send the result immediately instead of attempting a second response.
        result_kwargs = {"embed": embed, "ephemeral": ephemeral}
        if view is not None:
            result_kwargs["view"] = view
        if file is not None:
            result_kwargs["file"] = file
        await interaction.followup.send(**result_kwargs)
        return

    await interaction.response.send_message(**send_kwargs)
    await asyncio.sleep(delay)
    
    # Защита при обновлении на итоговое сообщение
    edit_kwargs = {"embed": embed}
    if view is not None:
        edit_kwargs["view"] = view
        
    await interaction.edit_original_response(**edit_kwargs)

_original_interaction_send_message = discord.InteractionResponse.send_message
_original_webhook_send = discord.Webhook.send


async def _embed_interaction_send_message(self, content=None, *args, **kwargs):
    if content is not None and kwargs.get("embed") is None and kwargs.get("embeds") is None:
        kwargs["embed"] = build_bot_embed("Сообщение", str(content))
        content = None
    return await _original_interaction_send_message(self, content, *args, **kwargs)


async def _embed_webhook_send(self, content=None, *args, **kwargs):
    if content is not None and kwargs.get("embed") is None and kwargs.get("embeds") is None:
        kwargs["embed"] = build_bot_embed("Сообщение", str(content))
        content = None
    return await _original_webhook_send(self, content, *args, **kwargs)


discord.InteractionResponse.send_message = _embed_interaction_send_message
discord.Webhook.send = _embed_webhook_send


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
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
async def setup_hook():
    bot.set_economy_guild_id = set_economy_guild_id
    bot.reset_economy_guild_id = reset_economy_guild_id
    bot.validate_bet = validate_bet
    bot.economy_lock = economy_lock
    bot.get_account = get_account
    bot.save_economy = save_economy
    bot.format_money = format_money
    try:
        await bot.add_cog(leveling.LevelingCog(bot))
        await bot.load_extension("cogs.casino")
        await bot.load_extension("cogs.catalog")
        await bot.load_extension("cogs.gangs")
        await bot.load_extension("cogs.robbery")
        await bot.load_extension("cogs.bounty")
        await bot.load_extension("cogs.naturalist")
        await bot.load_extension("cogs.miner")
    except Exception as e:
        logging.error(f"Failed to load LevelingCog: {e}")
bot.setup_hook = setup_hook

economy_data = EconomyStore()
economy_lock = asyncio.Lock()

RESET_CONFIRMATION_PHRASES = ("Я знаю что я делаю", "I know what I'm doing")
ALL_TARGET_ALIASES = {"all", "@everyone", "everyone", "все", "всем", "всех"}
ADMIN_COMMAND_NAMES = {
    "reset-all",
    "delete-role",
    "restart-roles",
    "check",
    "give-money",
    "remove-money",
    "set-money",
    "give-gold",
    "remove-gold",
    "set-gold",
    "give-map",
    "set-rate",
    "treasure-channel",
    "treasure-event",
    "set-icon-roles",
    "set-discounts-roles",
    "clear-discounts-roles",
    "fill-dealer",
    "give-moonshine-ingredient",
    "remove-moonshine-ingredient",
    "set-moonshine-upgrade",
    "set-moonshine-skill",
    "finish-moonshine",
    "reset-moonshine",
    "set-emoji",
    "set-message",
    "reset-work",
    "reset-dealer",
}


def is_admin_interaction(interaction):
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


async def ensure_admin_interaction(interaction):
    if is_admin_interaction(interaction):
        return True

    message = "У вас недостаточно прав. Требуется право Администратор."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
    return False


def is_all_target(value):
    return str(value).strip().casefold() in ALL_TARGET_ALIASES


def parse_member_id(value):
    text = str(value).strip()
    mention_match = re.fullmatch(r"<@!?(\d{15,25})>", text)
    if mention_match:
        return int(mention_match.group(1))
    if text.isdigit():
        return int(text)
    return None


async def resolve_member_text(interaction, value):
    if isinstance(value, discord.Member):
        return value

    if interaction.guild is None:
        return None

    text = str(value).strip()
    member_id = parse_member_id(text)
    if member_id is not None:
        member = interaction.guild.get_member(member_id)
        if member is not None:
            return member
        try:
            return await interaction.guild.fetch_member(member_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    normalized = text.casefold()
    for member in interaction.guild.members:
        names = {
            member.name.casefold(),
            member.display_name.casefold(),
            str(member).casefold(),
        }
        global_name = getattr(member, "global_name", None)
        if global_name:
            names.add(global_name.casefold())
        if normalized in names:
            return member
    return None


async def resolve_admin_targets(interaction, value):
    if is_all_target(value):
        if interaction.guild is None:
            return [], True, "Команда `all` доступна только на сервере."
        members = [member for member in interaction.guild.members if not member.bot]
        if not members:
            return [], True, "Не нашёл участников для массовой операции."
        return members, True, None

    member = await resolve_member_text(interaction, value)
    if member is None:
        return [], False, "Не нашёл участника. Укажите `all`, ID, упоминание или точное имя."
    return [member], False, None


def format_target_result(targets, is_all):
    if is_all:
        return f"**{format_integer(len(targets))} участников**"
    return targets[0].mention


async def role_key_autocomplete(interaction: discord.Interaction, current: str):
    normalized = normalize_role_name(current)
    choices = []
    for role_definition in ROLE_DEFINITIONS:
        search_values = [
            role_definition["key"],
            role_definition["name"],
            *role_definition.get("aliases", []),
        ]
        if normalized and not any(
            normalized in normalize_role_name(value) for value in search_values
        ):
            continue
        choices.append(
            app_commands.Choice(
                name=f"{role_definition['emoji']} {role_definition['name']}",
                value=role_definition["key"],
            )
        )
    return choices[:25]


async def role_name_autocomplete(interaction: discord.Interaction, current: str):
    normalized = normalize_role_name(current)
    choices = []
    for role_definition in ROLE_DEFINITIONS:
        search_values = [
            role_definition["key"],
            role_definition["name"],
            *role_definition.get("aliases", []),
        ]
        if normalized and not any(
            normalized in normalize_role_name(value) for value in search_values
        ):
            continue
        choices.append(
            app_commands.Choice(
                name=f"{role_definition['emoji']} {role_definition['name']}",
                value=role_definition["name"],
            )
        )

    guild = interaction.guild
    if guild is not None:
        existing = {choice.value.casefold() for choice in choices}
        for role in guild.roles:
            if normalized and normalized not in normalize_role_name(role.name):
                continue
            if role.name.casefold() in existing or role.is_default():
                continue
            choices.append(app_commands.Choice(name=role.name[:100], value=role.name))
            if len(choices) >= 25:
                break
    return choices[:25]


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


async def emoji_target_autocomplete(interaction: discord.Interaction, current: str):
    normalized = normalize_role_name(current)
    matches = []
    for name, value in EMOJI_TARGETS:
        if normalized and normalized not in normalize_role_name(name) and normalized not in value:
            continue
        matches.append(app_commands.Choice(name=name, value=value))
    return matches[:25]


async def bind_economy_context(interaction: discord.Interaction):
    set_economy_guild_id(interaction.guild_id)
    
    if interaction.type == discord.InteractionType.autocomplete:
        return True

    command_name = getattr(getattr(interaction, "command", None), "name", None)
    if command_name in ADMIN_COMMAND_NAMES and not is_admin_interaction(interaction):
        await ensure_admin_interaction(interaction)
        return False
        
    if interaction.guild and interaction.type == discord.InteractionType.application_command:
        if command_name != "command-chat":
            cog = bot.get_cog("LevelingCog")
            if cog:
                import json
                guild_id = str(interaction.guild.id)
                allow_all = cog.db.get_setting(guild_id, "allow_all_channels", "false") == "true"
                if not allow_all:
                    raw = cog.db.get_setting(guild_id, "command_channels", "[]")
                    try:
                        allowed = json.loads(raw)
                    except Exception:
                        allowed = []
                    if allowed and interaction.channel.id not in allowed:
                        channels_str = ", ".join(f"<#{c}>" for c in allowed)
                        await interaction.response.send_message(f"Команды можно использовать только в этих каналах: {channels_str}", ephemeral=True)
                        return False

    if interaction.guild and interaction.type == discord.InteractionType.application_command and command_name:
        asyncio.create_task(
            send_guild_log(
                interaction.guild,
                "command",
                f"{interaction.user.mention} использовал `/{command_name}` в {interaction.channel.mention}",
                color=discord.Color.blurple(),
            )
        )

    return True

bot.tree.interaction_check = bind_economy_context


def build_roles_embed(guild, member=None, account=None):
    embed = discord.Embed(
        title="Роли",
        description=get_custom_message("roles_description"),
        color=discord.Color.gold(),
    )
    if os.path.exists(ROLE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{ROLE_IMAGE_ATTACHMENT_NAME}")

    for role_definition in ROLE_DEFINITIONS:
        role = find_guild_role(guild, role_definition)
        icon = get_role_icon(role_definition, role)
        owns_role = (
            member is not None
            and has_game_role(member, role_definition["key"], account)
        )
        if owns_role:
            status = f"{icon} Куплено"
        else:
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

    embed.set_footer(text=get_custom_message("roles_footer"))
    return embed


def build_balance_embed(guild, member, account, rate):
    cash = account["cash"]
    gold = account["gold"]
    treasure_maps = account["treasure_maps"]
    role_sections = format_balance_role_sections(guild, member, account)
    gang_section = format_balance_gang_section(member, account)
    property_section = format_balance_property_section(account)

    inventory = account.get("inventory", {})
    if not isinstance(inventory, dict):
        inventory = {}
    try:
        has_safe = float(inventory.get("safe", 0)) > 0
    except (TypeError, ValueError):
        has_safe = False
    try:
        safe_cash = max(0.0, float(account.get("safe_cash", 0.0)))
    except (TypeError, ValueError):
        safe_cash = 0.0
    try:
        safe_gold = max(0.0, float(account.get("safe_gold", 0.0)))
    except (TypeError, ValueError):
        safe_gold = 0.0
    if has_safe:
        safe_line = (
            f"├─ {get_safe_emoji()} Сейф: "
            f"{format_number(safe_cash)} {get_cash_emoji()} / "
            f"{format_number(safe_gold)} {get_gold_emoji()}"
        )
    else:
        safe_line = (
            f"├─ {get_lock_emoji()} {get_safe_emoji()} Сейф не куплен · `/catalog`"
        )

    fin_emoji = economy_data.get("balance_ui_finance", DEFAULT_BALANCE_FINANCE_EMOJI)
    roles_emoji = economy_data.get("balance_ui_roles", DEFAULT_BALANCE_ROLES_EMOJI)
    eco_emoji = economy_data.get("balance_ui_economy", DEFAULT_BALANCE_ECONOMY_EMOJI)

    description = (
        f"{fin_emoji} Финансы\n"
        f"├─ {get_cash_emoji()} Деньги: {format_money_plain(cash)}\n"
        f"├─ {get_gold_emoji()} Золото: {format_gold_plain(gold)}\n"
        f"{safe_line}\n"
        f"└─ {get_map_emoji()} Карты: {format_treasure_maps_plain(treasure_maps)}\n\n"
        f"{gang_section}\n\n"
        f"{roles_emoji} Профессии\n"
        f"{role_sections}\n"
        f"\n{property_section}\n\n"
        "🧭 Активности\n"
        "├─ Заработок: `/work` · ограбление: `/rob`\n"
        f"├─ Раскопки: {'`/excavation`' if treasure_maps > 0 else f'{get_lock_emoji()} нужна карта сокровищ'}\n"
        "└─ Игры: `/dice` · `/poker` · `/blackjack`\n\n"
        f"{eco_emoji} Экономика\n"
        f"└─ Курс: 1 {get_gold_emoji()} = {format_exchange_rate(rate)}"
    )
    embed = discord.Embed(
        title=f"{get_stats_emoji()}Статистика: {member.display_name}",
        description=description,
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(BALANCE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{BALANCE_IMAGE_ATTACHMENT_NAME}")
    embed.set_footer(text="Закрытые профессии открываются через /roles.")
    return embed


async def buy_game_role(interaction, role_key):
    role_definition = get_role_definition(role_key)
    if role_definition is None:
        await interaction.response.send_message("Эта роль не найдена.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    token = set_economy_guild_id(interaction.guild_id)
    try:
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
            try:
                role = await interaction.guild.create_role(
                    name=get_role_display_name(role_definition),
                    color=ROLE_DISPLAY_COLOR,
                    reason="WildWest bot: автосоздание игровой роли при покупке",
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                await interaction.followup.send(
                    f"На сервере нет роли **{role_definition['name']}** и не удалось её создать: {e}. "
                    "Администратор может использовать `/restart-roles`.",
                    ephemeral=True,
                )
                return

        if (
            role not in member.roles
            and hasattr(role, "is_assignable")
            and not role.is_assignable()
        ):
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
            already_owned = role_key in account["owned_roles"] or role in member.roles

            if already_owned:
                add_owned_role(account, role_key)
                save_economy()
            else:
                paid_price = get_role_price(role)
                if account['gold'] + 0.0001 < paid_price:
                    save_economy()
                    await interaction.followup.send(
                        f"Недостаточно золота. Нужно **{format_role_price(paid_price)}**, "
                        f"а у вас **{format_gold(account.get('gold', 0.0))}**.",
                        ephemeral=True,
                    )
                    return
                else:
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
    finally:
        reset_economy_guild_id(token)

class RoleBuyButton(discord.ui.Button):
    def __init__(self, role_definition, guild, member=None, account=None):
        role = find_guild_role(guild, role_definition)
        price = get_role_price(role)
        icon = get_role_icon(role_definition, role)
        owns_role = (
            member is not None
            and has_game_role(member, role_definition["key"], account)
        )

        if owns_role:
            label = "Куплено"
            style = discord.ButtonStyle.secondary
            disabled = True
            emoji_to_use = icon or None

        elif role_definition["available"]:
            label = f"Купить за {format_gold_price_value(price)}"
            style = discord.ButtonStyle.success
            disabled = False

            # Иконка роли → приоритет, иначе золотой эмодзи
            if icon:
                emoji_to_use = icon
            else:
                gold_raw = get_gold_emoji()
                try:
                    emoji_to_use = discord.PartialEmoji.from_str(gold_raw)
                except Exception:
                    emoji_to_use = gold_raw  # стандартный символ (🟡) сработает

        else:
            label = "Пока недоступно"
            style = discord.ButtonStyle.secondary
            disabled = True
            emoji_to_use = icon or None

        super().__init__(
            label=label,
            style=style,
            emoji=emoji_to_use,
            disabled=disabled,
            custom_id=f"role_shop:{role_definition['key']}",
        )
        self.role_key = role_definition["key"]

    async def callback(self, interaction):
        await buy_game_role(interaction, self.role_key)
class RoleShopView(discord.ui.View):
    def __init__(self, guild, member=None, account=None):
        super().__init__(timeout=600)
        for role_definition in ROLE_DEFINITIONS:
            self.add_item(RoleBuyButton(role_definition, guild, member, account))

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
        return True

def build_help_pages(is_admin):
    pages = {}

    # 1. Overview
    overview = discord.Embed(
        title="Справка бота",
        description=(
            "Добро пожаловать на Дикий Запад! Бот предоставляет систему экономики, "
            "профессий, банд, а также мини-игры и торговлю.\n\n"
            "Используйте выпадающее меню ниже, чтобы выбрать нужную категорию команд."
        ),
        color=discord.Color.gold(),
    )
    overview.add_field(
        name="Быстрый старт",
        value=(
            "`/balance`, `/work`, `/roles`, `/gang-info`, `/bounty`, `/naturalist`"
        ),
        inline=False,
    )
    pages["overview"] = {
        "label": "Обзор",
        "description": "Главная страница справки",
        "emoji": "📖",
        "embed": overview
    }

    # 2. Economy
    economy = discord.Embed(
        title="Справка: Экономика и Действия",
        description="Основные команды для заработка и траты денег.",
        color=discord.Color.gold(),
    )
    economy.add_field(
        name="Деньги и Золото",
        value=(
            "`/balance` — показать ваш баланс, карты, повозку и витрину.\n"
            "`/work` — заработать деньги (кулдаун 2 часа).\n"
            "`/gold-rate` — показать текущий курс золота.\n"
            "`/buy-gold` / `/sell-gold` — обмен валюты."
        ),
        inline=False,
    )
    economy.add_field(
        name="Магазин и Взаимодействия",
        value=(
            "`/catalog` — открыть каталог товаров Wheeler, Rawson & Co.\n"
            "`/safe-money` / `/safe-take-money` — использование личного сейфа.\n"
            "`/rob` — ограбить другого игрока (риск штрафа, кулдаун 2 часа).\n"
            "`/send` — отправить личное сообщение через бота."
        ),
        inline=False,
    )
    pages["economy"] = {
        "label": "Экономика и Действия",
        "description": "Баланс, работа, магазин, банк и ограбления",
        "emoji": "💰",
        "embed": economy
    }

    # 3. Roles
    roles = discord.Embed(
        title="Справка: Роли и Профессии",
        description="Команды профессий и заработка.",
        color=discord.Color.gold(),
    )
    roles.add_field(
        name="Доступные профессии",
        value=(
            "`/roles` — список профессий с описаниями и кнопками покупки.\n"
            "`/dealer` / `/dealer-delivery` — заполнение и доставка повозки торговца.\n"
            "`/moonshine` — варка и продажа самогона, прокачка аппарата.\n"
            "`/bounty` / `/bounty-leaderboard` — охота за головами и доска почета.\n"
            "`/naturalist` — справочник животных и сбор образцов."
        ),
        inline=False,
    )
    roles.add_field(
        name="Карты сокровищ",
        value=(
            "`/excavation` — потратить карту и попытаться найти клад.\n"
            "Карты выдаются во время ежедневных ивентов."
        ),
        inline=False,
    )
    pages["roles"] = {
        "label": "Роли и Профессии",
        "description": "Торговец, Самогонщик, Охотник, Натуралист",
        "emoji": "🤠",
        "embed": roles
    }

    # 4. Gangs
    gangs = discord.Embed(
        title="Справка: Банды",
        description="Объединяйтесь с другими игроками в банды.",
        color=discord.Color.gold(),
    )
    gangs.add_field(
        name="Управление бандой",
        value=(
            "`/gang` — панель управления бандой (для лидера — полное меню).\n"
            "`/gang-create` — создать банду (цена: 50 золота).\n"
            "`/gang-info` — статистика банды.\n"
            "`/gang-join` / `/gang-leave` — вступление и выход."
        ),
        inline=False,
    )
    gangs.add_field(
        name="Общак и Войны",
        value=(
            "`/gang-deposit` / `/gang-withdraw` — пополнение и снятие денег из общака.\n"
            "`/gang-rob` — ограбить общак чужой банды."
        ),
        inline=False,
    )
    pages["gangs"] = {
        "label": "Банды",
        "description": "Создание банд, общак, войны и управление",
        "emoji": "🔫",
        "embed": gangs
    }

    # 5. Games
    games = discord.Embed(
        title="Справка: Игры",
        description="Испытайте удачу в казино.",
        color=discord.Color.gold(),
    )
    games.add_field(
        name="Доступные игры",
        value=(
            "`/dice bet` — кости против бота.\n"
            "`/poker bet` — 5-карточный покер с заменой карт.\n"
            "`/blackjack` — блэкджек с дилером."
        ),
        inline=False,
    )
    pages["games"] = {
        "label": "Игры",
        "description": "Кости, покер, блэкджек",
        "emoji": "🎲",
        "embed": games
    }

    # 5.5. Miner
    miner = discord.Embed(
        title="Справка: Шахтёр",
        description="Мини-игра «Глубокая жила» — копайте породу, добывайте руду и создавайте украшения.",
        color=discord.Color.gold(),
    )
    miner.add_field(
        name="Основные команды",
        value=(
            "`/mine` — копать один куб породы (лимит 3 в день).\n"
            "`/mine-status` — глубина, инвентарь, состояние инструмента.\n"
            "`/mine-buy` — купить расходники и кирки в лавке."
        ),
        inline=False,
    )
    miner.add_field(
        name="Торговля и ремесло",
        value=(
            "`/mine-sell` — продать руду, слитки, находки, камни, украшения в факторию.\n"
            "`/mine-smelt` — переплавить руду в слитки у кузнеца.\n"
            "`/mine-forge` — отдать слиток + камень ювелиру для создания украшения."
        ),
        inline=False,
    )
    pages["miner"] = {
        "label": "Шахтёр",
        "description": "Копка, руда, слитки и украшения",
        "emoji": "⛏️",
        "embed": miner
    }

    # 6. Admin
    admin = discord.Embed(
        title="Справка: Админ-команды",
        description="Команды управления сервером и экономикой.",
        color=discord.Color.gold(),
    )
    if is_admin:
        admin.add_field(
            name="Основные",
            value="`/check`, `/give-money`, `/remove-money`, `/set-money`, `/give-gold` и т.д.",
            inline=False,
        )
        admin.add_field(
            name="Профессии",
            value="`/fill-dealer`, `/give-moonshine-ingredient`, `/set-moonshine-upgrade`, `/set-moonshine-skill`, `/finish-moonshine`, `/reset-moonshine`",
            inline=False,
        )
        admin.add_field(
            name="Банды (Админ)",
            value="`/gang-admin` — админ-панель управления бандами сервера.",
            inline=False,
        )
        admin.add_field(
            name="Настройки и ивенты",
            value="`/treasure-event`, `/set-discount-shop`, `/set-rate`, `/set-emoji`, `/set-message`, `/set-icon-roles`, `/set-discounts-roles`",
            inline=False,
        )
    else:
        admin.add_field(
            name="Недоступно",
            value="У вас нет прав администратора для просмотра этих команд.",
            inline=False,
        )
    pages["admin"] = {
        "label": "Админ-команды",
        "description": "Настройки и управление ботом",
        "emoji": "⚙️",
        "embed": admin
    }

    # Add banner to all pages if exists
    for key, data in pages.items():
        if os.path.exists(TREASURE_BANNER_FILE):
            data["embed"].set_image(url=f"attachment://{TREASURE_BANNER_FILE}")

    return pages


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, pages):
        self.pages = pages
        options = []
        for key, data in pages.items():
            options.append(
                discord.SelectOption(
                    label=data["label"],
                    description=data["description"],
                    emoji=data["emoji"],
                    value=key
                )
            )
        super().__init__(placeholder="Выберите категорию команд...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_key = self.values[0]
        selected_page = self.pages[selected_key]["embed"]
        await interaction.response.edit_message(embed=selected_page, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=600)
        self.pages = pages
        self.add_item(HelpCategorySelect(pages))


def validate_bet(amount):
    if amount is None:
        return 0.0, None
    if not math.isfinite(amount) or amount < 0:
        return 0.0, "Ставка должна быть числом от нуля и выше."
    return round(float(amount), 2), None


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
        get_custom_message("role_required").format(role="Самогонщик"),
        ephemeral=True,
    )
    return None


async def deliver_moonshine_batch(interaction):
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

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

    async def on_error(self, interaction, error, item):
        logging.error(
            "Moonshine UI failed for user=%s guild=%s item=%s",
            getattr(interaction.user, "id", None),
            interaction.guild_id,
            getattr(item, "custom_id", type(item).__name__),
            exc_info=(type(error), error, error.__traceback__),
        )
        try:
            await send_interaction_response(
                interaction,
                "Не удалось выполнить действие самогонщика. "
                "Откройте `/moonshine` заново и повторите.",
                ephemeral=True,
            )
        except discord.HTTPException:
            pass


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
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        recipe = get_moonshine_mash_recipe(self.values[0])
        if recipe is None:
            await send_embed_response(
                interaction,
                "Рецепт устарел",
                "Откройте `/moonshine` заново и повторите выбор.",
                ephemeral=True,
            )
            return

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
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if self.values[0] == "none":
            await send_embed_response(
                interaction,
                "Нет рецептов",
                "**Марсель:** Пока нет доступных особых рецептов.",
                ephemeral=True,
            )
            return

        recipe = get_moonshine_special_recipe(self.values[0])
        if recipe is None:
            await send_embed_response(
                interaction,
                "Рецепт устарел",
                "Откройте `/moonshine` заново и повторите выбор.",
                ephemeral=True,
            )
            return

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
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            if moonshine.get("has_condenser"):
                save_economy()
                await send_interaction_response(
                    interaction,
                    "Конденсатор уже куплен.", ephemeral=True
                )
                return

            if account["cash"] + 0.0001 < MOONSHINE_CONDENSER_PRICE:
                save_economy()
                await send_interaction_response(
                    interaction,
                    f"Не хватает денег. Нужно **{format_money(MOONSHINE_CONDENSER_PRICE)}**, "
                    f"у вас **{format_money(account['cash'])}**.",
                    ephemeral=True,
                )
                return

            account["cash"] -= MOONSHINE_CONDENSER_PRICE
            moonshine["has_condenser"] = True
            set_moonshine_level(moonshine, 2)
            save_economy()

        await send_interaction_response(
            interaction,
            "Конденсатор куплен. Открыт самогон **2 уровня**.",
            ephemeral=True,
        )

    @discord.ui.button(label="Медный дистиллятор $875", style=discord.ButtonStyle.success)
    async def distiller_button(self, interaction, button):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            if moonshine.get("has_distiller"):
                save_economy()
                await send_interaction_response(
                    interaction,
                    "Медный дистиллятор уже куплен.", ephemeral=True
                )
                return

            if not moonshine.get("has_condenser"):
                save_economy()
                await send_interaction_response(
                    interaction,
                    "Сначала купите конденсатор для 2 уровня.", ephemeral=True
                )
                return

            if account["cash"] + 0.0001 < MOONSHINE_DISTILLER_PRICE:
                save_economy()
                await send_interaction_response(
                    interaction,
                    f"Не хватает денег. Нужно **{format_money(MOONSHINE_DISTILLER_PRICE)}**, "
                    f"у вас **{format_money(account['cash'])}**.",
                    ephemeral=True,
                )
                return

            account["cash"] -= MOONSHINE_DISTILLER_PRICE
            moonshine["has_distiller"] = True
            set_moonshine_level(moonshine, 3)
            save_economy()

        await send_interaction_response(
            interaction,
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
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            embed = build_moonshine_mash_embed(moonshine)
            view = MoonshineMashView(interaction.user.id, moonshine)
            save_economy()

        image = get_moonshine_image_file()
        if image:
            await interaction.followup.send(
                embed=embed, view=view, file=image, ephemeral=True
            )
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Добавить особые ингредиенты", style=discord.ButtonStyle.primary, row=0)
    async def special_button(self, interaction, button):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        async with economy_lock:
            account = get_account(interaction.user.id)
            moonshine = get_moonshine_account(account)
            embed = build_moonshine_special_embed(moonshine)
            view = MoonshineSpecialView(interaction.user.id, moonshine)
            save_economy()

        image = get_moonshine_image_file()
        if image:
            await interaction.followup.send(
                embed=embed, view=view, file=image, ephemeral=True
            )
        else:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Купить улучшения", style=discord.ButtonStyle.secondary, row=0)
    async def upgrades_button(self, interaction, button):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

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
            await interaction.followup.send(
                embed=embed,
                view=MoonshineUpgradeView(interaction.user.id),
                file=image,
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=embed,
                view=MoonshineUpgradeView(interaction.user.id),
                ephemeral=True,
            )

    @discord.ui.button(label="Отвезти повозку", style=discord.ButtonStyle.success, row=0)
    async def deliver_button(self, interaction, button):
        await deliver_moonshine_batch(interaction)

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction, button):
        if not interaction.response.is_done():
            await interaction.response.defer()

        async with economy_lock:
            account = get_account(interaction.user.id)
            embed = build_moonshine_embed(interaction.guild, account)
            save_economy()

        await interaction.edit_original_response(
            embed=embed, view=MoonshineMainView(interaction.user.id)
        )














































@tasks.loop(time=time(hour=12, minute=0, tzinfo=MSK_TZ))
async def daily_treasure_map_event():
    for guild_id in economy_data.configured_treasure_guild_ids():
        guild = bot.get_guild(int(guild_id)) if str(guild_id).isdigit() else None
        token = set_economy_guild_id(guild_id)
        try:
            try:
                granted_count, channel, skipped = await run_treasure_map_event(
                    scheduled=True, guild=guild
                )
            except discord.HTTPException as e:
                logging.info(
                    "Ежедневная выдача карт сохранена, но объявление не отправилось "
                    f"для сервера {guild_id}: {e}"
                )
                continue

            if skipped:
                continue

            if channel is None:
                logging.info(
                    "Ежедневная карта сокровищ выдана, но канал объявлений не настроен "
                    f"или недоступен. Сервер: {guild_id}; игроков: {granted_count}"
                )
        finally:
            reset_economy_guild_id(token)


@daily_treasure_map_event.before_loop
async def before_daily_treasure_map_event():
    await bot.wait_until_ready()


@tasks.loop(minutes=5)
async def periodic_economy_save():
    async with economy_lock:
        save_economy()


@periodic_economy_save.before_loop
async def before_periodic_economy_save():
    await bot.wait_until_ready()


async def sync_commands():
    """Register slash commands so they appear in Discord's input suggestions."""
    guilds = bot.guilds

    # Мы убрали очистку глобальных команд, так как bot.tree.clear_commands 
    # удаляет их из локальной памяти бота, из-за чего copy_global_to копировал 0 команд!

    # Копируем команды на каждый сервер (появляются моментально)
    for guild in guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            guild_commands = await bot.tree.sync(guild=guild)
            logging.info(f"Команды синхронизированы моментально для сервера '{guild.name}': {len(guild_commands)}")
        except Exception as e:
            logging.error(f"Синхронизация команд не удалась для сервера '{guild.name}': {e}")


@bot.event
async def on_ready():
    global COMMANDS_SYNCED

    logging.info(f"Бот {bot.user.name} запущен!")
    
    # Установка статуса бота
    try:
        # Читаем версию свежо из config.json при каждом запуске,
        # чтобы update_version.py сразу давал эффект без правки BOT_VERSION вручную
        config.sync()
        live_version = (config.get("version") or BOT_VERSION or "v0.0.0").lstrip("v")
        if hasattr(discord, "CustomActivity"):
            activity = discord.CustomActivity(name=f"pchev.me {live_version}")
        else:
            activity = discord.Activity(type=discord.ActivityType.custom, name=f"pchev.me {live_version}")
        await bot.change_presence(status=discord.Status.online, activity=activity)
    except Exception as e:
        logging.error(f"Не удалось установить статус: {e}")

    if not daily_treasure_map_event.is_running():
        daily_treasure_map_event.start()
    if not periodic_economy_save.is_running():
        periodic_economy_save.start()

    # Создать/обновить игровые роли на всех серверах при запуске бота
    for guild in bot.guilds:
        try:
            await ensure_guild_roles(guild)
        except Exception as e:
            logging.error(f"ensure_guild_roles при запуске не удалось для '{guild.name}': {e}")

    if COMMANDS_SYNCED:
        return

    try:
        await sync_commands()
        COMMANDS_SYNCED = True
    except Exception as e:
        logging.error(f"Command sync failed: {e}")


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
    guild_channels = get_guild_thread_channel_ids(interaction.guild.id)

    if channel_id in guild_channels:
        await interaction.response.send_message(
            f"Автоматические треды уже включены в {channel.mention}.",
            ephemeral=True,
        )
    else:
        guild_channels.add(channel_id)
        set_guild_thread_channel_ids(interaction.guild.id, guild_channels)
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
    guild_channels = get_guild_thread_channel_ids(interaction.guild.id)

    if channel_id in guild_channels:
        guild_channels.discard(channel_id)
        set_guild_thread_channel_ids(interaction.guild.id, guild_channels)
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


@bot.tree.command(name="news", description="Опубликовать новость через красивый Embed")
@app_commands.default_permissions(manage_guild=True)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(
    title="Главный заголовок новости",
    content="Основной текст новости (используйте \\n для переноса строк)",
    color="Цвет (название: red, blue, green, yellow и т.д. или HEX-код: #FF8800)",
    image="Изображение для новости"
)
async def news_command(
    interaction: discord.Interaction, 
    title: str, 
    content: str, 
    color: str = None, 
    image: discord.Attachment = None
):
    color_map = {
        "red": discord.Color.red(),
        "blue": discord.Color.blue(),
        "green": discord.Color.green(),
        "yellow": discord.Color.from_rgb(255, 255, 0),
        "purple": discord.Color.purple(),
        "orange": discord.Color.orange(),
        "pink": discord.Color.from_rgb(255, 192, 203),
        "black": discord.Color.from_rgb(0, 0, 0),
        "white": discord.Color.from_rgb(255, 255, 255),
        "blurple": discord.Color.blurple(),
        "grey": discord.Color.light_gray(),
        "gray": discord.Color.light_gray()
    }

    embed_color = discord.Color(0xff0000)
    if color:
        c_lower = color.lower().strip()
        if c_lower in color_map:
            embed_color = color_map[c_lower]
        elif c_lower.startswith("#"):
            hex_color = c_lower.lstrip("#")
            try:
                if len(hex_color) != 6:
                    raise ValueError
                embed_color = discord.Color(int(hex_color, 16))
            except ValueError:
                await interaction.response.send_message(f"❌ Некорректный HEX-код: `{color}`. Используйте формат, например, `#FF8800`.", ephemeral=True)
                return
        else:
            await interaction.response.send_message(f"❌ Неизвестный цвет: `{color}`. Укажите название цвета (например: red, blue) или HEX-код.", ephemeral=True)
            return

    actual_content = content.replace('\\n', '\n')
    lines = actual_content.split('\n')
    formatted_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('###'):
            header_text = stripped[3:].strip()
            formatted_lines.append(f"## {header_text}")
        elif stripped.startswith('##'):
            header_text = stripped[2:].strip()
            formatted_lines.append(f"### {header_text}")
        else:
            formatted_lines.append(line)
            
    final_content = '\n'.join(formatted_lines)

    embed = discord.Embed(title=title, description=final_content, color=embed_color)
    
    if image:
        if image.content_type and image.content_type.startswith('image/'):
            embed.set_image(url=image.url)
        else:
            await interaction.response.send_message("❌ Прикрепленный файл не является изображением.", ephemeral=True)
            return

    author_name = interaction.user.display_name
    author_icon = interaction.user.display_avatar.url if interaction.user.display_avatar else None
    embed.set_footer(text=f"Автор: {author_name}", icon_url=author_icon)
    embed.timestamp = discord.utils.utcnow()

    guild_data = economy_data.guild_data(interaction.guild_id)
    configured_channel_id = guild_data.get("news_channel_id")
    target_channel = None
    if configured_channel_id and interaction.guild:
        target_channel = interaction.guild.get_channel(int(configured_channel_id))

    if target_channel and target_channel.id != interaction.channel_id:
        try:
            await target_channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message(
                "Не удалось опубликовать новость: проверьте доступ бота к выбранному каналу.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"Новость опубликована в {target_channel.mention}.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(embed=embed)



@bot.tree.command(name="help", description="Показать возможности бота")
async def help_command(interaction: discord.Interaction):
    is_admin = False
    if isinstance(interaction.user, discord.Member):
        is_admin = interaction.user.guild_permissions.administrator

    pages = build_help_pages(is_admin)
    banner = get_treasure_banner_file()
    if banner:
        await interaction.response.send_message(
            embed=pages["overview"]["embed"], view=HelpView(pages), file=banner, ephemeral=True
        )
    else:
        await interaction.response.send_message(
            embed=pages["overview"]["embed"], view=HelpView(pages), ephemeral=True
        )


@bot.tree.command(name="roles", description="Показать игровые роли и купить доступные")
async def roles_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    async with economy_lock:
        remove_expired_role_discounts()
        account = get_account(interaction.user.id)
        save_economy()
        embed = build_roles_embed(interaction.guild, interaction.user, account)
        view = RoleShopView(interaction.guild, interaction.user, account)

    role_image = get_role_image_file()
    if role_image:
        await interaction.followup.send(
            embed=embed, view=view, file=role_image, ephemeral=True
        )
    else:
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


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
    dm_embed = build_bot_embed(
        "Личное сообщение",
        f"Отправитель: **{sender_name}** ({interaction.user.mention})\n\n{text}",
    )

    try:
        await member.send(embed=dm_embed)
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


async def perform_reset_all(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Эта команда доступна только на сервере.", ephemeral=True)
        return

    if not await ensure_admin_interaction(interaction):
        return

    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    guild_id = guild.id
    roles_to_remove = [
        role
        for role_definition in ROLE_DEFINITIONS
        if (role := find_guild_role(guild, role_definition)) is not None
    ]

    async with economy_lock:
        economy_data.reset_guild(guild_id)
        save_economy()

    removed_count = 0
    failed_count = 0
    for role in roles_to_remove:
        for member in list(guild.members):
            if role not in member.roles:
                continue
            try:
                await member.remove_roles(role, reason="Reset by admin via /reset-all")
                removed_count += 1
            except (discord.Forbidden, discord.HTTPException):
                failed_count += 1

    message = (
        "Сервер успешно сброшен: экономика обнулена, игровые роли удалены по возможности.\n"
        f"Удалений ролей: **{format_integer(removed_count)}**."
    )
    if failed_count:
        message += f"\nНе удалось удалить ролей: **{format_integer(failed_count)}**."
    await interaction.followup.send(message, ephemeral=True)


class ResetAllConfirmModal(discord.ui.Modal):
    def __init__(self, requester_id):
        super().__init__(title="Подтверждение полного сброса")
        self.requester_id = requester_id
        self.confirmation = discord.ui.TextInput(
            label="Фраза подтверждения",
            placeholder="Я знаю что я делаю / I know what I'm doing",
            max_length=64,
            required=True,
        )
        self.add_item(self.confirmation)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message(
                "Это подтверждение открыто не для вас.", ephemeral=True
            )
            return

        if str(self.confirmation.value).strip() not in RESET_CONFIRMATION_PHRASES:
            await interaction.response.send_message(
                "Подтверждение неверно. Сброс отменён.", ephemeral=True
            )
            return

        await perform_reset_all(interaction)


class ResetAllConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Ввести подтверждение",
            style=discord.ButtonStyle.danger,
            custom_id="reset_all:confirm",
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id != view.requester_id:
            await interaction.response.send_message(
                "Это подтверждение открыто не для вас.", ephemeral=True
            )
            return
        if not await ensure_admin_interaction(interaction):
            return
        await interaction.response.send_modal(ResetAllConfirmModal(view.requester_id))


class ResetAllConfirmView(discord.ui.View):
    def __init__(self, requester_id):
        super().__init__(timeout=120)
        self.requester_id = requester_id
        self.add_item(ResetAllConfirmButton())


@bot.tree.command(
    name="reset-all",
    description="Полный сброс сервера: обнуление экономики и удаление игровых ролей",
)
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def reset_all_command(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Эта команда доступна только на сервере.", ephemeral=True)
        return

    if not await ensure_admin_interaction(interaction):
        return

    embed = build_bot_embed(
        "Полный сброс сервера",
        (
            f"{get_custom_message('reset_prompt')}\n\n"
            "Будут обнулены деньги, золото, карты, профессии, прогресс ролей, "
            "самогон, натуралист, охотник и настройки экономики этого сервера. "
            "Игровые Discord-роли будут удалены у участников по возможности."
        ),
        color=discord.Color.red(),
    )
    await interaction.response.send_message(
        embed=embed, view=ResetAllConfirmView(interaction.user.id), ephemeral=True
    )


@bot.tree.command(
    name="delete-role",
    description="Удалить одну игровую роль у участника (внутренняя игровая покупка и Discord-роль)",
)
@app_commands.describe(member="Участник", role_key="Ключ роли (например: bounty_hunter, trader)")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.autocomplete(role_key=role_key_autocomplete)
async def delete_role_command(interaction: discord.Interaction, member: discord.Member, role_key: str):
    if interaction.guild is None:
        await interaction.response.send_message("Эта команда доступна только на сервере.", ephemeral=True)
        return

    role_definition = get_role_definition(role_key)
    if role_definition is None:
        # Try matching by name
        rd = find_role_definition_by_name(role_key)
        if rd is None:
            await interaction.response.send_message(
                "Роль не найдена. Укажите ключ роли (например: bounty_hunter, trader, moonshiner, naturalist).",
                ephemeral=True,
            )
            return
        role_definition = rd

    await interaction.response.defer(ephemeral=True)

    async with economy_lock:
        account = get_account(member.id)
        if role_definition["key"] in account.get("owned_roles", []):
            try:
                account["owned_roles"].remove(role_definition["key"])
            except ValueError:
                pass
        save_economy()

    # Remove the Discord role object if present on the guild member
    discord_role = find_guild_role(interaction.guild, role_definition)
    if discord_role is not None:
        try:
            if discord_role in member.roles:
                await member.remove_roles(discord_role, reason="Role removed by admin via /delete-role")
        except discord.Forbidden:
            await interaction.followup.send("Не хватает прав, чтобы удалить Discord-роль у участника.", ephemeral=True)
            return

    await interaction.followup.send(f"Роль '{role_definition['name']}' удалена у {member.mention} (игровая покупка и Discord-роль обновлены).", ephemeral=True)


@bot.tree.command(
    name="restart-roles",
    description="Проверить и пересоздать игровые роли WildWest на сервере",
)
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def restart_roles_command(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Эта команда доступна только на сервере.", ephemeral=True)
        return

    if not await ensure_admin_interaction(interaction):
        return

    await interaction.response.defer(ephemeral=True)

    try:
        result = await ensure_guild_roles(interaction.guild)
    except Exception as e:
        await interaction.followup.send(f"Ошибка при пересоздании ролей: {e}", ephemeral=True)
        return

    lines = []
    if result["created"]:
        lines.append(f"✅ Создано ({len(result['created'])}): " + ", ".join(f"**{n}**" for n in result["created"]))
    if result["updated"]:
        lines.append(f"🔄 Обновлено ({len(result['updated'])}): " + ", ".join(f"**{n}**" for n in result["updated"]))
    if result["skipped"]:
        lines.append(f"⏭️ Без изменений: {len(result['skipped'])} шт.")
    if result.get("assigned"):
        lines.append(f"👤 Выдано заголовочных ролей участникам: **{result['assigned']}**")
    if result["errors"]:
        lines.append("❌ Ошибки:\n" + "\n".join(result["errors"]))
    if not lines:
        lines.append("Все роли уже в порядке.")

    await interaction.followup.send("\n".join(lines), ephemeral=True)


@bot.tree.command(name="balance", description="Показать ваш баланс")
async def balance_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with economy_lock:
        rate = update_gold_rate()
        account = get_account(interaction.user.id)
        save_economy()

        embed = build_balance_embed(interaction.guild, interaction.user, account, rate)

    balance_image = get_balance_image_file()
    if balance_image:
        await interaction.followup.send(embed=embed, file=balance_image, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="work", description="Заработать случайную сумму денег")
async def work_command(interaction: discord.Interaction):
    await interaction.response.defer()
    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        cooldown = get_work_cooldown(account)

        if cooldown > 0:
            save_economy()
            message = (
                "Вы недавно работали. "
                f"Вы сможете снова работать через **{format_duration(cooldown)}**."
            )
            await interaction.followup.send(message, ephemeral=True)
            return

        reward = random_work_reward()
        scenario = random_work_scenario()
        account["cash"] += reward
        account["last_work_at"] = now_local().isoformat(timespec="seconds")
        save_economy()

    message_template = get_custom_message("work_success")
    await interaction.followup.send(
        message_template.format(
            mention=interaction.user.mention,
            reward=format_money(reward),
            scenario=scenario,
        )
    )


@bot.tree.command(name="dice", description="Сыграть в кости с ботом")
@app_commands.describe(bet="Ставка деньгами. 0 — без ставки")
async def dice_command(interaction: discord.Interaction, bet: float = 0.0):
    await interaction.response.defer(ephemeral=True)
    bet, error = validate_bet(bet)
    if error:
        await interaction.followup.send(error, ephemeral=True)
        return

    player_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)

    async with economy_lock:
        account = get_account(interaction.user.id)
        if account["cash"] + 0.0001 < bet:
            save_economy()
            await interaction.followup.send(
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

    await interaction.followup.send(
        f"🎲 {interaction.user.mention}: **{player_roll}**\n"
        f"🎲 Бот: **{bot_roll}**\n"
        f"{result}",
        ephemeral=True
    )
    if player_roll > bot_roll and bet >= 100:
        await interaction.channel.send(
            f"🎉 {interaction.user.mention} только что выиграл **{format_money(bet)}** в кости!"
        )


@bot.tree.command(name="poker", description="Сыграть 5-карточный покер с ботом")
@app_commands.describe(bet="Ставка деньгами. 0 — без ставки")
async def poker_command(interaction: discord.Interaction, bet: float = 0.0):
    await interaction.response.defer(ephemeral=True)
    bet, error = validate_bet(bet)
    if error:
        await interaction.followup.send(error, ephemeral=True)
        return

    deck = build_card_deck()
    random.shuffle(deck)
    player_hand = [deck.pop() for _ in range(5)]
    bot_hand = [deck.pop() for _ in range(5)]
    player_score, player_name = evaluate_poker_hand(player_hand)
    bot_score, bot_name = evaluate_poker_hand(bot_hand)

    async with economy_lock:
        account = get_account(interaction.user.id)
        if account["cash"] + 0.0001 < bet:
            save_economy()
            await interaction.followup.send(
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

    await interaction.followup.send(
        f"🃏 {interaction.user.mention}: **{format_cards(player_hand)}** — {player_name}\n"
        f"🃏 Бот: **{format_cards(bot_hand)}** — {bot_name}\n"
        f"{result}",
        ephemeral=True
    )
    if player_score > bot_score and bet >= 100:
        await interaction.channel.send(
            f"🎉 {interaction.user.mention} только что выиграл **{format_money(bet)}** в покер!"
        )


def build_treasure_hunt_embed(user, remaining_maps, attempts_left=2, note=None):
    description = (
        f"{user.mention}, карта привела вас к трём подозрительным местам.\n"
        f"Клад спрятан только под одной кнопкой. Попыток: **{attempts_left}**.\n"
        f"Карт осталось: **{format_treasure_maps(remaining_maps)}**."
    )
    if note:
        description += f"\n\n{note}"

    embed = build_bot_embed(
        "Раскопки",
        description,
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(TREASURE_BANNER_FILE):
        embed.set_image(url=f"attachment://{TREASURE_BANNER_FILE}")
    return embed


def build_treasure_result_embed(user, title, description):
    embed = build_bot_embed(
        title,
        f"{user.mention}, {description}",
        color=discord.Color.gold(),
    )
    if os.path.exists(TREASURE_BANNER_FILE):
        embed.set_image(url=f"attachment://{TREASURE_BANNER_FILE}")
    return embed


class TreasureDigButton(discord.ui.Button):
    def __init__(self, index):
        emoji = economy_data.get("treasure_dig_emoji", DEFAULT_TREASURE_DIG_EMOJI)
        super().__init__(
            label=f"Место {index + 1}",
            style=discord.ButtonStyle.primary,
            emoji=emoji,
            row=0,
        )
        self.index = index

    async def callback(self, interaction):
        view = self.view
        await view.dig(interaction, self)


class TreasureHuntView(discord.ui.View):
    def __init__(self, user_id, treasure_index, remaining_maps, guild_id=None):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.guild_id = guild_id
        self.treasure_index = treasure_index
        self.remaining_maps = remaining_maps
        self.attempts_used = 0
        self.finished = False
        self._is_digging = False
        for index in range(3):
            self.add_item(TreasureDigButton(index))

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.user_id:
            await send_embed_response(
                interaction,
                "Чужая карта",
                "Эта карта сокровищ открыта не для вас.",
                ephemeral=True,
            )
            return False
        return True

    def attempts_left(self):
        return max(0, 2 - self.attempts_used)

    def disable_all(self):
        for item in self.children:
            item.disabled = True

    def reveal_treasure(self):
        found_emoji = economy_data.get("treasure_found_emoji", DEFAULT_TREASURE_FOUND_EMOJI)
        for item in self.children:
            if item.index == self.treasure_index:
                item.emoji = found_emoji
                item.style = discord.ButtonStyle.success
            elif item.disabled:
                item.style = discord.ButtonStyle.danger

    async def grant_reward(self, interaction):
        cash_reward = random.randint(80, 200)
        gold_reward = round(random.uniform(0.5, 3.9), 2)

        # Явно устанавливаем guild_id: ContextVar сбрасывается после await asyncio.sleep,
        # поэтому без этого get_account() смотрит в "global" вместо реального сервера.
        guild_id = self.guild_id or interaction.guild_id
        token = set_economy_guild_id(guild_id)
        extra_map_granted = False
        try:
            async with economy_lock:
                account = get_account(interaction.user.id)
                ingredients_reward = grant_random_moonshine_ingredients(account)
                account["cash"] += cash_reward
                account["gold"] += gold_reward
                if random.random() < EXCAVATION_REWARD_CHANCE:
                    account["treasure_maps"] += 1
                    extra_map_granted = True
                remaining_maps = account["treasure_maps"]
                save_economy()
        finally:
            reset_economy_guild_id(token)

        ingredients_text = ", ".join(
            f"{get_ingredient_emoji(ingredient)} {ingredient} x{amount}"
            for ingredient, amount in sorted(ingredients_reward.items())
        ) or "нет"
        return cash_reward, gold_reward, ingredients_text, remaining_maps, extra_map_granted

    async def dig(self, interaction, button):
        if self.finished:
            await send_embed_response(
                interaction,
                "Раскопки завершены",
                "Эта карта уже разыграна.",
                ephemeral=True,
            )
            return

        if getattr(self, "_is_digging", False):
            await send_embed_response(
                interaction,
                "Копаем...",
                "Подождите, раскопки уже в процессе.",
                ephemeral=True,
            )
            return

        if button.disabled:
            await send_embed_response(
                interaction,
                "Уже проверено",
                "Это место уже раскопано. Выберите другое.",
                ephemeral=True,
            )
            return

        self._is_digging = True
        try:
            self.attempts_used += 1
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await asyncio.sleep(2)

            if button.index == self.treasure_index:
                found_emoji = economy_data.get("treasure_found_emoji", DEFAULT_TREASURE_FOUND_EMOJI)
                extra_emoji = economy_data.get("treasure_extra_emoji", DEFAULT_TREASURE_EXTRA_EMOJI)
                self.finished = True
                self.disable_all()
                button.emoji = found_emoji
                button.style = discord.ButtonStyle.success
                cash_reward, gold_reward, ingredients_text, remaining_maps, extra_map_granted = await self.grant_reward(interaction)
                
                result_text = (
                    f"вы нашли тайник! Получено: **{format_money(cash_reward)}** "
                    f"и **{format_gold(gold_reward)}**!\n"
                    f"Ингредиенты самогонщика: **{ingredients_text}**.\n"
                )
                if extra_map_granted:
                    result_text += f"{extra_emoji} **Вам повезло! Вы нашли дополнительную карту сокровищ!** {extra_emoji}\n"
                result_text += f"Карт осталось: **{format_treasure_maps(remaining_maps)}**."
                
                embed = build_treasure_result_embed(
                    interaction.user,
                    f"{found_emoji} Клад найден!",
                    result_text,
                )
                await interaction.edit_original_response(embed=embed, view=self)
                self.stop()
                return

            button.style = discord.ButtonStyle.danger
            if self.attempts_left() > 0:
                embed = build_treasure_hunt_embed(
                    interaction.user,
                    self.remaining_maps,
                    attempts_left=self.attempts_left(),
                    note="Под лопатой только камни и сухая земля. Осталась ещё одна попытка.",
                )
                await interaction.edit_original_response(embed=embed, view=self)
                return

            self.finished = True
            self.disable_all()
            self.reveal_treasure()
            embed = build_treasure_result_embed(
                interaction.user,
                "Клад ускользнул",
                (
                    "две попытки ушли в пустую землю. Крест на карте оказался точнее, "
                    "чем сегодняшняя удача."
                ),
            )
            await interaction.edit_original_response(embed=embed, view=self)
            self.stop()
        finally:
            self._is_digging = False

    async def on_timeout(self):
        if self.finished:
            return
        self.disable_all()
        self.finished = True
        self.stop()


@bot.tree.command(name="excavation", description="Использовать карту сокровищ для раскопок")
async def excavation_command(interaction: discord.Interaction):
    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)

        if account["treasure_maps"] <= 0:
            save_economy()
            await send_embed_response(
                interaction,
                "Нет карт",
                f"У вас нет {get_map_emoji()} карт сокровищ. Дождитесь ежедневной выдачи.",
                ephemeral=True,
            )
            return

        account["treasure_maps"] -= 1
        remaining_maps = account["treasure_maps"]
        save_economy()

    treasure_index = random.randint(0, 2)
    view = TreasureHuntView(interaction.user.id, treasure_index, remaining_maps, guild_id=interaction.guild_id)
    embed = build_treasure_hunt_embed(interaction.user, remaining_maps)
    banner = get_treasure_banner_file()
    await send_loading_then_edit(
        interaction,
        "Копаем клад...",
        embed,
        view=view,
        file=banner,
    )


@bot.tree.command(name="dealer", description="Торговец: заполнить повозку товарами")
async def dealer_command(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        await send_embed_response(
            interaction,
            "Только на сервере",
            "Эту команду можно использовать только на сервере.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)

        if not has_game_role(interaction.user, DEALER_ROLE_KEY, account):
            save_economy()
            await send_embed_response(
                interaction,
                "Нужна роль",
                get_custom_message("role_required").format(role="Торговец"),
                ephemeral=True,
            )
            return

        old_fill = account["dealer_wagon"]
        if old_fill >= 100:
            save_economy()
            await send_embed_response(
                interaction,
                "Повозка полная",
                "Повозка уже заполнена на **100%**.",
                ephemeral=True,
            )
            return

        cooldown = get_dealer_cooldown(account)
        if cooldown > 0:
            save_economy()
            await send_embed_response(
                interaction,
                "Повозка в пути",
                f"Следующую загрузку можно сделать через **{format_duration(cooldown)}**.",
                ephemeral=True,
            )
            return

        added_fill = random.randint(DEALER_MIN_FILL, DEALER_MAX_FILL)
        account["dealer_wagon"] = min(100.0, old_fill + added_fill)
        actual_added = account["dealer_wagon"] - old_fill
        account["last_dealer_at"] = now_local().isoformat(timespec="seconds")
        current_fill = account["dealer_wagon"]
        save_economy()

    embed = build_bot_embed(
        "Повозка торговца",
        f"{interaction.user.mention}, вы загрузили повозку на "
        f"**+{format_percent(actual_added)}**.\n"
        f"Текущее заполнение: **{format_percent(current_fill)}**.\n"
        f"Следующая загрузка: через **{format_duration(DEALER_COOLDOWN_SECONDS)}**.",
        color=discord.Color.dark_gold(),
    )
    await send_loading_then_edit(
        interaction,
        "Повозка едет...",
        embed,
    )


@bot.tree.command(name="dealer-delivery", description="Торговец: доставить полную повозку")
async def dealer_delivery_command(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        await send_embed_response(
            interaction,
            "Только на сервере",
            "Эту команду можно использовать только на сервере.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)

        if not has_game_role(interaction.user, DEALER_ROLE_KEY, account):
            save_economy()
            await send_embed_response(
                interaction,
                "Нужна роль",
                get_custom_message("role_required").format(role="Торговец"),
                ephemeral=True,
            )
            return

        if account["dealer_wagon"] < 100:
            current_fill = account["dealer_wagon"]
            save_economy()
            await send_embed_response(
                interaction,
                "Повозка не готова",
                "Для доставки нужна повозка, заполненная на **100%**.\n"
                f"Сейчас заполнено: **{format_percent(current_fill)}**.",
                ephemeral=True,
            )
            return

        reward = random.randint(DEALER_DELIVERY_MIN_REWARD, DEALER_DELIVERY_MAX_REWARD)
        account["dealer_wagon"] = 0.0
        account["cash"] += reward
        save_economy()

    embed = build_bot_embed(
        "Доставка завершена",
        f"{interaction.user.mention}, доставка завершена! Вы получили "
        f"**{format_money(reward)}**.\n"
        "Повозка снова пустая: **0,0%**.",
        color=discord.Color.dark_gold(),
    )
    await send_loading_then_edit(
        interaction,
        "Повозка едет...",
        embed,
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

        if not has_game_role(interaction.user, MOONSHINER_ROLE_KEY, account):
            save_economy()
            await interaction.followup.send(
                get_custom_message("role_required").format(role="Самогонщик"),
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



@bot.tree.command(name="check", description="Админ: показать баланс участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, чей баланс нужно посмотреть")
async def admin_balance_command(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    async with economy_lock:
        rate = update_gold_rate()
        account = get_account(member.id)
        save_economy()
        embed = build_balance_embed(interaction.guild, member, account, rate)

    balance_image = get_balance_image_file()
    if balance_image:
        await interaction.followup.send(embed=embed, file=balance_image, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="give-money", description="Админ: выдать деньги участнику")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, ID, упоминание или all", amount="Сумма денег")
async def admin_give_cash_command(
    interaction: discord.Interaction, member: str, amount: float
):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Введите сумму больше нуля.", ephemeral=True
        )
        return

    targets, is_all, error = await resolve_admin_targets(interaction, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    async with economy_lock:
        update_gold_rate()
        for target in targets:
            account = get_account(target.id)
            account["cash"] += amount
        save_economy()
        if is_all:
            total = amount * len(targets)
            message = (
                f"{format_target_result(targets, is_all)} получили по **{format_money(amount)}**.\n"
                f"Всего выдано: **{format_money(total)}**."
            )
        else:
            account = get_account(targets[0].id)
            message = (
                f"{targets[0].mention} получил(а) **{format_money(amount)}**.\n"
                f"{format_account(account)}"
            )

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="remove-money", description="Админ: отнять деньги у участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, ID, упоминание или all", amount="Сумма денег")
async def admin_remove_cash_command(
    interaction: discord.Interaction, member: str, amount: float
):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Введите сумму больше нуля.", ephemeral=True
        )
        return

    targets, is_all, error = await resolve_admin_targets(interaction, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    async with economy_lock:
        update_gold_rate()
        total_taken = 0.0
        for target in targets:
            account = get_account(target.id)
            taken = min(account["cash"], amount)
            account["cash"] -= taken
            total_taken += taken
        save_economy()
        if is_all:
            message = (
                f"{format_target_result(targets, is_all)}: снято по **{format_money(amount)}**.\n"
                f"Всего снято: **{format_money(total_taken)}**."
            )
        else:
            account = get_account(targets[0].id)
            message = f"Снято **{format_money(total_taken)}** с {targets[0].mention}.\n{format_account(account)}"

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
        set_non_negative(account, "cash", amount)
        save_economy()
        message = f"Баланс денег установлен для {member.mention}.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="give-gold", description="Админ: выдать золото участнику")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, ID, упоминание или all", amount="Сумма золота")
async def admin_give_gold_command(
    interaction: discord.Interaction, member: str, amount: float
):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Введите сумму больше нуля.", ephemeral=True
        )
        return

    targets, is_all, error = await resolve_admin_targets(interaction, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    async with economy_lock:
        update_gold_rate()
        for target in targets:
            account = get_account(target.id)
            account["gold"] += amount
        save_economy()
        if is_all:
            total = amount * len(targets)
            message = (
                f"{format_target_result(targets, is_all)} получили по **{format_gold(amount)}**.\n"
                f"Всего выдано: **{format_gold(total)}**."
            )
        else:
            account = get_account(targets[0].id)
            message = (
                f"{targets[0].mention} получил(а) **{format_gold(amount)}**.\n"
                f"{format_account(account)}"
            )

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="remove-gold", description="Админ: отнять золото у участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, ID, упоминание или all", amount="Сумма золота")
async def admin_remove_gold_command(
    interaction: discord.Interaction, member: str, amount: float
):
    if not is_valid_amount(amount):
        await interaction.response.send_message(
            "Введите сумму больше нуля.", ephemeral=True
        )
        return

    targets, is_all, error = await resolve_admin_targets(interaction, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    async with economy_lock:
        update_gold_rate()
        total_taken = 0.0
        for target in targets:
            account = get_account(target.id)
            taken = min(account["gold"], amount)
            account["gold"] -= taken
            total_taken += taken
        save_economy()
        if is_all:
            message = (
                f"{format_target_result(targets, is_all)}: снято по **{format_gold(amount)}**.\n"
                f"Всего снято: **{format_gold(total_taken)}**."
            )
        else:
            account = get_account(targets[0].id)
            message = f"Снято **{format_gold(amount)}** с {targets[0].mention}.\n{format_account(account)}"

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
        set_non_negative(account, "gold", amount)
        save_economy()
        message = f"Баланс золота установлен для {member.mention}.\n{format_account(account)}"

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="give-map", description="Админ: выдать карты сокровищ участнику")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, ID, упоминание или all", amount="Количество карт")
async def admin_give_map_command(
    interaction: discord.Interaction, member: str, amount: int = 1
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

    targets, is_all, error = await resolve_admin_targets(interaction, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    async with economy_lock:
        update_gold_rate()
        for target in targets:
            account = get_account(target.id)
            account["treasure_maps"] += amount
        save_economy()
        if is_all:
            total = amount * len(targets)
            message = (
                f"{format_target_result(targets, is_all)} получили по "
                f"**{format_treasure_maps(amount)}**.\n"
                f"Всего выдано: **{format_treasure_maps(total)}**."
            )
        else:
            account = get_account(targets[0].id)
            message = (
                f"{targets[0].mention} получил(а) **{format_treasure_maps(amount)}**.\n"
                f"{format_account(account)}"
            )

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="remove-map", description="Админ: забрать карты сокровищ у участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, ID, упоминание или all", amount="Количество карт")
async def admin_remove_map_command(
    interaction: discord.Interaction, member: str, amount: int = 1
):
    if amount <= 0:
        await interaction.response.send_message(
            "Введите количество карт больше нуля.", ephemeral=True
        )
        return

    targets, is_all, error = await resolve_admin_targets(interaction, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return

    async with economy_lock:
        update_gold_rate()
        total_taken = 0
        for target in targets:
            account = get_account(target.id)
            normalize_treasure_maps(account)
            taken = min(account["treasure_maps"], amount)
            account["treasure_maps"] -= taken
            total_taken += taken
        save_economy()
        if is_all:
            message = (
                f"{format_target_result(targets, is_all)}: забрано по **{format_treasure_maps(amount)}**.\n"
                f"Всего забрано: **{format_treasure_maps(total_taken)}**."
            )
        else:
            account = get_account(targets[0].id)
            message = (
                f"Забрано **{format_treasure_maps(total_taken)}** у {targets[0].mention}.\n"
                f"{format_account(account)}"
            )

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
@app_commands.autocomplete(role=role_name_autocomplete)
async def admin_set_role_icon_command(
    interaction: discord.Interaction, role: str, emoji: str
):
    emoji = emoji.strip()
    if not emoji:
        await interaction.response.send_message("Эмодзи не может быть пустым.", ephemeral=True)
        return
    if len(emoji) > 80:
        await interaction.response.send_message("Эмодзи слишком длинное (максимум 80 символов).", ephemeral=True)
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
@app_commands.autocomplete(role=role_name_autocomplete)
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
        f"Действует до **{expires_at.astimezone(MSK_TZ).strftime('%d.%m.%Y')}**."
    )
    if role_definition is None:
        message += "\nЭта роль не входит в список `/roles`, поэтому скидка в витрине не появится."

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="clear-discounts-roles", description="Админ: убрать скидку с роли")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(role="Название роли, например Натуралист или Торговец")
@app_commands.autocomplete(role=role_name_autocomplete)
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


@bot.tree.command(name="set-emoji", description="Админ: задать эмодзи валют, кнопок и ролей")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    currency="Что настроить: валюта, кнопка или иконка роли",
    emoji="Эмодзи, символ или серверное эмодзи, например <:gold:123456789>",
)
@app_commands.autocomplete(currency=emoji_target_autocomplete)
async def admin_set_emoji_command(
    interaction: discord.Interaction, currency: str, emoji: str
):
    emoji = emoji.strip()
    if not emoji:
        await interaction.response.send_message("Эмодзи не может быть пустым.", ephemeral=True)
        return
    if len(emoji) > 80:
        await interaction.response.send_message("Эмодзи слишком длинное (максимум 80 символов).", ephemeral=True)
        return

    currency = currency.strip()
    if currency not in {value for _, value in EMOJI_TARGETS}:
        await interaction.response.send_message(
            "Не нашёл такую настройку эмодзи. Используйте подсказки команды.",
            ephemeral=True,
        )
        return

    async with economy_lock:
        if currency == "cash":
            economy_data["cash_emoji"] = emoji
            message = f"Эмодзи для денег установлено: {emoji} ({format_money_plain(3)})"
        elif currency == "gold":
            economy_data["gold_emoji"] = emoji
            message = f"Эмодзи для золота установлено: {emoji} ({format_gold_plain(3)}). Пример: {emoji}"
        elif currency == "map":
            economy_data["map_emoji"] = emoji
            message = f"Эмодзи для карты установлено: **{format_treasure_maps(3)}**"
        elif currency == "stats":
            economy_data["stats_emoji"] = emoji
            message = f"Эмодзи для статистики установлено: **{get_stats_emoji()}Статистика**"
        elif currency.startswith("moonshine_star_"):
            level = currency.rsplit("_", 1)[-1]
            economy_data["moonshine_star_emojis"][level] = emoji
            message = f"Эмодзи для самогона {level} уровня установлено: **{emoji}**"
        elif currency == "moonshine_special":
            economy_data["moonshine_special_emoji"] = emoji
            message = f"Эмодзи для особого самогона установлено: **{emoji}**"
        elif currency == "moonshine_condenser":
            economy_data["moonshine_condenser_emoji"] = emoji
            message = f"Эмодзи для конденсатора установлено: **{emoji}**"
        elif currency == "moonshine_distiller":
            economy_data["moonshine_distiller_emoji"] = emoji
            message = f"Эмодзи для дистиллятора установлено: **{emoji}**"
        else:
            if currency.startswith("moonshine_button_"):
                button_key = currency.replace("moonshine_button_", "", 1)
                economy_data["moonshine_button_emojis"][button_key] = emoji
                message = f"Эмодзи кнопки самогонщика установлено: **{emoji}**"
            elif currency.startswith("naturalist_button_"):
                button_key = currency.replace("naturalist_button_", "", 1)
                economy_data["naturalist_button_emojis"][button_key] = emoji
                message = f"Эмодзи кнопки натуралиста установлено: **{emoji}**"
            elif currency.startswith("bounty_button_"):
                button_key = currency.replace("bounty_button_", "", 1)
                economy_data["bounty_button_emojis"][button_key] = emoji
                message = f"Эмодзи кнопки охотника установлено: **{emoji}**"
            elif currency.startswith("role_icon_"):
                role_key = currency.replace("role_icon_", "", 1)
                economy_data["role_key_icons"][role_key] = emoji
                message = f"Эмодзи роли установлено: **{emoji}**"
            elif currency.startswith("catalog_"):
                economy_data[currency] = emoji
                message = f"Эмодзи каталога установлено: **{emoji}**"
            else:
                message = "Настройка эмодзи обновлена."
        save_economy()

    await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="set-message", description="Админ: изменить текстовые сообщения бота")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    message_key="Какое сообщение изменить",
    text="Новый текст. Напишите default, чтобы вернуть стандартный текст.",
)
@app_commands.choices(
    message_key=[
        app_commands.Choice(name="Описание /roles", value="roles_description"),
        app_commands.Choice(name="Футер /roles", value="roles_footer"),
        app_commands.Choice(name="Сообщение /work", value="work_success"),
        app_commands.Choice(name="Требование роли", value="role_required"),
        app_commands.Choice(name="Подтверждение /reset-all", value="reset_prompt"),
    ]
)
async def admin_set_message_command(
    interaction: discord.Interaction, message_key: app_commands.Choice[str], text: str
):
    value = text.strip()
    if not value:
        await interaction.response.send_message("Текст не может быть пустым.", ephemeral=True)
        return
    if len(value) > 1800:
        await interaction.response.send_message("Текст слишком длинный (максимум 1800 символов).", ephemeral=True)
        return

    key = message_key.value
    if value.casefold() == "default":
        value = DEFAULT_CUSTOM_MESSAGES[key]

    async with economy_lock:
        economy_data["custom_messages"][key] = value
        save_economy()

    await interaction.response.send_message(
        f"Сообщение **{message_key.name}** обновлено.", ephemeral=True
    )


@bot.tree.command(name="auto-thread", description="Админ: Включить/выключить авто-ветки в текущем канале")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def admin_auto_thread_command(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    channel_ids = get_guild_thread_channel_ids(interaction.guild_id)
    
    if channel_id in channel_ids:
        channel_ids.remove(channel_id)
        state = "выключено"
    else:
        channel_ids.add(channel_id)
        state = "включено"
        
    async with economy_lock:
        set_guild_thread_channel_ids(interaction.guild_id, channel_ids)
        
    await interaction.response.send_message(
        f"Автоматическое создание веток для канала {interaction.channel.mention} **{state}**.",
        ephemeral=True
    )


@bot.tree.command(name="version", description="Показать текущую версию бота")
async def version_command(interaction: discord.Interaction):
    # Read version from config if available, fallback to BOT_VERSION
    try:
        cfg_version = config.get("version")
    except Exception:
        cfg_version = None
    version_text = cfg_version or BOT_VERSION or "v0.0.0"
    await interaction.response.send_message(f"Текущая версия бота: **{version_text}**")


@bot.tree.command(name="status", description="Показать статус бота: версия, серверы, пинг")
async def status_command(interaction: discord.Interaction):
    try:
        cfg_version = config.get("version") or BOT_VERSION or "v0.0.0"
    except Exception:
        cfg_version = BOT_VERSION or "v0.0.0"

    guild_count = len(bot.guilds) if hasattr(bot, "guilds") else "?"
    latency_ms = round(bot.latency * 1000) if getattr(bot, "latency", None) is not None else "?"

    settings = config.get("settings", {}) or {}
    save_on_change = settings.get("save_on_change", True)

    text = (
        f"Версия: **{cfg_version}**\n"
        f"Серверов: **{guild_count}**\n"
        f"Пинг: **{latency_ms} ms**\n"
        f"Автосохранение настроек: **{save_on_change}**"
    )

    await interaction.response.send_message(text)


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


@bot.tree.command(name="reset-dealer", description="Админ: сбросить кулдаун доставки /dealer у участника")
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(member="Участник, у которого нужно сбросить кулдаун /dealer")
async def admin_reset_dealer_command(interaction: discord.Interaction, member: discord.Member):
    token = set_economy_guild_id(interaction.guild_id)
    try:
        async with economy_lock:
            account = get_account(member.id)
            account["last_dealer_at"] = None
            save_economy()
    finally:
        reset_economy_guild_id(token)

    await interaction.response.send_message(
        f"Кулдаун торговца сброшен для {member.mention}.", ephemeral=True
    )


@reset_all_command.error
@delete_role_command.error
@admin_balance_command.error
@admin_give_cash_command.error
@admin_remove_cash_command.error
@admin_set_cash_command.error
@admin_give_gold_command.error
@admin_remove_gold_command.error
@admin_set_gold_command.error
@admin_give_map_command.error
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
@admin_set_message_command.error
@admin_reset_work_command.error
@admin_reset_dealer_command.error
@admin_auto_thread_command.error
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
    token = set_economy_guild_id(guild.id)
    try:
        async with economy_lock:
            economy_data.guild_data(guild.id)
            save_economy()
    finally:
        reset_economy_guild_id(token)

    try:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logging.info(f"Команды синхронизированы моментально для нового сервера '{guild.name}': {len(synced)}")
    except Exception as e:
        logging.error(f"Синхронизация команд не удалась для нового сервера '{guild.name}': {e}")

    try:
        await ensure_guild_roles(guild)
    except Exception as e:
        logging.error(f"ensure_guild_roles при входе на сервер '{guild.name}': {e}")


@bot.event
async def on_member_join(member):
    token = set_economy_guild_id(member.guild.id)
    try:
        data = economy_data.current()
        if data.get("welcome_role_id"):
            role = member.guild.get_role(int(data["welcome_role_id"]))
            if role:
                try:
                    await member.add_roles(role, reason="Welcome role")
                except discord.Forbidden:
                    logging.info(f"No permission to assign welcome role in {member.guild.id}")

        # Выдать заголовочную роль WildWest новому участнику
        header_role = discord.utils.find(
            lambda r: normalize_role_name(r.name) == normalize_role_name(WILDWEST_HEADER_ROLE_NAME),
            member.guild.roles,
        )
        if header_role is not None and header_role not in member.roles:
            try:
                await member.add_roles(header_role, reason="WildWest bot: выдача заголовочной роли")
            except (discord.Forbidden, discord.HTTPException):
                pass

        if data.get("welcome_enabled") and data.get("welcome_channel_id"):
            channel = member.guild.get_channel(int(data["welcome_channel_id"]))
            if channel:
                try:
                    await channel.send(format_welcome_message(data.get("welcome_message"), member))
                except discord.HTTPException as e:
                    logging.error(f"Failed to send welcome message: {e}")

        await send_guild_log(
            member.guild,
            "join",
            f"{member.mention} (`{member}`) присоединился к серверу.",
            color=discord.Color.green(),
        )
    finally:
        reset_economy_guild_id(token)


@bot.event
async def on_member_remove(member):
    token = set_economy_guild_id(member.guild.id)
    try:
        data = economy_data.current()
        if data.get("farewell_enabled") and data.get("welcome_channel_id"):
            channel = member.guild.get_channel(int(data["welcome_channel_id"]))
            if channel:
                template = data.get("farewell_message") or "{user} покинул сервер."
                text = template.replace("{user}", member.display_name).replace("{mention}", member.mention)
                try:
                    await channel.send(text)
                except discord.HTTPException as e:
                    logging.error(f"Failed to send farewell message: {e}")

        await send_guild_log(
            member.guild,
            "leave",
            f"**{member.display_name}** (`{member.id}`) покинул сервер.",
            color=discord.Color.orange(),
        )
    finally:
        reset_economy_guild_id(token)


@bot.event
async def on_member_ban(guild, user):
    await send_guild_log(
        guild,
        "ban",
        f"**{user}** (`{user.id}`) был забанен.",
        color=discord.Color.red(),
    )


@bot.event
async def on_member_unban(guild, user):
    await send_guild_log(
        guild,
        "unban",
        f"**{user}** (`{user.id}`) был разбанен.",
        color=discord.Color.green(),
    )


@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return
    content = (message.content or "")[:900]
    if not content and message.attachments:
        content = f"[вложение: {message.attachments[0].filename}]"
    await send_guild_log(
        message.guild,
        "delete",
        f"Удалено сообщение {message.author.mention} в {message.channel.mention}:\n>>> {content or '(пусто)'}",
        color=discord.Color.red(),
    )


@bot.event
async def on_message_edit(before, after):
    if before.author.bot or not before.guild or before.content == after.content:
        return
    await send_guild_log(
        before.guild,
        "edit",
        (
            f"{before.author.mention} отредактировал сообщение в {before.channel.mention}\n"
            f"**Было:** {before.content[:400]}\n**Стало:** {after.content[:400]}"
        ),
        color=discord.Color.gold(),
    )


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot or not member.guild:
        return
    if before.channel == after.channel:
        return
    if after.channel and not before.channel:
        await send_guild_log(
            member.guild,
            "voice_join",
            f"{member.mention} вошёл в {after.channel.mention}",
            color=discord.Color.green(),
        )
    elif before.channel and not after.channel:
        await send_guild_log(
            member.guild,
            "voice_leave",
            f"{member.mention} вышел из {before.channel.mention}",
            color=discord.Color.orange(),
        )


# Create a discussion thread for new posts in configured channels.
@bot.event
async def on_message(message):
    token = None
    if message.guild:
        token = set_economy_guild_id(message.guild.id)
    try:
        if message.author == bot.user:
            return

        await bot.process_commands(message)

        guild_thread_channels = set()
        if message.guild:
            guild_thread_channels = get_guild_thread_channel_ids(message.guild.id)

        if message.channel.id in guild_thread_channels:
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
                    await thread.send(embed=build_bot_embed("Обсуждение", "Оставьте Комментарий"))
                except discord.Forbidden:
                    logging.info(f"Нет прав для создания треда в канале {message.channel.id}")
                except discord.HTTPException as e:
                    logging.info(f"Создание треда не удалось: {e}")
    finally:
        if token is not None:
            reset_economy_guild_id(token)

# --- INJECT BOT GLOBALS INTO LOGIC MODULES ---
# Это необходимо, так как логика была вынесена из bot.py, 
# но продолжает использовать функции и переменные (например, economy_data, format_money).
def _inject_missing_globals():
    import src.bounty_logic
    import src.naturalist_logic
    import src.moonshiner_logic
    bot_globals = globals()
    for mod in [src.bounty_logic, src.naturalist_logic, src.moonshiner_logic]:
        for k, v in bot_globals.items():
            if not k.startswith("__") and not hasattr(mod, k):
                setattr(mod, k, v)

_inject_missing_globals()
# ---------------------------------------------

def main():
    load_env_file()
    # Resolve token: environment variables override config.json
    token = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN") or config.get("token", "")
    token = (token or "").strip()
    if not token:
        raise RuntimeError("Token not found. Set DISCORD_TOKEN in .env, in the environment, or in config.json")

    # Сохраняем данные при получении SIGTERM (Render/Railway убивают процесс этим сигналом при деплое)
    def _handle_sigterm(*args):
        logging.info("SIGTERM получен — сохраняем данные перед завершением...")
        try:
            economy_data.save_all()
            logging.info("Данные успешно сохранены.")
        except Exception as _e:
            logging.error("Ошибка при сохранении данных на SIGTERM: %s", _e)
        raise SystemExit(0)

    try:
        signal.signal(signal.SIGTERM, _handle_sigterm)
    except (OSError, ValueError):
        pass  # Windows или некорректный контекст — пропускаем

    Thread(target=run_web, daemon=True).start()
    bot.run(token)


if __name__ == "__main__":
    main()
