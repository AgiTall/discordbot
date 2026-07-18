"""Company progression and player investment helpers."""

from __future__ import annotations


WHEELER_RAWSON = "wheeler_rawson"

COMPANY_DEFINITIONS = {
    WHEELER_RAWSON: {
        "name": "Wheeler, Rawson & Co.",
        # Cumulative server-wide cash investments required for each level.
        "level_thresholds": (0, 1_500, 5_000, 12_000),
    },
}

# Personal, permanent brand discount. The final catalog discount is capped
# separately so administrator discounts cannot make goods almost free.
INVESTOR_DISCOUNT_TIERS = (
    (5_000, 8),
    (1_500, 6),
    (500, 4),
    (100, 2),
)
MAX_CATALOG_DISCOUNT = 25


def default_company_state() -> dict:
    return {"level": 1, "invested": 0, "investors": {}}


def level_for_investment(company_id: str, invested: int | float) -> int:
    definition = COMPANY_DEFINITIONS[company_id]
    total = max(0, int(invested or 0))
    level = 1
    for candidate, threshold in enumerate(definition["level_thresholds"], start=1):
        if total >= threshold:
            level = candidate
    return level


def normalize_company_state(company_id: str, state) -> dict:
    if not isinstance(state, dict):
        state = default_company_state()

    try:
        invested = max(0, int(state.get("invested", 0) or 0))
    except (TypeError, ValueError):
        invested = 0

    raw_investors = state.get("investors", {})
    investors = {}
    if isinstance(raw_investors, dict):
        for user_id, amount in raw_investors.items():
            try:
                normalized_amount = max(0, int(amount or 0))
            except (TypeError, ValueError):
                normalized_amount = 0
            if normalized_amount:
                investors[str(user_id)] = normalized_amount

    # The aggregate is authoritative. It may include investments made before
    # the personal leaderboard existed, so it is not rebuilt from investors.
    state["invested"] = invested
    state["investors"] = investors
    state["level"] = level_for_investment(company_id, invested)
    return state


def normalize_companies(data) -> dict:
    if not isinstance(data, dict):
        data = {}
    for company_id in COMPANY_DEFINITIONS:
        data[company_id] = normalize_company_state(company_id, data.get(company_id))
    return data


def get_company_state(guild_data: dict, company_id: str = WHEELER_RAWSON) -> dict:
    companies = normalize_companies(guild_data.get("companies"))
    guild_data["companies"] = companies
    return companies[company_id]


def add_investment(state: dict, company_id: str, user_id, amount: int) -> tuple[int, int]:
    """Apply an investment and return ``(old_level, new_level)``."""
    if amount <= 0:
        raise ValueError("Investment must be positive")
    state = normalize_company_state(company_id, state)
    old_level = state["level"]
    state["invested"] += int(amount)
    user_key = str(user_id)
    state["investors"][user_key] = state["investors"].get(user_key, 0) + int(amount)
    state["level"] = level_for_investment(company_id, state["invested"])
    return old_level, state["level"]


def personal_investment(state: dict, user_id) -> int:
    return int(state.get("investors", {}).get(str(user_id), 0) or 0)


def investor_discount_percent(state: dict, user_id) -> int:
    invested = personal_investment(state, user_id)
    for threshold, percent in INVESTOR_DISCOUNT_TIERS:
        if invested >= threshold:
            return percent
    return 0


def combined_discount_percent(item_discount, investor_discount) -> int:
    try:
        item_discount = max(0, int(item_discount or 0))
    except (TypeError, ValueError):
        item_discount = 0
    try:
        investor_discount = max(0, int(investor_discount or 0))
    except (TypeError, ValueError):
        investor_discount = 0
    return min(MAX_CATALOG_DISCOUNT, item_discount + investor_discount)


def next_level_threshold(company_id: str, level: int) -> int | None:
    thresholds = COMPANY_DEFINITIONS[company_id]["level_thresholds"]
    if level >= len(thresholds):
        return None
    return thresholds[level]


def progress_bar(current: int, target: int | None, width: int = 10) -> str:
    if target is None:
        return "▰" * width
    ratio = max(0.0, min(1.0, current / target)) if target else 1.0
    filled = int(ratio * width)
    return "▰" * filled + "▱" * (width - filled)
