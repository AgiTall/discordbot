"""Persistent weapon loadout, ammunition and condition helpers."""

SIDEARM_CLASSES = {"revolver", "pistol"}
LONGARM_CLASSES = {"repeater", "rifle", "shotgun"}

AMMO_CAPACITY_PER_WEAPON = {
    "revolver": 200,
    "pistol": 100,
    "repeater": 200,
    "rifle": 100,
    "shotgun": 60,
}

WEAPON_CLASS_NAMES = {
    "revolver": "револьвер",
    "pistol": "пистолет",
    "repeater": "карабин",
    "rifle": "винтовка",
    "shotgun": "дробовик",
}

WEAPON_DISPLAY_NAMES = {
    "revolver_cattleman": "Револьвер Cattleman",
    "revolver_doubleaction": "Револьвер Double-Action",
    "revolver_doubleaction_gambler": "Револьвер Игрока",
    "revolver_lemat": "Револьвер LeMat",
    "revolver_schofield": "Револьвер Schofield",
    "pistol_mauser": "Пистолет Mauser",
    "pistol_semiauto": "Полуавтоматический пистолет",
    "pistol_volcanic": "Пистолет Volcanic",
    "repeater_carbine": "Карабин Repeater",
    "repeater_henry": "Карабин Litchfield",
    "repeater_lancaster": "Карабин Lancaster",
    "rifle_boltaction": "Болтовая винтовка",
    "rifle_elephant": "Слонобой",
    "rifle_springfield": "Винтовка Springfield",
    "rifle_varmint": "Варминт-винтовка",
    "sniperrifle_carcano": "Винтовка Carcano",
    "sniperrifle_rollingblock": "Винтовка Rolling Block",
    "shotgun_doublebarrel": "Двуствольный дробовик",
    "shotgun_doublebarrel_exotic": "Редкий дробовик",
    "shotgun_pump": "Помповый дробовик",
    "shotgun_repeating": "Дробовик рычажного действия",
    "shotgun_sawedoff": "Обрез",
    "shotgun_semiauto": "Полуавтоматический дробовик",
}

WEAPON_EMOJI_IDS = {
    "sniperrifle_rollingblock": 1527598337795166288,
    "sniperrifle_carcano": 1527598336234881164,
    "shotgun_semiauto": 1527598334515085362,
    "shotgun_sawedoff": 1527598332736966686,
    "shotgun_repeating": 1527598330899730513,
    "shotgun_pump": 1527598328609505291,
    "shotgun_doublebarrel_exotic": 1527598326894170162,
    "shotgun_doublebarrel": 1527598325308723280,
    "rifle_varmint": 1527598323840585811,
    "rifle_springfield": 1527598322087628930,
    "rifle_elephant": 1527598319528968303,
    "rifle_boltaction": 1527598317817827449,
    "revolver_schofield": 1527598316140101642,
    "revolver_lemat": 1527598313870852147,
    "revolver_doubleaction_gambler": 1527598312608497674,
    "revolver_doubleaction": 1527598310792233000,
    "revolver_cattleman": 1527598299501035660,
    "repeater_lancaster": 1527598297710071858,
    "repeater_henry": 1527598295734685748,
    "repeater_carbine": 1527598294010695801,
    "pistol_volcanic": 1527598284447940739,
    "pistol_semiauto": 1527598232459411607,
    "pistol_mauser": 1527598229410287648,
}


def weapon_emoji(item_key: str) -> str:
    emoji_id = WEAPON_EMOJI_IDS.get(item_key)
    # The ID identifies the emoji; a short markup name avoids Discord's name limit.
    return f"<:gun:{emoji_id}>" if emoji_id else "🔫"


_CLASS_CATEGORY = {
    "revolver": "revolvers", "pistol": "pistols", "repeater": "carbines",
    "rifle": "rifles", "shotgun": "shotguns",
}
WEAPON_CATALOG = {
    key: {"category": _CLASS_CATEGORY[
        "revolver" if key.startswith("revolver_") else
        "pistol" if key.startswith("pistol_") else
        "repeater" if key.startswith("repeater_") else
        "shotgun" if key.startswith("shotgun_") else "rifle"
    ]}
    for key in WEAPON_DISPLAY_NAMES
}

AMMO_TYPE_NAMES = {
    "normal": "обычные",
    "split_point": "с надрезом",
    "high_velocity": "скоростные",
    "express": "экспресс",
    "explosive": "разрывные экспресс",
}

AMMO_EMOJIS = {
    "split_point": "<:bullet_split_point:1527591455395418232>",
    "normal": "<:bullet_normal:1527591453784670308>",
    "high_velocity": "<:bullet_high_velocity:1527591452207485118>",
    "explosive": "<:bullet_express_explosive:1527591450043355216>",
    "express": "<:bullet_express:1527591448214503535>",
}

AMMO_ROLL_BONUSES = {
    "normal": 0,
    "split_point": 1,
    "high_velocity": 1,
    "express": 2,
    "explosive": 3,
}
AMMO_USE_PRIORITY = ("explosive", "express", "high_velocity", "split_point", "normal")


def weapon_class(item_key: str, item_data: dict | None = None) -> str | None:
    category = (item_data or {}).get("category")
    if category == "revolvers" or item_key.startswith("revolver_"):
        return "revolver"
    if category == "pistols" or item_key.startswith("pistol_"):
        return "pistol"
    if category == "carbines" or item_key.startswith("repeater_"):
        return "repeater"
    if category == "rifles" or item_key.startswith(("rifle_", "sniperrifle_")):
        return "rifle"
    if category == "shotguns" or item_key.startswith("shotgun_"):
        return "shotgun"
    return None


def owned_weapon_keys(account: dict, catalog_items: dict) -> list[str]:
    inventory = account.get("inventory", {})
    return [
        key for key, data in catalog_items.items()
        if weapon_class(key, data) and int(inventory.get(key, 0) or 0) > 0
    ]


def normalize_weapon_state(account: dict, catalog_items: dict) -> dict:
    """Migrate old accounts and sanitize weapon-related state in place."""
    owned = owned_weapon_keys(account, catalog_items)
    owned_set = set(owned)

    condition = account.setdefault("weapon_condition", {})
    if not isinstance(condition, dict):
        condition = account["weapon_condition"] = {}
    for key in owned:
        try:
            condition[key] = max(0.0, min(100.0, float(condition.get(key, 100.0))))
        except (TypeError, ValueError):
            condition[key] = 100.0
    for key in list(condition):
        if key not in owned_set:
            condition.pop(key, None)

    had_loadout = isinstance(account.get("weapon_loadout"), dict)
    loadout = account.setdefault("weapon_loadout", {"sidearms": [], "longarms": []})
    if not isinstance(loadout, dict):
        loadout = account["weapon_loadout"] = {"sidearms": [], "longarms": []}

    sidearms = [
        key for key in loadout.get("sidearms", [])
        if key in owned_set and weapon_class(key, catalog_items.get(key)) in SIDEARM_CLASSES
    ]
    # Two sidearms are allowed only when both use the same ammunition class.
    if sidearms:
        first_class = weapon_class(sidearms[0], catalog_items.get(sidearms[0]))
        sidearms = [
            key for key in sidearms
            if weapon_class(key, catalog_items.get(key)) == first_class
        ][:2]
    if not sidearms and not had_loadout:
        candidates = [key for key in owned if weapon_class(key, catalog_items.get(key)) in SIDEARM_CLASSES]
        if candidates:
            first_class = weapon_class(candidates[0], catalog_items.get(candidates[0]))
            sidearms = [key for key in candidates if weapon_class(key, catalog_items.get(key)) == first_class][:2]

    longarms = [
        key for key in loadout.get("longarms", [])
        if key in owned_set and weapon_class(key, catalog_items.get(key)) in LONGARM_CLASSES
    ][:2]
    if not longarms and not had_loadout:
        longarms = [key for key in owned if weapon_class(key, catalog_items.get(key)) in LONGARM_CLASSES][:2]

    loadout["sidearms"] = list(dict.fromkeys(sidearms))
    loadout["longarms"] = list(dict.fromkeys(longarms))

    ammo = account.setdefault("ammo", {})
    if not isinstance(ammo, dict):
        ammo = account["ammo"] = {}
    for class_key in AMMO_CAPACITY_PER_WEAPON:
        class_ammo = ammo.setdefault(class_key, {})
        if not isinstance(class_ammo, dict):
            class_ammo = ammo[class_key] = {}
        for ammo_type in AMMO_TYPE_NAMES:
            try:
                class_ammo[ammo_type] = max(0, int(class_ammo.get(ammo_type, 0)))
            except (TypeError, ValueError):
                class_ammo[ammo_type] = 0
    selected_ammo = account.setdefault("selected_ammo", {})
    if not isinstance(selected_ammo, dict):
        selected_ammo = account["selected_ammo"] = {}
    for class_key in AMMO_CAPACITY_PER_WEAPON:
        if selected_ammo.get(class_key) not in AMMO_TYPE_NAMES:
            selected_ammo[class_key] = "normal"
    return account


def equipped_weapon_keys(account: dict) -> list[str]:
    loadout = account.get("weapon_loadout", {})
    return list(loadout.get("sidearms", [])) + list(loadout.get("longarms", []))


def ammo_capacity(account: dict, class_key: str, catalog_items: dict) -> int:
    equipped = [
        key for key in equipped_weapon_keys(account)
        if weapon_class(key, catalog_items.get(key)) == class_key
    ]
    count = len(equipped)
    if class_key in {"revolver", "pistol"}:
        return AMMO_CAPACITY_PER_WEAPON[class_key] * min(count, 2)
    return AMMO_CAPACITY_PER_WEAPON.get(class_key, 0) if count else 0


def ammo_total(account: dict, class_key: str) -> int:
    return sum(max(0, int(value or 0)) for value in account.get("ammo", {}).get(class_key, {}).values())


def equip_weapon(account: dict, item_key: str, catalog_items: dict) -> tuple[bool, str]:
    normalize_weapon_state(account, catalog_items)
    if item_key not in owned_weapon_keys(account, catalog_items):
        return False, "Это оружие не куплено."
    class_key = weapon_class(item_key, catalog_items.get(item_key))
    loadout = account["weapon_loadout"]
    slot_key = "sidearms" if class_key in SIDEARM_CLASSES else "longarms"
    equipped = loadout[slot_key]
    if item_key in equipped:
        return False, "Это оружие уже взято с собой."
    if slot_key == "sidearms":
        if equipped and weapon_class(equipped[0], catalog_items.get(equipped[0])) != class_key:
            return False, "Нельзя одновременно взять револьвер и пистолет. Освободите короткоствольные слоты."
        if len(equipped) >= 2:
            return False, "Оба короткоствольных слота уже заняты."
    elif len(equipped) >= 2:
        return False, "Оба слота крупного оружия уже заняты."
    equipped.append(item_key)
    return True, "Оружие добавлено в снаряжение."


def unequip_weapon(account: dict, item_key: str) -> bool:
    loadout = account.get("weapon_loadout", {})
    for slot_key in ("sidearms", "longarms"):
        equipped = loadout.get(slot_key, [])
        if item_key in equipped:
            equipped.remove(item_key)
            return True
    return False


def condition_stat_multiplier(condition: float) -> float:
    """Condition scales weapon stats from 60% at zero to 100% when clean."""
    return round(0.60 + 0.40 * max(0.0, min(100.0, float(condition))) / 100.0, 3)


def use_weapon_shot(account: dict, catalog_items: dict, wear: float = 1.5) -> dict | None:
    """Fire one equipped weapon, consuming the best available cartridge.

    Returns shot metadata or ``None`` when no equipped weapon has ammunition.
    """
    normalize_weapon_state(account, catalog_items)
    for item_key in equipped_weapon_keys(account):
        class_key = weapon_class(item_key, catalog_items.get(item_key))
        class_ammo = account["ammo"].get(class_key, {})
        selected = account["selected_ammo"].get(class_key, "normal")
        ammo_type = selected if class_ammo.get(selected, 0) > 0 else next(
            (key for key in AMMO_USE_PRIORITY if class_ammo.get(key, 0) > 0), None
        )
        if not ammo_type:
            continue
        account["selected_ammo"][class_key] = ammo_type
        condition = account["weapon_condition"].get(item_key, 100.0)
        multiplier = condition_stat_multiplier(condition)
        # A completely neglected weapon gives -2; a clean one has no penalty.
        condition_modifier = round((multiplier - 1.0) * 5)
        class_ammo[ammo_type] -= 1
        account["weapon_condition"][item_key] = max(0.0, condition - max(0.0, wear))
        return {
            "weapon": item_key,
            "class": class_key,
            "ammo_type": ammo_type,
            "ammo_bonus": AMMO_ROLL_BONUSES[ammo_type],
            "condition_modifier": condition_modifier,
            "condition_before": condition,
            "condition_after": account["weapon_condition"][item_key],
        }
    return None
