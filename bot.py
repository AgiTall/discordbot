from src.bounty_logic import *
from src.moonshiner_logic import *
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
import sqlite3
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
CHANNELS_FILE = "data/channels.txt"
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
DEPOSIT_DAILY_RATE = 0.03
WORK_COOLDOWN_SECONDS = 60 * 60
DEALER_COOLDOWN_SECONDS = 60 * 60
DEFAULT_CASH_EMOJI = "$"
DEFAULT_GOLD_EMOJI = "🪙"
DEFAULT_MAP_EMOJI = "🗺️"
DEFAULT_INVESTMENT_EMOJI = "📈"
DEFAULT_STATS_EMOJI = "👤"
TREASURE_BANNER_FILE = "assets/images/goldenmap.png"
ROLE_IMAGE_FILE = "assets/images/roles.png"
ROLE_IMAGE_ATTACHMENT_NAME = "roles.png"
BALANCE_IMAGE_FILE = "assets/images/balance.png"
BALANCE_IMAGE_ATTACHMENT_NAME = "balance.png"
NATURALIST_IMAGE_FILE = "assets/images/naturalist.png"
NATURALIST_IMAGE_ATTACHMENT_NAME = "naturalist.png"
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
DEFAULT_NATURALIST_BUTTON_EMOJIS = {
    "sample": "🔬",
    "sell": "💵",
    "collection": "📖",
    "legendary": "🐾",
    "shop": "🧪",
    "refresh": "🔄",
}
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
        "emoji": "🎯",
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
        "available": True,
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

DEFAULT_ROLE_EMOJIS = {
    role_definition["key"]: role_definition["emoji"]
    for role_definition in ROLE_DEFINITIONS
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
        "investment_emoji": DEFAULT_INVESTMENT_EMOJI,
        "stats_emoji": DEFAULT_STATS_EMOJI,
        "moonshine_star_emojis": DEFAULT_MOONSHINE_STAR_EMOJIS.copy(),
        "moonshine_special_emoji": DEFAULT_MOONSHINE_SPECIAL_EMOJI,
        "moonshine_button_emojis": DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy(),
        "naturalist_button_emojis": DEFAULT_NATURALIST_BUTTON_EMOJIS.copy(),
        "bounty_button_emojis": DEFAULT_BOUNTY_BUTTON_EMOJIS.copy(),
        "role_key_icons": DEFAULT_ROLE_EMOJIS.copy(),
        "custom_messages": DEFAULT_CUSTOM_MESSAGES.copy(),
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
    data.setdefault("investment_emoji", DEFAULT_INVESTMENT_EMOJI)
    data.setdefault("stats_emoji", DEFAULT_STATS_EMOJI)
    data.setdefault("moonshine_star_emojis", DEFAULT_MOONSHINE_STAR_EMOJIS.copy())
    data.setdefault("moonshine_special_emoji", DEFAULT_MOONSHINE_SPECIAL_EMOJI)
    data.setdefault("moonshine_condenser_emoji", DEFAULT_MOONSHINE_CONDENSER_EMOJI)
    data.setdefault("moonshine_distiller_emoji", DEFAULT_MOONSHINE_DISTILLER_EMOJI)
    data.setdefault("moonshine_button_emojis", DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy())
    data.setdefault("naturalist_button_emojis", DEFAULT_NATURALIST_BUTTON_EMOJIS.copy())
    data.setdefault("bounty_button_emojis", DEFAULT_BOUNTY_BUTTON_EMOJIS.copy())
    data.setdefault("role_key_icons", DEFAULT_ROLE_EMOJIS.copy())
    data.setdefault("custom_messages", DEFAULT_CUSTOM_MESSAGES.copy())
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


class EconomyStore:
    def __init__(self, db_path="data/economy.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.conn:
            self.conn.execute("CREATE TABLE IF NOT EXISTS guilds (guild_id TEXT PRIMARY KEY, data TEXT)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS users (guild_id TEXT, user_id TEXT, data TEXT, PRIMARY KEY(guild_id, user_id))")
        self.guild_cache = {}

    def _load_guild(self, guild_id):
        cursor = self.conn.execute("SELECT data FROM guilds WHERE guild_id = ?", (str(guild_id),))
        row = cursor.fetchone()
        if row:
            data = json.loads(row["data"])
        else:
            data = default_economy()
        
        # Load users
        users_cursor = self.conn.execute("SELECT user_id, data FROM users WHERE guild_id = ?", (str(guild_id),))
        users = {}
        for u_row in users_cursor:
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
        self.guild_cache[guild_id] = default_economy()
        self.save_all()

    def reset_guild(self, guild_id):
        guild_key = str(guild_id) if guild_id else ECONOMY_GLOBAL_KEY
        self.guild_cache[guild_key] = default_economy()
        self.save_all()

    def configured_treasure_guild_ids(self):
        cursor = self.conn.execute("SELECT guild_id FROM guilds")
        for row in cursor:
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
        with self.conn:
            for guild_id, data in self.guild_cache.items():
                data_copy = dict(data)
                users = data_copy.pop("users", {})
                self.conn.execute(
                    "INSERT OR REPLACE INTO guilds (guild_id, data) VALUES (?, ?)", 
                    (str(guild_id), json.dumps(data_copy, ensure_ascii=False))
                )
                for user_id, user_data in users.items():
                    self.conn.execute(
                        "INSERT OR REPLACE INTO users (guild_id, user_id, data) VALUES (?, ?, ?)",
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


def get_investment_emoji():
    emoji = economy_data.get("investment_emoji")
    if not emoji:
        return str(DEFAULT_INVESTMENT_EMOJI)
    return str(emoji)


def get_stats_emoji():
    emoji = economy_data.get("stats_emoji")
    if not emoji:
        return str(DEFAULT_STATS_EMOJI)
    return str(emoji)












def debug_gold_info():
    """Return tuple (economy_key, stored_value, resolved_string) for debugging."""
    key = get_current_economy_key()
    stored = economy_data.get("gold_emoji")
    resolved = get_gold_emoji()
    return key, stored, resolved


def get_naturalist_button_emoji(button_key):
    emojis = economy_data.get("naturalist_button_emojis", {})
    emoji = emojis.get(button_key)
    if not emoji:
        return str(DEFAULT_NATURALIST_BUTTON_EMOJIS[button_key])
    return str(emoji)




def get_custom_message(message_key):
    messages = economy_data.get("custom_messages", {})
    msg = messages.get(message_key)
    if not msg:
        return DEFAULT_CUSTOM_MESSAGES[message_key]
    return msg


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
            body = "🔒 Недоступен"

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














def xp_for_next_level(level, base):
    return max(1, int(level * base))


def apply_role_xp(progress, amount, max_level, base):
    progress["xp"] = max(0, int(progress.get("xp", 0)) + int(amount))
    progress["level"] = max(1, min(max_level, int(progress.get("level", 1))))
    levels_gained = 0

    while progress["level"] < max_level:
        needed = xp_for_next_level(progress["level"], base)
        if progress["xp"] < needed:
            break
        progress["xp"] -= needed
        progress["level"] += 1
        levels_gained += 1

    if progress["level"] >= max_level:
        progress["level"] = max_level
        progress["xp"] = min(progress["xp"], xp_for_next_level(max_level, base))

    return levels_gained












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


def format_sample_name(sample_key):
    if sample_key in ANIMALS:
        return ANIMALS[sample_key]["name"]
    if sample_key in LEGENDARY_ANIMALS:
        return LEGENDARY_ANIMALS[sample_key]["name"]
    return sample_key


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
            elif role_definition["key"] == BOUNTY_ROLE_KEY:
                row = f"{icon} {name}: {format_bounty_short(account)}"
            elif role_definition["key"] == NATURALIST_ROLE_KEY:
                row = f"{icon} {name}: {format_naturalist_short(account)}"
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
            "deposit": 0.0,
            "treasure_maps": 0,
            "owned_roles": [],
            "dealer_wagon": 0.0,
            "last_dealer_at": None,
            "bounty": default_bounty_data(),
            "moonshine": default_moonshine_data(),
            "naturalist": default_naturalist_data(),
            "collection_showcase": [],
            "deposit_updated_at": now_local().isoformat(timespec="seconds"),
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
    account.setdefault("deposit", 0.0)
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
            "`/dealer-delivery` — доставить полную повозку и получить 500–625 долларов."
        )
    if role_key == MOONSHINER_ROLE_KEY:
        return (
            "\n\nКоманды самогонщика:\n"
            "`/moonshine` — открыть меню предприятия, выбрать бражку за 50 долларов, "
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






def get_naturalist_image_file():
    if not os.path.exists(NATURALIST_IMAGE_FILE):
        return None
    return discord.File(NATURALIST_IMAGE_FILE, filename=NATURALIST_IMAGE_ATTACHMENT_NAME)


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
        
    await interaction.response.send_message(**kwargs)


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
    bot.validate_bet = validate_bet
    bot.economy_lock = economy_lock
    bot.get_account = get_account
    bot.save_economy = save_economy
    bot.format_money = format_money
    bot.accrue_deposit_interest = accrue_deposit_interest
    try:
        await bot.add_cog(leveling.LevelingCog(bot))
        await bot.load_extension("cogs.casino")
    except Exception as e:
        logging.error(f"Failed to load LevelingCog: {e}")
bot.setup_hook = setup_hook

active_channels = load_channels()
economy_data = EconomyStore()
economy_lock = asyncio.Lock()

RESET_CONFIRMATION_PHRASES = ("Я знаю что я делаю", "I know what I'm doing")
ALL_TARGET_ALIASES = {"all", "@everyone", "everyone", "все", "всем", "всех"}
ADMIN_COMMAND_NAMES = {
    "reset-all",
    "delete-role",
    "check",
    "give-money",
    "remove-money",
    "set-money",
    "give-gold",
    "remove-gold",
    "set-gold",
    "give-map",
    "set-deposit",
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
    ("Инвестиции", "investment"),
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


def build_balance_embed(guild, member, account, rate, interest=0.0):
    cash = account["cash"]
    gold = account["gold"]
    deposit = account["deposit"]
    treasure_maps = account["treasure_maps"]
    role_sections, unavailable_role_sections = format_balance_role_sections(
        guild, member, account
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
        title=f"{get_stats_emoji()}Статистика: {member.display_name}",
        description=description,
        color=discord.Color.dark_gold(),
    )
    if os.path.exists(BALANCE_IMAGE_FILE):
        embed.set_image(url=f"attachment://{BALANCE_IMAGE_ATTACHMENT_NAME}")
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
            await interaction.followup.send(
                f"На сервере нет роли **{role_definition['name']}**. "
                "Администратор должен создать её или переименовать существующую.",
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
            accrue_deposit_interest(account)
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
            "`/dealer` — команда торговца: заполнить повозку на 10–35%; кулдаун 1 час.\n"
            "`/dealer-delivery` — доставить полную повозку и получить 500–625 долларов.\n"
            "`/moonshine` — меню самогонщика: бражка за 50 долларов, особые ингредиенты, улучшения и доставка."
        ),
        inline=False,
    )
    roles.add_field(
        name="Карты сокровищ",
        value=(
            "`/excavation` — потратить карту, выбрать одно из трёх мест и получить 2 попытки найти клад.\n"
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
                "`/give-money member/all amount` — выдать деньги.\n"
                "`/remove-money member amount` — отнять деньги.\n"
                "`/set-money member amount` — установить деньги.\n"
                "`/give-gold member/all amount` — выдать золото.\n"
                "`/remove-gold member amount` — отнять золото.\n"
                "`/set-gold member amount` — установить золото.\n"
                "`/set-deposit member amount` — установить вклад."
            ),
            inline=False,
        )
        admin.add_field(
            name="Карты и Повозка",
            value=(
                "`/give-map member/all amount` — выдать карты сокровищ.\n"
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
                "`/set-emoji currency emoji` — настроить эмодзи валют, кнопок и ролей.\n"
                "`/set-message message_key text` — изменить текстовые шаблоны.\n"
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
        if os.path.exists(TREASURE_BANNER_FILE):
            page.set_image(url=f"attachment://{TREASURE_BANNER_FILE}")

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


class NaturalistOwnerView(discord.ui.View):
    def __init__(self, user_id, timeout=600):
        super().__init__(timeout=timeout)
        self.user_id = user_id

    async def interaction_check(self, interaction):
        set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Это меню натуралиста открыто не для вас.", ephemeral=True
            )
            return False
        return True


class NaturalistMainView(NaturalistOwnerView):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.sample_button.emoji = get_naturalist_button_emoji("sample")
        self.sell_button.emoji = get_naturalist_button_emoji("sell")
        self.collection_button.emoji = get_naturalist_button_emoji("collection")
        self.legendary_button.emoji = get_naturalist_button_emoji("legendary")
        self.shop_button.emoji = get_naturalist_button_emoji("shop")
        self.refresh_button.emoji = get_naturalist_button_emoji("refresh")

    @discord.ui.button(label="Взять образец", style=discord.ButtonStyle.primary, row=0)
    async def sample_button(self, interaction, button):
        embed = build_bot_embed(
            "Выбор региона",
            "Выберите регион, где хотите искать животное.",
            color=discord.Color.dark_green(),
        )
        if os.path.exists(NATURALIST_IMAGE_FILE):
            embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
        await interaction.response.edit_message(
            embed=embed, view=NaturalistRegionView(interaction.user.id)
        )

    @discord.ui.button(label="Сдать образцы", style=discord.ButtonStyle.success, row=0)
    async def sell_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            samples = dict(naturalist.get("samples", {}))
            if not samples:
                save_economy()
                await interaction.response.send_message(
                    "У вас пока нет образцов для сдачи.", ephemeral=True
                )
                return

            multiplier = get_naturalist_sale_multiplier(naturalist)
            cash_total = 0.0
            gold_total = 0.0
            xp_total = 0
            sold_count = 0
            for sample_key, amount in samples.items():
                if sample_key in ANIMALS:
                    item = ANIMALS[sample_key]
                    cash_total += item["cash"] * amount
                    xp_total += item["xp"] * amount
                else:
                    item = LEGENDARY_ANIMALS[sample_key]
                    cash_total += item["cash"] * amount
                    gold_total += item["gold"] * amount
                    xp_total += item["xp"] * amount
                sold_count += amount
            cash_total = round(cash_total * multiplier, 2)
            account["cash"] += cash_total
            account["gold"] += gold_total
            naturalist["samples"] = {}
            levels = apply_role_xp(naturalist, xp_total, NATURALIST_MAX_LEVEL, 180)
            interaction.client.dispatch("leveling_add_xp", interaction.user, xp_total, "jobs")
            save_economy()

            note = (
                f"Гарриет приняла **{format_integer(sold_count)}** образцов: "
                f"**{format_money(cash_total)}**"
            )
            if gold_total > 0:
                note += f" и **{format_gold(gold_total)}**"
            note += f". Опыт: **+{xp_total}**."
            if levels:
                note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(interaction.user.id)
        )

    @discord.ui.button(label="Справочник", style=discord.ButtonStyle.secondary, row=0)
    async def collection_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            embed = build_naturalist_collection_embed(naturalist)
            save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistCollectionView(interaction.user.id, naturalist)
        )

    @discord.ui.button(label="Легендарное животное", style=discord.ButtonStyle.primary, row=1)
    async def legendary_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            if naturalist["level"] < 5:
                save_economy()
                await interaction.response.send_message(
                    "Легендарные животные открываются с 5 уровня натуралиста.",
                    ephemeral=True,
                )
                return
            embed = build_naturalist_legendary_embed(naturalist)
            save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistLegendaryView(interaction.user.id, naturalist)
        )

    @discord.ui.button(label="Магазин", style=discord.ButtonStyle.secondary, row=1)
    async def shop_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            embed = build_naturalist_shop_embed(account, naturalist)
            save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistShopView(interaction.user.id)
        )

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_button(self, interaction, button):
        async with economy_lock:
            account = get_account(interaction.user.id)
            embed = build_naturalist_embed(interaction.guild, account)
            save_economy()
        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(interaction.user.id)
        )


class NaturalistRegionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=f"{region['emoji']} {region['name']}",
                value=region_key,
                description=", ".join(ANIMALS[key]["name"] for key in CATEGORIES[region_key]),
            )
            for region_key, region in NATURALIST_REGIONS.items()
        ]
        super().__init__(
            placeholder="Выберите регион",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        region_key = self.values[0]
        region = NATURALIST_REGIONS[region_key]
        lines = []
        for animal_key in CATEGORIES[region_key]:
            animal = ANIMALS[animal_key]
            lines.append(
                f"**{animal['name']}** — {animal['shots']} патр., "
                f"шанс {format_percent(animal['chance'] * 100)}, "
                f"сдача {format_money(animal['cash'])}, опыт {animal['xp']}"
            )
        embed = build_bot_embed(
            f"{region['emoji']} {region['name']}",
            "\n".join(lines),
            color=discord.Color.dark_green(),
        )
        if os.path.exists(NATURALIST_IMAGE_FILE):
            embed.set_image(url=f"attachment://{NATURALIST_IMAGE_ATTACHMENT_NAME}")
        await interaction.response.edit_message(
            embed=embed, view=NaturalistAnimalView(interaction.user.id, region_key)
        )


class NaturalistRegionView(NaturalistOwnerView):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.add_item(NaturalistRegionSelect())


class NaturalistAnimalSelect(discord.ui.Select):
    def __init__(self, region_key):
        options = []
        for animal_key in CATEGORIES[region_key]:
            animal = ANIMALS[animal_key]
            options.append(
                discord.SelectOption(
                    label=animal["name"],
                    value=animal_key,
                    description=(
                        f"{animal['shots']} патр. · шанс {format_percent(animal['chance'] * 100)} · "
                        f"{format_number(animal['cash'])}$"
                    ),
                )
            )
        super().__init__(
            placeholder="Выберите животное",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        animal_key = self.values[0]
        animal = ANIMALS[animal_key]
        async with economy_lock:
            account = get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            cooldown = get_naturalist_sample_cooldown(naturalist)
            if cooldown > 0:
                save_economy()
                await interaction.response.send_message(
                    f"Следующий образец можно брать через **{format_duration(cooldown)}**.",
                    ephemeral=True,
                )
                return
            if naturalist["inventory"]["tranquilizers"] < animal["shots"]:
                save_economy()
                await interaction.response.send_message(
                    "Не хватает транквилизаторов. Купите их в магазине натуралиста.",
                    ephemeral=True,
                )
                return

            naturalist["inventory"]["tranquilizers"] -= animal["shots"]
            naturalist["last_sample_at"] = now_local().isoformat(timespec="seconds")
            chance = get_naturalist_success_chance(naturalist, animal["chance"])
            success = random.random() <= chance
            if success:
                naturalist["samples"][animal_key] = naturalist["samples"].get(animal_key, 0) + 1
                xp_reward = random.randint(20, 30)
                levels = apply_role_xp(
                    naturalist, xp_reward, NATURALIST_MAX_LEVEL, 180
                )
                interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
                note = (
                    f"Образец **{animal['name']}** получен. "
                    f"Потрачено патронов: **{animal['shots']}**. "
                    f"Опыт: **+{xp_reward}**."
                )
                if levels:
                    note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            else:
                note = (
                    f"**{animal['name']}** убежал. "
                    f"Потрачено патронов: **{animal['shots']}**. "
                    f"Шанс был **{format_percent(chance * 100)}**."
                )
            save_economy()
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(interaction.user.id)
        )


class NaturalistAnimalView(NaturalistOwnerView):
    def __init__(self, user_id, region_key):
        super().__init__(user_id)
        self.add_item(NaturalistAnimalSelect(region_key))


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


class NaturalistCategoryButton(discord.ui.Button):
    def __init__(self, region_key, naturalist):
        region = NATURALIST_REGIONS[region_key]
        complete = has_full_naturalist_category(naturalist, region_key)
        super().__init__(
            label=f"Сдать: {region['name']}",
            style=discord.ButtonStyle.success if complete else discord.ButtonStyle.secondary,
            emoji=region["emoji"],
            disabled=not complete,
            custom_id=f"naturalist:category:{region_key}",
        )
        self.region_key = region_key

    async def callback(self, interaction):
        async with economy_lock:
            account = get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            if not has_full_naturalist_category(naturalist, self.region_key):
                save_economy()
                await interaction.response.send_message(
                    "Для сдачи категории нужен хотя бы один образец каждого животного.",
                    ephemeral=True,
                )
                return
            for animal_key in CATEGORIES[self.region_key]:
                naturalist["samples"][animal_key] -= 1
                if naturalist["samples"][animal_key] <= 0:
                    naturalist["samples"].pop(animal_key, None)
            cash_reward = round(100.0 * get_naturalist_sale_multiplier(naturalist), 2)
            gold_reward = 0.5
            xp_reward = 300
            account["cash"] += cash_reward
            account["gold"] += gold_reward
            levels = apply_role_xp(naturalist, xp_reward, NATURALIST_MAX_LEVEL, 180)
            interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
            save_economy()
            region = NATURALIST_REGIONS[self.region_key]
            note = (
                f"Категория **{region['name']}** сдана: "
                f"**{format_money(cash_reward)}**, **{format_gold(gold_reward)}**, "
                f"опыт **+{xp_reward}**."
            )
            if levels:
                note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(interaction.user.id)
        )


class NaturalistCollectionView(NaturalistOwnerView):
    def __init__(self, user_id, naturalist):
        super().__init__(user_id)
        for region_key in NATURALIST_REGIONS:
            self.add_item(NaturalistCategoryButton(region_key, naturalist))


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


class NaturalistLegendarySelect(discord.ui.Select):
    def __init__(self, naturalist):
        options = []
        for animal_key, animal in LEGENDARY_ANIMALS.items():
            if naturalist["level"] < animal["required_level"]:
                continue
            options.append(
                discord.SelectOption(
                    label=animal["name"],
                    value=animal_key,
                    description=(
                        f"10 патр. · {format_number(animal['cash'])}$ · "
                        f"{format_number(animal['gold'])} зол."
                    ),
                )
            )
        if not options:
            options.append(
                discord.SelectOption(
                    label="Нет доступных легендарных животных",
                    value="none",
                    description="Повысьте уровень натуралиста",
                )
            )
        super().__init__(
            placeholder="Выберите легендарное животное",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "Пока нет доступных легендарных животных.", ephemeral=True
            )
            return

        animal_key = self.values[0]
        animal = LEGENDARY_ANIMALS[animal_key]
        async with economy_lock:
            account = get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            cooldown = get_naturalist_legendary_cooldown(naturalist)
            if cooldown > 0:
                save_economy()
                await interaction.response.send_message(
                    f"Следующая легендарная охота будет доступна через **{format_duration(cooldown)}**.",
                    ephemeral=True,
                )
                return
            if naturalist["level"] < animal["required_level"]:
                save_economy()
                await interaction.response.send_message(
                    "Уровень натуралиста пока слишком низкий.", ephemeral=True
                )
                return
            if naturalist["inventory"]["tranquilizers"] < 10:
                save_economy()
                await interaction.response.send_message(
                    "Для легендарной охоты нужно 10 транквилизаторов.",
                    ephemeral=True,
                )
                return

            naturalist["inventory"]["tranquilizers"] -= 10
            naturalist["legendary_cooldown_until"] = (
                now_local() + timedelta(seconds=NATURALIST_LEGENDARY_COOLDOWN_SECONDS)
            ).isoformat(timespec="seconds")
            chance = min(0.70, 0.50 + naturalist["level"] * 0.01)
            success = random.random() <= chance
            if success:
                naturalist["samples"][animal_key] = naturalist["samples"].get(animal_key, 0) + 1
                xp_reward = max(20, animal["xp"] // 3)
                levels = apply_role_xp(
                    naturalist, xp_reward, NATURALIST_MAX_LEVEL, 180
                )
                interaction.client.dispatch("leveling_add_xp", interaction.user, xp_reward, "jobs")
                note = (
                    f"Легендарный образец **{animal['name']}** получен. "
                    f"Опыт: **+{xp_reward}**."
                )
                if levels:
                    note += f"\nНовый уровень натуралиста: **{naturalist['level']}**."
            else:
                note = (
                    f"**{animal['name']}** ушёл от вас. "
                    f"Шанс был **{format_percent(chance * 100)}**."
                )
            save_economy()
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(interaction.user.id)
        )


class NaturalistLegendaryView(NaturalistOwnerView):
    def __init__(self, user_id, naturalist):
        super().__init__(user_id)
        self.add_item(NaturalistLegendarySelect(naturalist))


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


class NaturalistShopButton(discord.ui.Button):
    def __init__(self, amount, label):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.success,
            emoji=get_naturalist_button_emoji("shop"),
        )
        self.amount = amount

    async def callback(self, interaction):
        async with economy_lock:
            account = get_account(interaction.user.id)
            naturalist = get_naturalist_account(account)
            cap = get_naturalist_tranq_cap(naturalist)
            current = naturalist["inventory"]["tranquilizers"]
            space = max(0, cap - current)
            if space <= 0:
                save_economy()
                await interaction.response.send_message(
                    "Сумка транквилизаторов уже заполнена.", ephemeral=True
                )
                return
            if self.amount == "max":
                affordable = int(account["cash"] // NATURALIST_TRANQ_PRICE)
                amount = min(space, affordable)
            else:
                amount = min(space, int(self.amount))
            cost = amount * NATURALIST_TRANQ_PRICE
            if amount <= 0 or account["cash"] + 0.0001 < cost:
                save_economy()
                await interaction.response.send_message(
                    "Не хватает денег на покупку транквилизаторов.", ephemeral=True
                )
                return
            account["cash"] -= cost
            naturalist["inventory"]["tranquilizers"] += amount
            save_economy()
            note = f"Куплено **{amount}** транквилизаторов за **{format_money(cost)}**."
            embed = build_naturalist_embed(interaction.guild, account, note=note)

        await interaction.response.edit_message(
            embed=embed, view=NaturalistMainView(interaction.user.id)
        )


class NaturalistShopView(NaturalistOwnerView):
    def __init__(self, user_id):
        super().__init__(user_id)
        self.add_item(NaturalistShopButton(10, "Купить 10"))
        self.add_item(NaturalistShopButton(50, "Купить 50"))
        self.add_item(NaturalistShopButton("max", "Купить максимум"))


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

    # Global sync is useful for production, but Discord can cache it for a while.
    try:
        global_commands = await bot.tree.sync()
        logging.info(f"Глобальные команды синхронизированы: {len(global_commands)}")
    except Exception as e:
        logging.error(f"Синхронизация глобальных команд не удалась: {e}")

    # Guild sync appears in the Discord client almost immediately.
    for guild in guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            guild_commands = await bot.tree.sync(guild=guild)
            logging.info(
                f"Команды синхронизированы для сервера '{guild.name}': "
                f"{len(guild_commands)}"
            )
        except Exception as e:
            logging.error(f"Синхронизация команд не удалась для сервера '{guild.name}': {e}")


@bot.event
async def on_ready():
    global COMMANDS_SYNCED

    logging.info(f"Бот {bot.user.name} запущен!")
    
    # Установка статуса бота
    try:
        if hasattr(discord, "CustomActivity"):
            activity = discord.CustomActivity(name=f"pchev.me {BOT_VERSION.lstrip('v')}")
        else:
            activity = discord.Activity(type=discord.ActivityType.custom, name=f"pchev.me {BOT_VERSION.lstrip('v')}")
        await bot.change_presence(status=discord.Status.online, activity=activity)
    except Exception as e:
        logging.error(f"Не удалось установить статус: {e}")

    if not daily_treasure_map_event.is_running():
        daily_treasure_map_event.start()
    if not periodic_economy_save.is_running():
        periodic_economy_save.start()

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
    guild_channels = get_guild_thread_channel_ids(interaction.guild.id)

    if channel_id in guild_channels:
        guild_channels.discard(channel_id)
        set_guild_thread_channel_ids(interaction.guild.id, guild_channels)
        if channel_id in active_channels:
            active_channels.discard(channel_id)
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


@bot.tree.command(name="news", description="Опубликовать новость через красивый Embed")
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

    embed_color = discord.Color.blurple()
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
            embed=pages[0], view=HelpView(pages), file=banner, ephemeral=True
        )
    else:
        await interaction.response.send_message(
            embed=pages[0], view=HelpView(pages), ephemeral=True
        )


@bot.tree.command(name="roles", description="Показать игровые роли и купить доступные")
async def roles_command(interaction: discord.Interaction):
    async with economy_lock:
        remove_expired_role_discounts()
        account = get_account(interaction.user.id)
        save_economy()
        embed = build_roles_embed(interaction.guild, interaction.user, account)
        view = RoleShopView(interaction.guild, interaction.user, account)

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


@bot.tree.command(name="balance", description="Показать ваш баланс")
async def balance_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with economy_lock:
        rate = update_gold_rate()
        account = get_account(interaction.user.id)
        interest = accrue_deposit_interest(account)
        save_economy()

        embed = build_balance_embed(interaction.guild, interaction.user, account, rate, interest)

    balance_image = get_balance_image_file()
    if balance_image:
        await interaction.followup.send(embed=embed, file=balance_image, ephemeral=True)
    else:
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
        scenario = random_work_scenario()
        account["cash"] += reward
        account["last_work_at"] = now_local().isoformat(timespec="seconds")
        save_economy()

    message_template = get_custom_message("work_success")
    await interaction.response.send_message(
        message_template.format(
            mention=interaction.user.mention,
            reward=format_money(reward),
            scenario=scenario,
        )
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
        super().__init__(
            label=f"Место {index + 1}",
            style=discord.ButtonStyle.primary,
            emoji="⛏️",
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
        for item in self.children:
            if item.index == self.treasure_index:
                item.emoji = "💰"
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
            f"{ingredient} x{amount}"
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
                self.finished = True
                self.disable_all()
                button.emoji = "💰"
                button.style = discord.ButtonStyle.success
                cash_reward, gold_reward, ingredients_text, remaining_maps, extra_map_granted = await self.grant_reward(interaction)
                
                result_text = (
                    f"вы нашли тайник! Получено: **{format_money(cash_reward)}** "
                    f"и **{format_gold(gold_reward)}**!\n"
                    f"Ингредиенты самогонщика: **{ingredients_text}**.\n"
                )
                if extra_map_granted:
                    result_text += "✨ **Вам повезло! Вы нашли дополнительную карту сокровищ!** ✨\n"
                result_text += f"Карт осталось: **{format_treasure_maps(remaining_maps)}**."
                
                embed = build_treasure_result_embed(
                    interaction.user,
                    "💰 Клад найден!",
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


@bot.tree.command(name="excavation", description="Использовать карту сокровищ для раскопок")
async def excavation_command(interaction: discord.Interaction):
    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)

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
        accrue_deposit_interest(account)

        if not has_game_role(interaction.user, DEALER_ROLE_KEY, account):
            save_economy()
            await send_embed_response(
                interaction,
                "Нужна роль",
                "Команда доступна только роли **Торговец**. Купить её можно через `/roles`.",
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
        accrue_deposit_interest(account)

        if not has_game_role(interaction.user, DEALER_ROLE_KEY, account):
            save_economy()
            await send_embed_response(
                interaction,
                "Нужна роль",
                "Команда доступна только роли **Торговец**. Купить её можно через `/roles`.",
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






@bot.tree.command(name="naturalist", description="Натуралист: образцы, справочник и магазин")
async def naturalist_command(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "Эту команду можно использовать только на сервере.", ephemeral=True
        )
        return

    async with economy_lock:
        update_gold_rate()
        account = get_account(interaction.user.id)
        accrue_deposit_interest(account)
        if not has_game_role(interaction.user, NATURALIST_ROLE_KEY, account):
            save_economy()
            await interaction.response.send_message(
                get_custom_message("role_required").format(role="Натуралист"),
                ephemeral=True,
            )
            return
        embed = build_naturalist_embed(interaction.guild, account)
        save_economy()

    image = get_naturalist_image_file()
    view = NaturalistMainView(interaction.user.id)
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
@app_commands.describe(member="Участник, чей баланс нужно посмотреть")
async def admin_balance_command(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)

    async with economy_lock:
        rate = update_gold_rate()
        account = get_account(member.id)
        interest = accrue_deposit_interest(account)
        save_economy()
        embed = build_balance_embed(interaction.guild, member, account, rate, interest)

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
            accrue_deposit_interest(account)
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
            accrue_deposit_interest(account)
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
        accrue_deposit_interest(account)
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
            accrue_deposit_interest(account)
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
            accrue_deposit_interest(account)
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
        accrue_deposit_interest(account)
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
            accrue_deposit_interest(account)
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
            accrue_deposit_interest(account)
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
        elif currency == "investment":
            economy_data["investment_emoji"] = emoji
            message = (
                f"Эмодзи для инвестиций установлено: "
                f"**{get_investment_emoji()} Вклад: {format_money_plain(3)}**"
            )
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
@admin_set_message_command.error
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
        logging.info(f"Команды синхронизированы для нового сервера '{guild.name}': {len(synced)}")
    except Exception as e:
        logging.error(f"Синхронизация команд не удалась для нового сервера '{guild.name}': {e}")


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

        if message.channel.id in guild_thread_channels or message.channel.id in active_channels:
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
                    await thread.send(embed=build_bot_embed("Обсуждение", "Делитесь мыслями."))
                except discord.Forbidden:
                    logging.info(f"Нет прав для создания треда в канале {message.channel.id}")
                except discord.HTTPException as e:
                    logging.info(f"Создание треда не удалось: {e}")
    finally:
        if token is not None:
            reset_economy_guild_id(token)

def main():
    load_env_file()
    # Resolve token: environment variables override config.json
    token = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN") or config.get("token", "")
    token = (token or "").strip()
    if not token:
        raise RuntimeError("Token not found. Set DISCORD_TOKEN in .env, in the environment, or in config.json")

    Thread(target=run_web, daemon=True).start()
    bot.run(token)


if __name__ == "__main__":
    main()
