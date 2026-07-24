import math
import random
from datetime import datetime, time, timedelta, timezone

from src.xp_utils import apply_role_xp


TRADER_MAX_LEVEL = 20
TRADER_XP_BASE = 180
TRADER_PRODUCTION_SECONDS = 2 * 60
TRADER_SUPPLY_BATCH = 25
TRADER_RESUPPLY_XP = 500
TRADER_ORDER_SUPPLIES_COST = 20.0
TRADER_HUNTING_WAGON_COST = 875.0
TRADER_ROUTE_REQUIRED_LEVEL = 4
TRADER_ROUTE_GOODS = 18
TRADER_ROUTE_CASH = (40.0, 100.0)
TRADER_ROUTE_XP = 300
TRADER_ROUTE_TZ = timezone(timedelta(hours=3))

TRADER_WAGONS = {
    "small": {
        "name": "Маленькая",
        "capacity": 25,
        "cost": 0.0,
        "cash": (50.0, 62.5),
        "xp": (250, 312),
    },
    "medium": {
        "name": "Средняя",
        "capacity": 50,
        "cost": 500.0,
        "cash": (150.0, 187.5),
        "xp": (1250, 1562),
    },
    "large": {
        "name": "Большая",
        "capacity": 100,
        "cost": 750.0,
        "cash": (500.0, 625.0),
        "xp": (2000, 2500),
    },
}


def _now():
    return datetime.now(timezone.utc)


def _parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def default_trader_data():
    return {
        "level": 1,
        "xp": 0,
        "wagon_size": "small",
        "has_hunting_wagon": False,
        "materials": 0.0,
        "goods": 0,
        "supplies_remaining": TRADER_SUPPLY_BATCH,
        "production_updated_at": None,
        "last_trade_route_slot": None,
    }


def normalize_trader_data(trader):
    if not isinstance(trader, dict):
        trader = default_trader_data()

    try:
        trader["level"] = max(1, min(TRADER_MAX_LEVEL, int(trader.get("level", 1))))
    except (TypeError, ValueError):
        trader["level"] = 1
    try:
        trader["xp"] = max(0, int(trader.get("xp", 0)))
    except (TypeError, ValueError):
        trader["xp"] = 0

    wagon_size = str(trader.get("wagon_size", "small"))
    trader["wagon_size"] = wagon_size if wagon_size in TRADER_WAGONS else "small"
    trader["has_hunting_wagon"] = bool(trader.get("has_hunting_wagon", False))

    capacity = get_trader_capacity(trader)
    try:
        trader["materials"] = max(0.0, round(float(trader.get("materials", 0.0)), 2))
    except (TypeError, ValueError):
        trader["materials"] = 0.0
    try:
        trader["goods"] = max(0, min(capacity, int(trader.get("goods", 0))))
    except (TypeError, ValueError):
        trader["goods"] = 0
    try:
        trader["supplies_remaining"] = max(
            0,
            min(TRADER_SUPPLY_BATCH, int(trader.get("supplies_remaining", TRADER_SUPPLY_BATCH))),
        )
    except (TypeError, ValueError):
        trader["supplies_remaining"] = TRADER_SUPPLY_BATCH
    trader.setdefault("production_updated_at", None)
    trader.setdefault("last_trade_route_slot", None)
    return trader


def get_trader_capacity(trader):
    wagon_size = str(trader.get("wagon_size", "small"))
    return TRADER_WAGONS.get(wagon_size, TRADER_WAGONS["small"])["capacity"]


def sync_legacy_trader_fields(account):
    trader = account["trader"]
    capacity = get_trader_capacity(trader)
    account["dealer_wagon"] = round(trader["goods"] / capacity * 100, 2)
    return trader


def get_trader_account(account):
    had_trader = isinstance(account.get("trader"), dict)
    trader = normalize_trader_data(account.get("trader"))
    if not had_trader:
        try:
            legacy_percent = max(0.0, min(100.0, float(account.get("dealer_wagon", 0.0))))
        except (TypeError, ValueError):
            legacy_percent = 0.0
        trader["goods"] = min(
            get_trader_capacity(trader),
            int(round(get_trader_capacity(trader) * legacy_percent / 100)),
        )
    account["trader"] = trader
    return sync_legacy_trader_fields(account)


def update_trader_production(trader, *, now=None):
    trader = normalize_trader_data(trader)
    current = now or _now()
    previous = _parse_datetime(trader.get("production_updated_at"))
    trader["production_updated_at"] = current.isoformat(timespec="seconds")
    if previous is None:
        return 0

    elapsed = max(0.0, (current - previous).total_seconds())
    possible = int(elapsed // TRADER_PRODUCTION_SECONDS)
    if possible <= 0:
        return 0

    capacity_left = get_trader_capacity(trader) - trader["goods"]
    produced = min(
        possible,
        int(math.floor(trader["materials"])),
        trader["supplies_remaining"],
        capacity_left,
    )
    if produced <= 0:
        return 0

    trader["materials"] = round(trader["materials"] - produced, 2)
    trader["goods"] += produced
    trader["supplies_remaining"] -= produced
    return produced


def add_trader_materials(trader, amount):
    amount = max(0.0, float(amount))
    trader["materials"] = round(float(trader.get("materials", 0.0)) + amount, 2)
    return amount


def trader_needs_supplies(trader):
    return (
        trader["supplies_remaining"] <= 0
        and trader["goods"] < get_trader_capacity(trader)
    )


def resupply_trader(trader, *, method):
    if not trader_needs_supplies(trader):
        return False, 0
    trader["supplies_remaining"] = TRADER_SUPPLY_BATCH
    trader["production_updated_at"] = _now().isoformat(timespec="seconds")
    xp = TRADER_RESUPPLY_XP if method == "mission" else 0
    levels = apply_role_xp(trader, xp, TRADER_MAX_LEVEL, TRADER_XP_BASE)
    return True, levels


def can_buy_trader_upgrade(trader, item):
    if item == "medium":
        return trader["wagon_size"] == "small"
    if item == "large":
        return trader["wagon_size"] == "medium"
    if item == "hunting":
        return not trader["has_hunting_wagon"]
    return False


def buy_trader_upgrade(trader, item):
    if not can_buy_trader_upgrade(trader, item):
        return False
    if item in {"medium", "large"}:
        trader["wagon_size"] = item
    elif item == "hunting":
        trader["has_hunting_wagon"] = True
    return True


def roll_trader_delivery(trader, rng=None):
    rng = rng or random
    wagon = TRADER_WAGONS[trader["wagon_size"]]
    cash = round(rng.uniform(*wagon["cash"]), 2)
    xp = rng.randint(*wagon["xp"])
    return cash, xp


def complete_trader_delivery(trader, rng=None):
    capacity = get_trader_capacity(trader)
    if trader["goods"] < capacity:
        return None
    cash, xp = roll_trader_delivery(trader, rng)
    trader["goods"] = 0
    trader["production_updated_at"] = _now().isoformat(timespec="seconds")
    levels = apply_role_xp(trader, xp, TRADER_MAX_LEVEL, TRADER_XP_BASE)
    return cash, xp, levels


def get_trade_route_slot(*, now=None):
    current = (now or _now()).astimezone(TRADER_ROUTE_TZ)
    route_time = current.timetz().replace(tzinfo=None)
    if route_time >= time(22, 52):
        suffix = "22:52"
        route_date = current.date()
    elif route_time >= time(9, 22):
        suffix = "09:22"
        route_date = current.date()
    else:
        suffix = "22:52"
        route_date = (current - timedelta(days=1)).date()
    return f"{route_date.isoformat()}T{suffix}"


def complete_trade_route(trader, *, now=None, rng=None):
    if trader["level"] < TRADER_ROUTE_REQUIRED_LEVEL:
        return None
    slot = get_trade_route_slot(now=now)
    if trader.get("last_trade_route_slot") == slot:
        return None
    rng = rng or random
    capacity = get_trader_capacity(trader)
    goods = min(TRADER_ROUTE_GOODS, capacity - trader["goods"])
    cash = round(rng.uniform(*TRADER_ROUTE_CASH), 2)
    trader["goods"] += goods
    trader["last_trade_route_slot"] = slot
    levels = apply_role_xp(
        trader, TRADER_ROUTE_XP, TRADER_MAX_LEVEL, TRADER_XP_BASE
    )
    return goods, cash, TRADER_ROUTE_XP, levels, slot
