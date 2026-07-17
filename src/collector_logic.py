"""Pure game rules for the collector profession."""

from datetime import datetime, timezone
from pathlib import Path
import random

COLLECTOR_ROLE_KEY = "collector"
SHOVEL_PRICE = 35.0
DETECTOR_PRICE = 250.0

_ITEM_DIR = Path(__file__).resolve().parents[1] / "ref" / "collector" / "items"
_ALL = sorted(p.stem for p in _ITEM_DIR.glob("*.png"))

def _eggs(key): return key.startswith("provision_") and key.endswith("_egg")

COLLECTIONS = {
    "tarot": {"name": "Карты Таро", "prefix": "document_card_", "level": 1, "tools": (), "payout": 520, "map_price": 12},
    "bottles": {"name": "Редкий алкоголь", "prefix": "consumable_", "level": 1, "tools": (), "payout": 190, "map_price": 10},
    "flowers": {"name": "Дикие цветы", "prefix": "provision_wldflwr_", "level": 1, "tools": (), "payout": 145, "map_price": 8},
    "eggs": {"name": "Птичьи яйца", "test": _eggs, "level": 2, "tools": (), "payout": 180, "map_price": 10},
    "heirlooms": {"name": "Семейные реликвии", "prefix": "provision_hrlm_", "level": 3, "tools": ("shovel",), "payout": 330, "map_price": 16},
    "arrowheads": {"name": "Наконечники стрел", "prefix": "provision_arrowhead_", "level": 5, "tools": ("shovel",), "payout": 310, "map_price": 18},
    "coins": {"name": "Старинные монеты", "prefix": "provision_coin_", "level": 8, "tools": ("detector",), "payout": 440, "map_price": 24},
    "jewelry": {"name": "Украшения", "prefix": "provision_jewelry_", "level": 10, "tools": ("detector",), "payout": 850, "map_price": 30},
    "fossils": {"name": "Окаменелости", "prefix": "collector_fossil_", "level": 12, "tools": ("shovel", "detector"), "payout": 650, "map_price": 28},
}

def _items(rule):
    if "test" in rule: return tuple(k for k in _ALL if rule["test"](k))
    return tuple(k for k in _ALL if k.startswith(rule["prefix"]) and k != "consumable_plump_bird_thyme_cooked")

COLLECTION_ITEMS = {key: _items(rule) for key, rule in COLLECTIONS.items()}

def default_collector_data():
    return {"level": 1, "xp": 0, "inventory": {}, "maps": {}, "tools": {"shovel": False, "detector": False}, "sets_sold": 0}

def normalize_collector_data(raw):
    data = default_collector_data()
    if isinstance(raw, dict): data.update(raw)
    data["level"] = max(1, min(20, int(data.get("level", 1) or 1)))
    data["xp"] = max(0, int(data.get("xp", 0) or 0))
    data["sets_sold"] = max(0, int(data.get("sets_sold", 0) or 0))
    inv = data.get("inventory") if isinstance(data.get("inventory"), dict) else {}
    valid = {x for values in COLLECTION_ITEMS.values() for x in values}
    clean = {}
    for key, value in inv.items():
        if key not in valid: continue
        try: quantity = max(0, int(value or 0))
        except (TypeError, ValueError): quantity = 0
        if quantity: clean[key] = quantity
    data["inventory"] = clean
    maps = data.get("maps") if isinstance(data.get("maps"), dict) else {}
    data["maps"] = {}
    for key in COLLECTIONS:
        try: data["maps"][key] = max(0, int(maps.get(key, 0) or 0))
        except (TypeError, ValueError): data["maps"][key] = 0
    tools = data.get("tools") if isinstance(data.get("tools"), dict) else {}
    data["tools"] = {"shovel": bool(tools.get("shovel")), "detector": bool(tools.get("detector"))}
    return data

def item_display_name(key):
    prefixes = ("collector_fossil_", "document_card_", "provision_arrowhead_", "provision_coin_", "provision_hrlm_", "provision_jewelry_", "provision_wldflwr_", "provision_", "consumable_")
    value = key
    for prefix in prefixes:
        if value.startswith(prefix): value = value[len(prefix):]; break
    return value.replace("_", " ").title()

def emoji_name(key): return key[:32]

def progress(data, collection):
    inv = data["inventory"]
    items = COLLECTION_ITEMS[collection]
    return sum(inv.get(x, 0) > 0 for x in items), len(items)

def total_items(data): return sum(data["inventory"].values())

def complete_sets(data, collection):
    items = COLLECTION_ITEMS[collection]
    return min((data["inventory"].get(x, 0) for x in items), default=0)

def sell_set(data, collection):
    if complete_sets(data, collection) < 1: return 0
    for item in COLLECTION_ITEMS[collection]:
        data["inventory"][item] -= 1
    data["sets_sold"] += 1
    return COLLECTIONS[collection]["payout"]

def sell_individual_items(data, collection):
    count = 0
    for item in COLLECTION_ITEMS[collection]:
        count += data["inventory"].pop(item, 0)
    unit_price = max(1, COLLECTIONS[collection]["payout"] // len(COLLECTION_ITEMS[collection]) // 2)
    return count, count * unit_price

def begin_search(data, collection):
    rule = COLLECTIONS[collection]
    if data["level"] < rule["level"]: return {"error": "level", "required": rule["level"]}
    missing = [x for x in rule["tools"] if not data["tools"].get(x)]
    if missing: return {"error": "tools", "missing": missing}
    if data["maps"].get(collection, 0) < 1: return {"error": "map"}
    data["maps"][collection] -= 1
    return {"ready": True}

def grant_find(data, collection, rng=None):
    rng = rng or random
    item = rng.choice(COLLECTION_ITEMS[collection])
    data["inventory"][item] = data["inventory"].get(item, 0) + 1
    xp = rng.randint(12, 22); data["xp"] += xp; levels = 0
    while data["level"] < 20 and data["xp"] >= data["level"] * 100:
        data["xp"] -= data["level"] * 100; data["level"] += 1; levels += 1
    return {"found": True, "item": item, "quantity": data["inventory"][item], "xp": xp, "levels": levels}
