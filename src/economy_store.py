"""
src/economy_store.py
EconomyStore (PostgreSQL), функции нормализации, загрузки и сохранения экономики,
ContextVar для multi-guild изоляции, вспомогательные функции времени и аккаунтов.
"""

import json
import logging
import math
import os
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone

import psycopg2
import psycopg2.extras

from emoji_config import (
    DEFAULT_CASH_EMOJI, DEFAULT_GOLD_EMOJI, DEFAULT_MAP_EMOJI,
    DEFAULT_STATS_EMOJI, DEFAULT_SAFE_EMOJI, DEFAULT_LOCK_EMOJI,
    DEFAULT_MOONSHINE_STAR_EMOJIS, DEFAULT_MOONSHINE_SPECIAL_EMOJI,
    DEFAULT_MOONSHINE_CONDENSER_EMOJI, DEFAULT_MOONSHINE_DISTILLER_EMOJI,
    DEFAULT_MOONSHINE_BUTTON_EMOJIS, DEFAULT_MOONSHINE_INGREDIENT_EMOJIS,
    DEFAULT_NATURALIST_BUTTON_EMOJIS,
    DEFAULT_MOONSHINE_PROD_EMOJI, DEFAULT_MOONSHINE_LVL_EMOJI,
    DEFAULT_MOONSHINE_ACCESS_EMOJI, DEFAULT_MOONSHINE_BOTTLES_EMOJI,
    DEFAULT_MOONSHINE_WAGON_EMOJI, DEFAULT_MOONSHINE_BREWING_EMOJI,
    DEFAULT_MOONSHINE_KETTLE_EMOJI, DEFAULT_MOONSHINE_EQUIP_EMOJI,
    DEFAULT_MOONSHINE_SKILL_EMOJI, DEFAULT_MOONSHINE_STOR_FULL_EMOJI,
    DEFAULT_MOONSHINE_STOR_EMPTY_EMOJI, DEFAULT_MOONSHINE_FINANCE_EMOJI,
    DEFAULT_BALANCE_FINANCE_EMOJI, DEFAULT_BALANCE_ROLES_EMOJI,
    DEFAULT_BALANCE_ECONOMY_EMOJI, DEFAULT_BALANCE_GANG_EMOJI,
)
from src.constants import (
    ECONOMY_FILE, ECONOMY_GLOBAL_KEY, START_GOLD_RATE, MIN_GOLD_RATE,
    DEFAULT_CUSTOM_MESSAGES, DEFAULT_ROLE_EMOJIS,
)
from src.collector_logic import default_collector_data, normalize_collector_data
from src.bounty_logic import (
    DEFAULT_BOUNTY_BUTTON_EMOJIS,
    default_bounty_data,
    normalize_bounty_data,
)
from src.moonshiner_logic import default_moonshine_data, normalize_moonshine_data
from src.naturalist_logic import default_naturalist_data, normalize_naturalist_data
from src.company_logic import normalize_companies

# ──────────────────────────────────────────────────────────────
#  ЧАСОВЫЕ ПОЯСА / ВРЕМЯ
# ──────────────────────────────────────────────────────────────

MSK_TZ = timezone(timedelta(hours=3), "MSK")


def now_local() -> datetime:
    return datetime.now(timezone.utc)


def today_iso() -> str:
    return now_local().date().isoformat()


def today_msk_iso() -> str:
    return datetime.now(MSK_TZ).date().isoformat()


def parse_local_datetime(value) -> datetime:
    if not value:
        return now_local()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return now_local()
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_local_date(value) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return now_local().date()


# ──────────────────────────────────────────────────────────────
#  CONTEXT VAR — изоляция по серверу
# ──────────────────────────────────────────────────────────────

current_economy_guild_id: ContextVar[str | None] = ContextVar(
    "current_economy_guild_id", default=None
)


def set_economy_guild_id(guild_id):
    return current_economy_guild_id.set(str(guild_id) if guild_id else ECONOMY_GLOBAL_KEY)


def reset_economy_guild_id(token):
    current_economy_guild_id.reset(token)


def get_current_economy_key() -> str:
    return current_economy_guild_id.get() or ECONOMY_GLOBAL_KEY


def with_economy_context(func):
    async def wrapper(interaction, *args, **kwargs):
        token = set_economy_guild_id(interaction.guild_id)
        try:
            return await func(interaction, *args, **kwargs)
        finally:
            reset_economy_guild_id(token)
    return wrapper


# ──────────────────────────────────────────────────────────────
#  ЭКОНОМИКА ПО УМОЛЧАНИЮ / НОРМАЛИЗАЦИЯ
# ──────────────────────────────────────────────────────────────

def default_economy() -> dict:
    return {
        "gold_rate":                    START_GOLD_RATE,
        "gold_rate_date":               today_iso(),
        "cash_emoji":                   DEFAULT_CASH_EMOJI,
        "gold_emoji":                   DEFAULT_GOLD_EMOJI,
        "map_emoji":                    DEFAULT_MAP_EMOJI,
        "stats_emoji":                  DEFAULT_STATS_EMOJI,
        "safe_emoji":                   DEFAULT_SAFE_EMOJI,
        "lock_emoji":                   DEFAULT_LOCK_EMOJI,
        "moonshine_star_emojis":        DEFAULT_MOONSHINE_STAR_EMOJIS.copy(),
        "moonshine_special_emoji":      DEFAULT_MOONSHINE_SPECIAL_EMOJI,
        "moonshine_button_emojis":      DEFAULT_MOONSHINE_BUTTON_EMOJIS.copy(),
        "moonshine_ingredient_emojis":  DEFAULT_MOONSHINE_INGREDIENT_EMOJIS.copy(),
        "naturalist_button_emojis":     DEFAULT_NATURALIST_BUTTON_EMOJIS.copy(),
        "bounty_button_emojis":         DEFAULT_BOUNTY_BUTTON_EMOJIS.copy(),
        "role_key_icons":               DEFAULT_ROLE_EMOJIS.copy(),
        "custom_messages":              DEFAULT_CUSTOM_MESSAGES.copy(),
        "treasure_dig_emoji":           None,
        "treasure_found_emoji":         None,
        "treasure_extra_emoji":         None,
        "treasure_channel_id":          None,
        "news_channel_id":              None,
        "thread_channel_ids":           [],
        "welcome_enabled":              False,
        "welcome_channel_id":           None,
        "welcome_role_id":              None,
        "welcome_message":              "Добро пожаловать на сервер, {mention}! 🎉",
        "farewell_enabled":             False,
        "farewell_message":             "{user} покинул сервер. До свидания!",
        "logs_channel_id":              None,
        "log_join":                     True,
        "log_leave":                    True,
        "log_ban":                      True,
        "log_delete":                   False,
        "log_edit":                     False,
        "log_voice":                    False,
        "log_commands":                 False,
        "last_treasure_map_drop_date":  None,
        "role_icons":                   {},
        "role_discounts":               {},
        "casino_bank":                  0.0,
        "companies":                    normalize_companies({}),
        "users":                        {},
    }


def normalize_economy_data(data: dict) -> dict:
    if not isinstance(data, dict):
        data = default_economy()

    # Гарантируем gold_emoji непустой строкой
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

    data.setdefault("gold_rate", START_GOLD_RATE)
    data.setdefault("gold_rate_date", today_iso())
    data.setdefault("cash_emoji", DEFAULT_CASH_EMOJI)
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
    data.setdefault("treasure_dig_emoji", None)
    data.setdefault("treasure_found_emoji", None)
    data.setdefault("treasure_extra_emoji", None)
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
    try:
        casino_bank = round(float(data.get("casino_bank", 0.0)), 2)
        if not math.isfinite(casino_bank) or casino_bank < 0:
            raise ValueError("casino_bank must be finite and non-negative")
        data["casino_bank"] = casino_bank
    except (TypeError, ValueError, OverflowError):
        data["casino_bank"] = 0.0
    data["companies"] = normalize_companies(data.get("companies"))
    data.setdefault("users", {})

    # moonshine UI emojis
    data.setdefault("moonshine_ui_prod",       DEFAULT_MOONSHINE_PROD_EMOJI)
    data.setdefault("moonshine_ui_lvl",        DEFAULT_MOONSHINE_LVL_EMOJI)
    data.setdefault("moonshine_ui_access",     DEFAULT_MOONSHINE_ACCESS_EMOJI)
    data.setdefault("moonshine_ui_bottles",    DEFAULT_MOONSHINE_BOTTLES_EMOJI)
    data.setdefault("moonshine_ui_wagon",      DEFAULT_MOONSHINE_WAGON_EMOJI)
    data.setdefault("moonshine_ui_brewing",    DEFAULT_MOONSHINE_BREWING_EMOJI)
    data.setdefault("moonshine_ui_kettle",     DEFAULT_MOONSHINE_KETTLE_EMOJI)
    data.setdefault("moonshine_ui_equip",      DEFAULT_MOONSHINE_EQUIP_EMOJI)
    data.setdefault("moonshine_ui_skill",      DEFAULT_MOONSHINE_SKILL_EMOJI)
    data.setdefault("moonshine_ui_stor_full",  DEFAULT_MOONSHINE_STOR_FULL_EMOJI)
    data.setdefault("moonshine_ui_stor_empty", DEFAULT_MOONSHINE_STOR_EMPTY_EMOJI)
    data.setdefault("moonshine_ui_finance",    DEFAULT_MOONSHINE_FINANCE_EMOJI)

    # balance UI emojis
    data.setdefault("balance_ui_finance", DEFAULT_BALANCE_FINANCE_EMOJI)
    data.setdefault("balance_ui_roles",   DEFAULT_BALANCE_ROLES_EMOJI)
    data.setdefault("balance_ui_economy", DEFAULT_BALANCE_ECONOMY_EMOJI)
    data.setdefault("balance_ui_gang",    DEFAULT_BALANCE_GANG_EMOJI)

    # Валидация структур
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


# ──────────────────────────────────────────────────────────────
#  POSTGRES URL НОРМАЛИЗАЦИЯ
# ──────────────────────────────────────────────────────────────

def _normalize_db_url_for_psycopg2(url: str | None) -> str | None:
    """Убирает +asyncpg и другие SQLAlchemy-префиксы из DATABASE_URL."""
    if not url:
        return url
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    url = url.replace("postgres://", "postgresql://")
    return url


# ──────────────────────────────────────────────────────────────
#  ECONOMY STORE
# ──────────────────────────────────────────────────────────────

class EconomyStore:
    def __init__(self, db_url: str | None = None):
        if db_url is None:
            db_url = os.environ.get("DATABASE_URL")
        self.db_url = _normalize_db_url_for_psycopg2(db_url)
        self._connect()
        self._init_tables()
        self.guild_cache: dict = {}

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
        """Создать таблицы economy_guilds / economy_users и мигрировать данные."""
        with self.conn.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS economy_guilds "
                "(guild_id TEXT PRIMARY KEY, data TEXT)"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS economy_users "
                "(guild_id TEXT, user_id TEXT, data TEXT, PRIMARY KEY(guild_id, user_id))"
            )

            # Миграция из старой таблицы guilds
            try:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'guilds' AND column_name = 'data'
                """)
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*) FROM economy_guilds")
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("""
                            INSERT INTO economy_guilds (guild_id, data)
                            SELECT guild_id, data FROM guilds
                            ON CONFLICT (guild_id) DO NOTHING
                        """)
                        migrated = cursor.rowcount
                        if migrated > 0:
                            logging.info(
                                f"EconomyStore: мигрировано {migrated} гильдий "
                                "из старой таблицы 'guilds' → 'economy_guilds'"
                            )
            except Exception as e:
                logging.debug(f"EconomyStore: миграция guilds пропущена: {e}")

            # Миграция из старой таблицы users
            try:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'data'
                """)
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*) FROM economy_users")
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("""
                            INSERT INTO economy_users (guild_id, user_id, data)
                            SELECT guild_id, user_id, data FROM users
                            WHERE data IS NOT NULL
                            ON CONFLICT (guild_id, user_id) DO NOTHING
                        """)
                        migrated = cursor.rowcount
                        if migrated > 0:
                            logging.info(
                                f"EconomyStore: мигрировано {migrated} пользователей "
                                "из старой таблицы 'users' → 'economy_users'"
                            )
            except Exception as e:
                logging.debug(f"EconomyStore: миграция users пропущена: {e}")

    def _load_guild(self, guild_id: str) -> dict:
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT data FROM economy_guilds WHERE guild_id = %s", (str(guild_id),)
            )
            row = cursor.fetchone()
            data = json.loads(row["data"]) if row else default_economy()

            cursor.execute(
                "SELECT user_id, data FROM economy_users WHERE guild_id = %s", (str(guild_id),)
            )
            users = {u_row["user_id"]: json.loads(u_row["data"]) for u_row in cursor}
            data["users"] = users
            return normalize_economy_data(data)

    def current(self) -> dict:
        guild_id = get_current_economy_key()
        if guild_id not in self.guild_cache:
            self.guild_cache[guild_id] = self._load_guild(guild_id)
        return self.guild_cache[guild_id]

    def guild_data(self, guild_id) -> dict:
        guild_key = str(guild_id) if guild_id else ECONOMY_GLOBAL_KEY
        if guild_key not in self.guild_cache:
            self.guild_cache[guild_key] = self._load_guild(guild_key)
        return self.guild_cache[guild_key]

    def reset_current(self):
        guild_id = get_current_economy_key()
        self._delete_guild_users_from_db(guild_id)
        self.guild_cache[guild_id] = default_economy()
        self.save_all()

    def reset_guild(self, guild_id):
        guild_key = str(guild_id) if guild_id else ECONOMY_GLOBAL_KEY
        self._delete_guild_users_from_db(guild_key)
        self.guild_cache[guild_key] = default_economy()
        self.save_all()

    def _delete_guild_users_from_db(self, guild_key: str):
        self._ensure_conn()
        with self.conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM economy_users WHERE guild_id = %s", (str(guild_key),)
            )

    def configured_treasure_guild_ids(self) -> list:
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
        return {}  # Deprecated

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
                    "INSERT INTO economy_guilds (guild_id, data) VALUES (%s, %s) "
                    "ON CONFLICT (guild_id) DO UPDATE SET data = EXCLUDED.data",
                    (str(guild_id), json.dumps(data_copy, ensure_ascii=False))
                )
                for user_id, user_data in users.items():
                    cursor.execute(
                        "INSERT INTO economy_users (guild_id, user_id, data) "
                        "VALUES (%s, %s, %s) "
                        "ON CONFLICT (guild_id, user_id) DO UPDATE SET data = EXCLUDED.data",
                        (str(guild_id), str(user_id), json.dumps(user_data, ensure_ascii=False))
                    )


def save_economy():
    """Сохранить все данные экономики в БД."""
    from src import state
    state.economy_data.save_all()


# ──────────────────────────────────────────────────────────────
#  АККАУНТ ПОЛЬЗОВАТЕЛЯ
# ──────────────────────────────────────────────────────────────

def get_account(user_id) -> dict:
    """Получить или создать аккаунт пользователя в текущем контексте гильдии."""
    from src import state
    user_key = str(user_id)
    account = state.economy_data["users"].setdefault(
        user_key,
        {
            "cash":               0.0,
            "gold":               0.0,
            "treasure_maps":      0,
            "owned_roles":        [],
            "dealer_wagon":       0.0,
            "last_dealer_at":     None,
            "bounty":             default_bounty_data(),
            "moonshine":          default_moonshine_data(),
            "naturalist":         default_naturalist_data(),
            "collector":          default_collector_data(),
            "collection_showcase": [],
            "last_work_at":       None,
        },
    )

    # Гарантируем корректность числовых полей
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
    account["bounty"]     = normalize_bounty_data(account.get("bounty"))
    account["moonshine"]  = normalize_moonshine_data(account.get("moonshine"))
    account["naturalist"] = normalize_naturalist_data(account.get("naturalist"))
    account["collector"]  = normalize_collector_data(account.get("collector"))
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
    from src.weapon_system import WEAPON_CATALOG, normalize_weapon_state
    return normalize_weapon_state(account, WEAPON_CATALOG)


# ──────────────────────────────────────────────────────────────
#  КУРС ЗОЛОТА
# ──────────────────────────────────────────────────────────────

def update_gold_rate() -> float:
    """Пересчитать курс золота за пропущенные дни."""
    import random
    from src import state
    current_day = parse_local_date(state.economy_data.get("gold_rate_date", today_iso()))
    target_day  = now_local().date()
    rate        = float(state.economy_data.get("gold_rate", START_GOLD_RATE))

    if current_day > target_day:
        state.economy_data["gold_rate_date"] = today_iso()
        return rate

    while current_day < target_day:
        current_day += timedelta(days=1)
        rng           = random.Random(f"gold-rate:{current_day.isoformat()}")
        change_percent = rng.uniform(-0.018, 0.022)
        new_rate       = round(max(MIN_GOLD_RATE, rate * (1 + change_percent)), 2)
        if new_rate == rate:
            new_rate += 0.01 if rng.random() >= 0.5 else -0.01
        rate = round(max(MIN_GOLD_RATE, new_rate), 2)

    state.economy_data["gold_rate"]      = rate
    state.economy_data["gold_rate_date"] = today_iso()
    return rate
