"""Pure helpers used by the Discord administrator commands.

Keeping mutations here makes destructive admin actions predictable and easy to
test without a Discord connection.
"""

from __future__ import annotations

from src.bounty_logic import (
    BOUNTY_MAX_LEVEL,
    default_bounty_data,
    normalize_bounty_data,
)
from src.collector_logic import default_collector_data, normalize_collector_data
from src.moonshiner_logic import default_moonshine_data, normalize_moonshine_data
from src.naturalist_logic import (
    NATURALIST_MAX_LEVEL,
    default_naturalist_data,
    normalize_naturalist_data,
)


PROFESSION_NAMES = {
    "bounty": "Охотник за головами",
    "naturalist": "Натуралист",
    "collector": "Коллекционер",
}

RESETTABLE_MECHANICS = {
    "bounty": "Охотник за головами",
    "naturalist": "Натуралист",
    "collector": "Коллекционер",
    "moonshine": "Самогонщик",
    "trader": "Торговец",
    "all_professions": "Все профессии",
}


def change_quantity(
    container: dict,
    key: str,
    action: str,
    amount: int,
    *,
    cap: int | None = None,
) -> tuple[int, int]:
    """Change a non-negative integer value and return ``(old, new)``."""
    if action not in {"add", "remove", "set"}:
        raise ValueError("Неизвестное действие с количеством.")
    try:
        amount = int(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("Количество должно быть целым числом.") from exc
    if amount < 0:
        raise ValueError("Количество не может быть отрицательным.")

    try:
        old = max(0, int(container.get(key, 0) or 0))
    except (TypeError, ValueError):
        old = 0

    if action == "add":
        new = old + amount
    elif action == "remove":
        new = max(0, old - amount)
    else:
        new = amount

    if cap is not None:
        new = min(max(0, int(cap)), new)
    container[key] = new
    return old, new


def set_profession_progress(
    account: dict,
    profession: str,
    level: int,
    xp: int,
) -> dict:
    """Set level/XP for a profession that has an independent progression."""
    try:
        level = int(level)
        xp = int(xp)
    except (TypeError, ValueError) as exc:
        raise ValueError("Уровень и опыт должны быть целыми числами.") from exc
    if xp < 0:
        raise ValueError("Опыт не может быть отрицательным.")

    if profession == "bounty":
        data = normalize_bounty_data(account.get("bounty"))
        data["level"] = max(1, min(BOUNTY_MAX_LEVEL, level))
        data["xp"] = xp
        account["bounty"] = normalize_bounty_data(data)
        return account["bounty"]
    if profession == "naturalist":
        data = normalize_naturalist_data(account.get("naturalist"))
        data["level"] = max(1, min(NATURALIST_MAX_LEVEL, level))
        data["xp"] = xp
        account["naturalist"] = normalize_naturalist_data(data)
        return account["naturalist"]
    if profession == "collector":
        data = normalize_collector_data(account.get("collector"))
        data["level"] = max(1, min(20, level))
        data["xp"] = xp
        account["collector"] = normalize_collector_data(data)
        return account["collector"]
    raise ValueError("У этой профессии нет настраиваемой шкалы уровня и опыта.")


def reset_account_cooldowns(account: dict, activity: str) -> list[str]:
    """Reset one or more account-owned cooldowns and return changed labels."""
    changed: list[str] = []

    def reset_field(container: dict, key: str, label: str) -> None:
        container[key] = None
        changed.append(label)

    if activity in {"work", "all"}:
        reset_field(account, "last_work_at", "/work")
    if activity in {"trader", "all"}:
        reset_field(account, "last_dealer_at", "Торговец")
    if activity in {"bounty", "all"}:
        bounty = normalize_bounty_data(account.get("bounty"))
        account["bounty"] = bounty
        reset_field(bounty, "last_bounty_at", "Охотник")
    if activity in {"naturalist", "all"}:
        naturalist = normalize_naturalist_data(account.get("naturalist"))
        account["naturalist"] = naturalist
        reset_field(naturalist, "last_sample_at", "Натуралист: обычная охота")
    if activity in {"naturalist_legendary", "all"}:
        naturalist = normalize_naturalist_data(account.get("naturalist"))
        account["naturalist"] = naturalist
        reset_field(
            naturalist,
            "legendary_cooldown_until",
            "Натуралист: легендарная охота",
        )
    if activity in {"robbery", "all"}:
        cooldowns = account.setdefault("cooldowns", {})
        if not isinstance(cooldowns, dict):
            cooldowns = account["cooldowns"] = {}
        reset_field(cooldowns, "last_player_rob_at", "Ограбление игрока")
    if activity in {"safe", "all"}:
        cooldowns = account.setdefault("cooldowns", {})
        if not isinstance(cooldowns, dict):
            cooldowns = account["cooldowns"] = {}
        reset_field(cooldowns, "safe_withdraw_at", "Сейф")

    known = {
        "work", "trader", "bounty", "naturalist", "naturalist_legendary",
        "robbery", "safe", "all",
    }
    if activity not in known:
        raise ValueError("Неизвестная активность.")
    return changed


def reset_mechanic(account: dict, mechanic: str) -> list[str]:
    """Reset profession state while preserving currencies and purchased roles."""
    reset: list[str] = []
    requested = (
        ("bounty", "naturalist", "collector", "moonshine", "trader")
        if mechanic == "all_professions"
        else (mechanic,)
    )
    for key in requested:
        if key == "bounty":
            account["bounty"] = default_bounty_data()
            reset.append("Охотник за головами")
        elif key == "naturalist":
            account["naturalist"] = default_naturalist_data()
            reset.append("Натуралист")
        elif key == "collector":
            account["collector"] = default_collector_data()
            reset.append("Коллекционер")
        elif key == "moonshine":
            account["moonshine"] = default_moonshine_data()
            reset.append("Самогонщик")
        elif key == "trader":
            account["dealer_wagon"] = 0.0
            account["last_dealer_at"] = None
            reset.append("Торговец")
        else:
            raise ValueError("Неизвестная механика.")
    return reset
