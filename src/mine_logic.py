"""Логика шахтёрской мини-игры «Глубокая жила» (1898 г., Этап 1)."""

import os
import random
import json
import logging
from datetime import date

import psycopg2
import psycopg2.extras

from emoji_config import (
    EMOJI_ORE_COAL,
    EMOJI_ORE_IRON,
    EMOJI_ORE_COPPER,
    EMOJI_ORE_SILVER,
    EMOJI_ORE_GOLD,
    EMOJI_BAR_IRON,
    EMOJI_BAR_COPPER,
    EMOJI_BAR_SILVER,
    EMOJI_GEM_CRYSTAL,
    EMOJI_GEM_AMETHYST,
    EMOJI_GEM_EMERALD,
    EMOJI_GEM_DIAMOND,
    EMOJI_BLOCKED,
    EMOJI_MINE_DIG,
    EMOJI_WARNING,
)

# Kept as a compatibility constant for older imports.  MineDB no longer uses a
# local SQLite file: Render's filesystem is ephemeral, so mine progress must
# live in the same PostgreSQL instance as the rest of the bot data.
MINE_DB_FILE = "data/mine.db"
MINER_ROLE_KEY = "miner"
DAILY_MINE_LIMIT = 5
OIL_PER_MINES = 3   # 1 фляга масла расходуется каждые N кубов

# ─────────────────────────────────────────────────
#  КИРКИ
# ─────────────────────────────────────────────────
PICKAXES = {
    "basic": {
        "name": "Обычная кирка",
        "max_durability": 60,
        "price": 0.0,
        "ore_bonus": 0.0,
        "break_chance": 0.05,
    },
    "steel": {
        "name": "Стальная кирка",
        "max_durability": 150,
        "price": 50.0,
        "ore_bonus": 0.08,
        "break_chance": 0.02,
    },
    "putilov": {
        "name": "Кирка Annesburg Mining Co.",
        "max_durability": 300,
        "price": 150.0,
        "ore_bonus": 0.18,
        "break_chance": 0.005,
    },
}

# ─────────────────────────────────────────────────
#  МАГАЗИН (расходники)
# ─────────────────────────────────────────────────
SHOP_ITEMS = {
    "oil": {
        "name": "Масло для фонаря",
        "price": 1.00,
        "unit": "фляга",
        "description": "Фонарь горит 3 куба на одну флягу. Без масла — штраф и риск не найти руду.",
    },
    "wood": {
        "name": "Крепёжный лес",
        "price": 1.50,
        "unit": "бревно",
        "description": "Ставится в выработку на глубине >50 м. Предотвращает обвал.",
    },
    "dynamite": {
        "name": "Динамит",
        "price": 5.0,
        "unit": "патрон",
        "description": "Вскрывает 3 куба разом, но рушит крепь и может испортить часть руды.",
    },
    "canary": {
        "name": "Канарейка",
        "price": 3.0,
        "unit": "птица",
        "description": "Предупредит о рудничном газе. Одноразовая. Берегите живую душу.",
    },
    "pickaxe_steel": {
        "name": "Стальная кирка",
        "price": 50.0,
        "unit": "штука",
        "description": "Прочнее обычной, бьёт точнее. Служит долго.",
    },
    "pickaxe_putilov": {
        "name": "Кирка Annesburg Mining Co.",
        "price": 150.0,
        "unit": "штука",
        "description": "Элитный инструмент с клеймом Annesburg Mining Co. Самый надёжный.",
    },
}

# ─────────────────────────────────────────────────
#  СЛОИ ПОРОД
# ─────────────────────────────────────────────────
DEPTH_LAYERS = [
    {
        "min": 0, "max": 20,
        "name": "Пласт Роанок-Ридж",
        "rock": [
            "жёлтая глина с галькой",
            "мягкий известняк с трещинами",
            "песчаник с прожилками",
            "щебень и уплотнённый грунт",
        ],
        "ores": {
            "coal": {"chance": 0.32, "amount": (1, 4)},
        },
        "find_chance": 0.005,
        "empty_chance": 0.68,
        "gas_chance": 0.0,
        "collapse_risk": 0.0,
    },
    {
        "min": 20, "max": 50,
        "name": "Железная жила Аннесберга",
        "rock": [
            "серый сланец с ржавыми прожилками",
            "твёрдый известняк",
            "красная глина с окислами железа",
            "плотный песчаник",
        ],
        "ores": {
            "coal":   {"chance": 0.10, "amount": (1, 3)},
            "iron":   {"chance": 0.22, "amount": (1, 3)},
            "copper": {"chance": 0.12, "amount": (1, 2)},
        },
        "find_chance": 0.01,
        "empty_chance": 0.48,
        "gas_chance": 0.05,
        "collapse_risk": 0.0,
    },
    {
        "min": 50, "max": 100,
        "name": "Серебряный уступ Гриззли",
        "rock": [
            "гранит с кварцевыми жилами",
            "тёмный базальт",
            "сланец со слюдяными включениями",
            "монолитная порода с трещинами",
        ],
        "ores": {
            "iron":   {"chance": 0.10, "amount": (1, 2)},
            "copper": {"chance": 0.08, "amount": (1, 2)},
            "silver": {"chance": 0.20, "amount": (1, 2)},
        },
        "find_chance": 0.02,
        "empty_chance": 0.42,
        "gas_chance": 0.12,
        "collapse_risk": 0.12,
    },
    {
        "min": 100, "max": 150,
        "name": "Золотая жила Камберленда",
        "rock": [
            "чёрный базальт в серных кристаллах",
            "кварцевая жила с блёстками",
            "кристаллический гранит",
            "порода в железных подтёках",
        ],
        "ores": {
            "silver": {"chance": 0.10, "amount": (1, 2)},
            "gold":   {"chance": 0.18, "amount": (1, 2)},
        },
        "find_chance": 0.03,
        "empty_chance": 0.44,
        "gas_chance": 0.22,
        "collapse_risk": 0.22,
    },
    {
        "min": 150, "max": 9999,
        "name": "Чёрный провал Роанок",
        "rock": [
            "обожжённый базальт с красными прожилками",
            "порода в серных натёках",
            "чёрный гранит, горячий на ощупь",
        ],
        "ores": {
            "gold": {"chance": 0.20, "amount": (1, 3)},
        },
        "find_chance": 0.05,
        "empty_chance": 0.32,
        "gas_chance": 0.35,
        "collapse_risk": 0.40,
    },
]

# ─────────────────────────────────────────────────
#  РУДЫ
# ─────────────────────────────────────────────────
ORE_NAMES = {
    "coal":   "уголь",
    "iron":   "железная руда",
    "copper": "медная руда",
    "silver": "серебряная руда",
    "gold":   "золотая руда",
}

ORE_SELL_PRICE = {
    "coal":   0.20,
    "iron":   0.40,
    "copper": 0.65,
    "silver": 1.80,
    "gold":   5.00,
}

ORE_EMOJIS = {
    "coal":   EMOJI_ORE_COAL,
    "iron":   EMOJI_ORE_IRON,
    "copper": EMOJI_ORE_COPPER,
    "silver": EMOJI_ORE_SILVER,
    "gold":   EMOJI_ORE_GOLD,
}

BAR_EMOJIS = {
    "iron_bar":   EMOJI_BAR_IRON,
    "copper_bar": EMOJI_BAR_COPPER,
    "silver_bar": EMOJI_BAR_SILVER,
}

# ─────────────────────────────────────────────────
#  ПЕРЕПЛАВКА
# ─────────────────────────────────────────────────
# Сколько единиц экономического золота даёт 1 партия переплавки (2 золотой руды)
MINE_GOLD_TO_ECONOMY_RATE = 0.10

SMELT_RECIPES = {
    "iron":   {"ore_per_bar": 3, "fee": 0.50, "bar_key": "iron_bar",   "bar_name": "железный слиток",   "bar_sell": 1.80},
    "copper": {"ore_per_bar": 3, "fee": 0.65, "bar_key": "copper_bar", "bar_name": "медный слиток",     "bar_sell": 2.40},
    "silver": {"ore_per_bar": 2, "fee": 1.00, "bar_key": "silver_bar", "bar_name": "серебряный слиток", "bar_sell": 6.00},
    # gold → не создаёт слиток, а начисляет экономическое золото (account["gold"])
    "gold":   {"ore_per_bar": 2, "fee": 2.00, "economy_gold": True,
               "bar_key": None, "bar_name": "золото", "bar_sell": 0},
}

BAR_NAMES      = {r["bar_key"]: r["bar_name"] for r in SMELT_RECIPES.values() if not r.get("economy_gold")}
BAR_SELL_PRICE = {r["bar_key"]: r["bar_sell"] for r in SMELT_RECIPES.values() if not r.get("economy_gold")}

# ─────────────────────────────────────────────────
#  ДРАГОЦЕННЫЕ КАМНИ
# ─────────────────────────────────────────────────
# Коэффициент «ювелирной вагонетки» (Этап 2). Сейчас = 1.0 (без бонуса).
JEWELRY_WAGON_BONUS = 1.5

GEMS = {
    "crystal":  {"name": "горный хрусталь", "emoji": EMOJI_GEM_CRYSTAL,  "min_depth": 30,  "chance": 0.040, "sell": 3.50},
    "amethyst": {"name": "аметист",         "emoji": EMOJI_GEM_AMETHYST, "min_depth": 60,  "chance": 0.025, "sell": 9.00},
    "emerald":  {"name": "изумруд",         "emoji": EMOJI_GEM_EMERALD,  "min_depth": 100, "chance": 0.015, "sell": 22.00},
    "diamond":  {"name": "алмаз",           "emoji": EMOJI_GEM_DIAMOND,  "min_depth": 150, "chance": 0.008, "sell": 50.00},
}

GEM_NAMES = {k: v["name"] for k, v in GEMS.items()}
GEM_SELL  = {k: v["sell"] for k, v in GEMS.items()}

# ─────────────────────────────────────────────────
#  УКРАШЕНИЯ (ювелир)
# ─────────────────────────────────────────────────
JEWELRY_KEY_PREFIX = "jewel_"
JEWELRY_VALUE_MULT = 2.5   # украшение стоит в 2.5× дороже суммы слитка и камня
JEWELRY_FEE_PCT    = 0.20  # такса ювелира — 20% от стоимости материалов

# Типы украшений: ключ → (существительное, род для согласования)
FORGE_TEMPLATES = {
    "ring":    {"noun": "перстень",  "gender": "м"},
    "brooch":  {"noun": "брошь",     "gender": "ж"},
    "pendant": {"noun": "медальон",  "gender": "м"},
    "earring": {"noun": "серьги",    "gender": "мн"},
    "pin":     {"noun": "заколка",   "gender": "ж"},
}

METAL_ADJ = {
    "gold":   {"м": "Золотой",    "ж": "Золотая",    "мн": "Золотые"},
    "silver": {"м": "Серебряный", "ж": "Серебряная", "мн": "Серебряные"},
}

GEM_PREP = {  # предлог «с» + творительный падеж
    "crystal":  "с горным хрусталём",
    "amethyst": "с аметистом",
    "emerald":  "с изумрудом",
    "diamond":  "с алмазом",
}

FORGE_DONE_LINES = [
    "Готово, приятель. Такая вещь и в Сен-Дени уйдёт мигом.",
    "Ювелир склонился над тиглями… и поднял голову с улыбкой.",
    "— Держите, — кивнул мастер. — Даже у богачей Сен-Дени такого не найдётся.",
    "Пламя горелки стихло. Украшение остыло и засверкало.",
    "— Хорошие материалы дали хорошую работу, — буркнул мастер.",
]

GEM_FIND_LINES = [
    "В породе блеснула грань.",
    "Камень выпал из матрицы прямо в ладонь.",
    "Кирка вскрыла полость — и там он лежал.",
    "Порода иногда хранит подарки.",
]

# ─────────────────────────────────────────────────
#  РЕДКИЕ НАХОДКИ
# ─────────────────────────────────────────────────
RARE_FINDS = [
    {
        "key": "samorodok",
        "name": "самородок из Камберленда",
        "sell": 12.0,
        "desc": "Тяжёлый самородок с насечкой старателя. Роанок-Ридж хранит такие нечасто.",
    },
    {
        "key": "coins_tsar",
        "name": "серебряные доллары 1878 года",
        "sell": 7.0,
        "desc": "Горсть потемневших долларов. Похоже, чей-то тайник так и не дождался хозяина.",
    },
    {
        "key": "rail_putilov",
        "name": "обломок рельса Annesburg Mining Co.",
        "sell": 4.0,
        "desc": "Тяжёлый кусок узкоколейки. Фирменное клеймо ещё различимо под угольной пылью.",
    },
    {
        "key": "watch_gold",
        "name": "золотые карманные часы",
        "sell": 18.0,
        "desc": "Инкрустированная крышка. Механизм стоит, но золото вечно.",
    },
    {
        "key": "compass_old",
        "name": "старинный компас",
        "sell": 9.0,
        "desc": "Медный. Стрелка подрагивает — магнитная аномалия рядом.",
    },
    {
        "key": "ingot_kazenny",
        "name": "слиток со штампом Гриззли",
        "sell": 22.0,
        "desc": "Серебро со старым штампом старательской артели. Откуда оно в этой выработке?",
    },
    {
        "key": "notebook_miner",
        "name": "дневник шахтёра Аннесберга",
        "sell": 5.0,
        "desc": "Страницы слиплись от сырости. Внутри — набросок жил и несколько имён, зачёркнутых углём.",
    },
]

FIND_BY_KEY   = {f["key"]: f for f in RARE_FINDS}
FIND_NAMES    = {f["key"]: f["name"] for f in RARE_FINDS}
FIND_SELL     = {f["key"]: f["sell"] for f in RARE_FINDS}

# Объединённые справочники для продажи (руды, слитки, находки, камни; украшения — динамически)
ALL_SELLABLE_NAMES = {}
ALL_SELLABLE_NAMES.update(ORE_NAMES)
ALL_SELLABLE_NAMES.update(BAR_NAMES)
ALL_SELLABLE_NAMES.update(FIND_NAMES)
ALL_SELLABLE_NAMES.update(GEM_NAMES)

ALL_SELL_PRICES = {}
ALL_SELL_PRICES.update(ORE_SELL_PRICE)
ALL_SELL_PRICES.update(BAR_SELL_PRICE)
ALL_SELL_PRICES.update(FIND_SELL)
ALL_SELL_PRICES.update(GEM_SELL)

# ─────────────────────────────────────────────────
#  АТМОСФЕРНЫЕ ТЕКСТЫ
# ─────────────────────────────────────────────────
ATMOSPHERE_TAGS = [
    "Керосинка чадит — тени пляшут по стенам.",
    "Доски крепи скрипят. Порода давит сверху.",
    "Воздух спёртый, фонарь тускнеет.",
    "Пар от лебёдки свистит где-то наверху.",
    "Капли воды падают с потолка — кап, кап.",
    "Вдали глухой удар. Где-то рвут динамитом.",
    "Пыль оседает медленно.",
    "Стены чёрные от угольной пыли.",
    "Запах серы. Поглядывайте на фонарь.",
    "Скрипит вагонетка на далёком рельсе.",
    "Темнота здесь живая.",
    "Тихо. Только порода потрескивает.",
]

GAS_WARNINGS = [
    "Пламя в фонаре вдруг стало синим — рудничный газ!",
    "Воздух стал вязким, голова кружится. Углекислота.",
    "Из трещины потянуло едкой вонью. Дышать тяжело.",
    "Глаза щиплет. Что-то нехорошее в этом кубе.",
]

COLLAPSE_WARNINGS = [
    "Трещина в породе поползла вверх — обвал!",
    "Потолок просел с глухим треском.",
    "Доски разлетелись щепой — порода пошла вниз.",
]

NO_OIL_LINES = [
    "Фонарь погас. В кромешной тьме почти ничего не видно.",
    "Масло кончилось. Работаете наощупь — удача против вас.",
]

EMPTY_HITS = [
    "Порода крошится, но руды нет.",
    "Только щебень и пустая галька.",
    "Кирка бьёт по мёртвому камню — пусто.",
    "Ни прожилки. Жила ушла куда-то в сторону.",
    "Куб вынут — сплошная порода без ценного.",
    "Здесь ничего нет. Камень и камень.",
]

PICKAXE_HIT_LINES = [
    "Кирка хрустнула — попался кремний.",
    "Удар по скрытой жиле. Инструмент жалуется.",
    "Щелчок в рукоятке. Прочность снизилась.",
]


# ─────────────────────────────────────────────────
#  БАЗА ДАННЫХ
# ─────────────────────────────────────────────────
class MineDB:
    """Persistent mine storage backed by PostgreSQL.

    The public methods intentionally match the former SQLite implementation,
    so the Discord UI can use the storage without knowing where it lives.
    """

    def __init__(self, db_url: str | None = None):
        # Older callers passed ``MINE_DB_FILE``.  Treat a file path as the
        # legacy value and use DATABASE_URL instead, rather than silently
        # creating a new non-persistent database.
        if not db_url or "://" not in db_url:
            db_url = os.environ.get("DATABASE_URL")
        self.db_url = self._normalize_db_url(db_url) if db_url else None
        self.conn = None

    @staticmethod
    def _normalize_db_url(url: str) -> str:
        return (
            url.replace("postgresql+asyncpg://", "postgresql://")
            .replace("postgresql+psycopg2://", "postgresql://")
            .replace("postgres://", "postgresql://")
        )

    def _ensure_conn(self):
        if self.conn is None:
            if not self.db_url:
                raise RuntimeError("DATABASE_URL is required for mine storage")
            self.conn = psycopg2.connect(
                self.db_url,
                cursor_factory=psycopg2.extras.DictCursor,
            )
            self.conn.autocommit = True
            self._init_tables()
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except Exception:
            logging.warning("MineDB: connection lost, reconnecting")
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = psycopg2.connect(
                self.db_url,
                cursor_factory=psycopg2.extras.DictCursor,
            )
            self.conn.autocommit = True

    def _init_tables(self):
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS mine_players (
                guild_id           TEXT NOT NULL,
                discord_id         TEXT NOT NULL,
                pickaxe_type       TEXT    DEFAULT 'basic',
                pickaxe_durability INTEGER DEFAULT 60,
                oil_units          INTEGER DEFAULT 5,
                wood_count         INTEGER DEFAULT 0,
                dynamite_count     INTEGER DEFAULT 0,
                canary_count       INTEGER DEFAULT 0,
                daily_mines_left   INTEGER DEFAULT 3,
                last_mine_date     TEXT    DEFAULT '',
                current_depth      INTEGER DEFAULT 0,
                total_mined        INTEGER DEFAULT 0,
                inventory          TEXT    DEFAULT '{}',
                PRIMARY KEY (guild_id, discord_id)
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS mine_guild (
                guild_id    TEXT PRIMARY KEY,
                shaft_depth INTEGER DEFAULT 0
            )
            """)

    # ── Игрок ──────────────────────────────────────
    def get_player(self, guild_id: str, discord_id: str) -> dict:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mine_players (guild_id, discord_id) VALUES (%s, %s) "
                "ON CONFLICT (guild_id, discord_id) DO NOTHING",
                (str(guild_id), str(discord_id)),
            )
            cur.execute(
                "SELECT * FROM mine_players WHERE guild_id = %s AND discord_id = %s",
                (str(guild_id), str(discord_id)),
            )
            row = cur.fetchone()
        p = dict(row)
        try:
            p["inventory"] = json.loads(p["inventory"] or "{}")
        except (json.JSONDecodeError, TypeError):
            p["inventory"] = {}
        return p

    def save_player(self, guild_id: str, discord_id: str, p: dict):
        inv_json = json.dumps(p.get("inventory", {}), ensure_ascii=False)
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute("""
            INSERT INTO mine_players
                (guild_id, discord_id, pickaxe_type, pickaxe_durability,
                 oil_units, wood_count, dynamite_count, canary_count,
                 daily_mines_left, last_mine_date, current_depth, total_mined, inventory)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(guild_id, discord_id) DO UPDATE SET
                pickaxe_type       = excluded.pickaxe_type,
                pickaxe_durability = excluded.pickaxe_durability,
                oil_units          = excluded.oil_units,
                wood_count         = excluded.wood_count,
                dynamite_count     = excluded.dynamite_count,
                canary_count       = excluded.canary_count,
                daily_mines_left   = excluded.daily_mines_left,
                last_mine_date     = excluded.last_mine_date,
                current_depth      = excluded.current_depth,
                total_mined        = excluded.total_mined,
                inventory          = excluded.inventory
            """, (
                str(guild_id), str(discord_id),
                p.get("pickaxe_type", "basic"),
                p.get("pickaxe_durability", 60),
                p.get("oil_units", 5),
                p.get("wood_count", 0),
                p.get("dynamite_count", 0),
                p.get("canary_count", 0),
                p.get("daily_mines_left", DAILY_MINE_LIMIT),
                p.get("last_mine_date", ""),
                p.get("current_depth", 0),
                p.get("total_mined", 0),
                inv_json,
            ))

    # ── Сервер (общий ствол) ────────────────────────
    def get_guild_shaft(self, guild_id: str) -> int:
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mine_guild (guild_id) VALUES (%s) "
                "ON CONFLICT (guild_id) DO NOTHING",
                (str(guild_id),),
            )
            cur.execute(
                "SELECT shaft_depth FROM mine_guild WHERE guild_id = %s",
                (str(guild_id),),
            )
            row = cur.fetchone()
        return row["shaft_depth"]

    def set_guild_shaft(self, guild_id: str, depth: int):
        self._ensure_conn()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mine_guild (guild_id, shaft_depth) VALUES (%s, %s) "
                "ON CONFLICT(guild_id) DO UPDATE SET shaft_depth = excluded.shaft_depth",
                (str(guild_id), int(depth)),
            )

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None


# ─────────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────────



def get_depth_layer(depth: int) -> dict:
    for layer in DEPTH_LAYERS:
        if layer["min"] <= depth < layer["max"]:
            return layer
    return DEPTH_LAYERS[-1]


def inv_get(player: dict, key: str) -> int:
    return int(player["inventory"].get(key, 0))


def inv_add(player: dict, key: str, amount: int):
    player["inventory"][key] = inv_get(player, key) + amount


def inv_remove(player: dict, key: str, amount: int):
    player["inventory"][key] = max(0, inv_get(player, key) - amount)


def reset_daily_if_needed(player: dict):
    """Сбросить daily_mines_left если наступил новый день (UTC)."""
    today = date.today().isoformat()
    if player.get("last_mine_date", "") != today:
                if rest2.startswith(gem_key + "_"):
                    type_key = rest2[len(gem_key) + 1:]
                    if type_key in FORGE_TEMPLATES:
                        return metal, gem_key, type_key
    return None


def get_jewelry_name(key: str) -> str:
    """Сгенерировать название украшения по ключу инвентаря."""
    parsed = parse_jewelry_key(key)
    if not parsed:
        return key
    metal, gem_key, type_key = parsed
    tmpl = FORGE_TEMPLATES[type_key]
    adj = METAL_ADJ[metal][tmpl["gender"]]
    prep = GEM_PREP.get(gem_key, f"с {gem_key}")
    return f"{adj} {tmpl['noun']} {prep}"


def get_jewelry_sell_price(key: str) -> float:
    """Вычислить цену продажи украшения по ключу (2.5× стоимости материалов)."""
    parsed = parse_jewelry_key(key)
    if not parsed:
        return 0.0
    metal, gem_key, _ = parsed
    bar_val = BAR_SELL_PRICE.get(f"{metal}_bar", 0.0)
    gem_val = GEMS.get(gem_key, {}).get("sell", 0.0)
    return round((bar_val + gem_val) * JEWELRY_VALUE_MULT, 2)


def get_item_name(key: str):
    """Универсально: вернуть название предмета по ключу инвентаря."""
    name = ALL_SELLABLE_NAMES.get(key)
    if name:
        return name
    if key.startswith(JEWELRY_KEY_PREFIX):
        return get_jewelry_name(key)
    return None


def get_item_price(key: str) -> float:
    """Универсально: вернуть цену продажи предмета по ключу."""
    if key in ALL_SELL_PRICES:
        return ALL_SELL_PRICES[key]
    if key.startswith(JEWELRY_KEY_PREFIX):
        return get_jewelry_sell_price(key)
    return 0.0


def roll_gem(depth: int, jewelry_bonus: float = 1.0):
    """Бросок на нахождение драгоценного камня. Возвращает dict с полем 'key' или None."""
    candidates = sorted(
        ((k, v) for k, v in GEMS.items() if depth >= v["min_depth"]),
        key=lambda x: -x[1]["min_depth"],  # редкие проверяются первыми
    )
    for gem_key, gem in candidates:
        if random.random() < gem["chance"] * jewelry_bonus:
            return {**gem, "key": gem_key}
    return None


# ─────────────────────────────────────────────────
#  ОСНОВНАЯ МЕХАНИКА ДОБЫЧИ
# ─────────────────────────────────────────────────
def roll_mine(player: dict, has_oil: bool) -> dict:
    """
    Бросок добычи одного куба. Мутирует inventory и некоторые поля player.
    Возвращает dict с результатами для формирования ответа.
    """
    layer = get_depth_layer(player["current_depth"])
    pickaxe = PICKAXES.get(player.get("pickaxe_type", "basic"), PICKAXES["basic"])

    result = {
        "ore": None,
        "ore_amount": 0,
        "find": None,
        "gem": None,          # драгоценный камень (независимый бросок)
        "gas": False,
        "gas_blocked": False,
        "collapse": False,
        "collapse_blocked": False,
        "pickaxe_damaged": False,
        "events": [],   # список строк атмосферных событий
    }

    # ── Газ ──────────────────────────────────────
    if random.random() < layer["gas_chance"]:
        result["gas"] = True
        if player.get("canary_count", 0) > 0:
            player["canary_count"] -= 1
            result["gas_blocked"] = True
            result["events"].append(
                "🐦 Канарейка упала! Газ обнаружен вовремя. Птица погибла, вы успели уйти."
            )
        else:
            result["events"].append(f"{EMOJI_WARNING} {random.choice(GAS_WARNINGS)}")

    # -- Газ без защиты: попытка НЕ сгорает, добыча снижается вдвое
    gas_penalty = result["gas"] and not result["gas_blocked"]

    # ── Обвал ────────────────────────────────────
    if player["current_depth"] > 50 and random.random() < layer["collapse_risk"]:
        if player.get("wood_count", 0) > 0:
            player["wood_count"] -= 1
            result["collapse_blocked"] = True
            result["events"].append("🪵 Крепь выдержала! Использовано 1 бревно крепёжного леса.")
        else:
            result["collapse"] = True
            result["events"].append(f"{EMOJI_WARNING} {random.choice(COLLAPSE_WARNINGS)}")

    # ── Нет масла: предупреждение ─────────────────
    if not has_oil:
        result["events"].append(f"🪔 {random.choice(NO_OIL_LINES)}")

    # ── Прочность кирки ──────────────────────────
    if random.random() < pickaxe["break_chance"]:
        damage = 2 if player["pickaxe_type"] == "basic" else 1
        player["pickaxe_durability"] = max(0, player["pickaxe_durability"] - damage)
        result["pickaxe_damaged"] = True
        if player["pickaxe_durability"] <= 10:
            result["events"].append(
                f"{EMOJI_MINE_DIG} {random.choice(PICKAXE_HIT_LINES)} "
                f"Прочность: **{player['pickaxe_durability']}**. Пора задуматься о замене."
            )

    # ── Без масла: шанс пропустить всё ───────────
    if not has_oil and random.random() < 0.35:
        result["events"].append("Ничего не нашли — в темноте ничего не видно.")
        return result

    # ── Драгоценный камень (независимый бросок) ───
    gem = roll_gem(player["current_depth"])
    if gem:
        result["gem"] = gem
        inv_add(player, gem["key"], 1)
        result["events"].append(f"{EMOJI_GEM_DIAMOND} {random.choice(GEM_FIND_LINES)}")

    # ── Редкая находка ────────────────────────────
    if random.random() < layer["find_chance"]:
        find = random.choice(RARE_FINDS)
        result["find"] = find
        inv_add(player, find["key"], 1)
        return result

    # ── Руда ─────────────────────────────────────
    ore_bonus = pickaxe["ore_bonus"]
    roll = random.random()
    cumulative = 0.0
    for ore_key, ore_data in layer["ores"].items():
        adjusted_chance = ore_data["chance"] + ore_bonus * 0.5
        cumulative += adjusted_chance
    if result["collapse"]:
        result["events"].append("Обвал завалил проход — ничего не взяли.")
    else:
        result["events"].append(random.choice(EMPTY_HITS))
    return result
