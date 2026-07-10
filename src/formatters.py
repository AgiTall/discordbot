"""
src/formatters.py
Все функции форматирования чисел, валют, прогрессбаров и т.д.,
а также геттеры emoji из economy_data.
"""

import math

from emoji_config import (
    DEFAULT_CASH_EMOJI, DEFAULT_GOLD_EMOJI, DEFAULT_MAP_EMOJI,
    DEFAULT_STATS_EMOJI, DEFAULT_SAFE_EMOJI, DEFAULT_LOCK_EMOJI,
    DEFAULT_BALANCE_FINANCE_EMOJI, DEFAULT_BALANCE_ROLES_EMOJI,
    DEFAULT_BALANCE_ECONOMY_EMOJI, DEFAULT_BALANCE_GANG_EMOJI,
)
from src.constants import DEFAULT_CUSTOM_MESSAGES
from src.xp_utils import format_integer   # уже есть в проекте


# ──────────────────────────────────────────────────────────────
#  EMOJI-ГЕТТЕРЫ
# ──────────────────────────────────────────────────────────────

def _economy():
    """Ленивый доступ к economy_data, чтобы избежать циклических импортов."""
    from src import state
    return state.economy_data


def get_cash_emoji() -> str:
    emoji = _economy().get("cash_emoji")
    return str(emoji) if emoji else DEFAULT_CASH_EMOJI


def get_gold_emoji() -> str:
    emoji = _economy().get("gold_emoji")
    return str(emoji) if emoji else DEFAULT_GOLD_EMOJI


def get_map_emoji() -> str:
    emoji = _economy().get("map_emoji")
    return str(emoji) if emoji else str(DEFAULT_MAP_EMOJI)


def get_stats_emoji() -> str:
    emoji = _economy().get("stats_emoji")
    return str(emoji) if emoji else str(DEFAULT_STATS_EMOJI)


def get_safe_emoji() -> str:
    emoji = _economy().get("safe_emoji")
    return str(emoji) if emoji else str(DEFAULT_SAFE_EMOJI)


def get_lock_emoji() -> str:
    emoji = _economy().get("lock_emoji")
    return str(emoji) if emoji else str(DEFAULT_LOCK_EMOJI)


def get_custom_message(message_key: str) -> str:
    messages = _economy().get("custom_messages", {})
    msg = messages.get(message_key)
    if not msg:
        return DEFAULT_CUSTOM_MESSAGES[message_key]
    return msg


# ──────────────────────────────────────────────────────────────
#  ЧИСЛА / ДЕНЬГИ / ЗОЛОТО
# ──────────────────────────────────────────────────────────────

def format_number(value, decimals: int = 2) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",")


def format_money(value) -> str:
    return f"{format_number(value)} {get_cash_emoji()}"


def format_money_plain(value) -> str:
    return f"{format_number(value)}"


def format_gold(value) -> str:
    return f"{format_number(value)} {get_gold_emoji()}"


def format_gold_plain(value) -> str:
    return f"{format_number(value)}"


def format_exchange_rate(value) -> str:
    return f"{format_number(value)} {get_cash_emoji()}"


def format_treasure_maps(value) -> str:
    return f"{format_integer(value)} {get_map_emoji()} карт сокровищ"


def format_treasure_maps_plain(value) -> str:
    return f"{format_integer(value)} карт сокровищ"


def format_gold_price_value(value) -> str:
    value = float(value)
    if value.is_integer():
        return format_integer(value)
    return format_number(value, 2)


def format_role_price(value) -> str:
    return f"{format_gold_price_value(value)} {get_gold_emoji()}"


def format_percent(value) -> str:
    return f"{format_number(value, 1)}%"


def format_progress_bar(value, width: int = 10) -> str:
    percent = max(0.0, min(100.0, float(value)))
    filled  = round(width * percent / 100)
    return "█" * filled + "░" * (width - filled)


def format_progress_percent(value) -> str:
    return f"{format_progress_bar(value)} {format_percent(value)}"


def format_minutes(seconds) -> str:
    return f"{max(1, int(seconds // 60))} мин"


def format_duration(seconds) -> str:
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    parts = []
    if days:    parts.append(f"{days} д")
    if hours:   parts.append(f"{hours} ч")
    if minutes: parts.append(f"{minutes} мин")
    if seconds or not parts:
        parts.append(f"{seconds} сек")
    return " ".join(parts[:2])


# ──────────────────────────────────────────────────────────────
#  АККАУНТ / ПРОФИЛЬ
# ──────────────────────────────────────────────────────────────

def format_collection_showcase(account: dict) -> str:
    items = account.get("collection_showcase", [])
    if not items:
        return "пока пусто"
    return ", ".join(str(item) for item in items[:10])


def format_account(account: dict) -> str:
    from src.moonshiner_logic import format_moonshine_short
    return (
        f"Деньги: **{format_money(account['cash'])}**\n"
        f"Золото: **{format_gold(account['gold'])}**\n"
        f"Карты: **{format_treasure_maps(account['treasure_maps'])}**\n"
        f"Повозка торговца: **{format_percent(account['dealer_wagon'])}**\n"
        f"Самогонщик: **{format_moonshine_short(account)}**\n"
        f"Витрина коллекционных предметов: **{format_collection_showcase(account)}**"
    )


def fit_embed_description(lines, limit: int = 3900) -> str:
    description  = ""
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


def format_recipe_ingredients(recipe: dict) -> str:
    return ", ".join(
        f"{amount}x {ingredient}"
        for ingredient, amount in recipe["ingredients"].items()
    )


# ──────────────────────────────────────────────────────────────
#  РОЛИ В БАЛАНСЕ
# ──────────────────────────────────────────────────────────────

def format_balance_role_sections(guild, member, account: dict):
    """Возвращает (owned_text, unavailable_text) для embed /balance."""
    from src.role_utils import (
        find_guild_role, has_game_role, get_role_icon, ROLE_DEFINITIONS,
        DEALER_ROLE_KEY, MOONSHINER_ROLE_KEY, BOUNTY_ROLE_KEY, NATURALIST_ROLE_KEY,
    )
    from src.moonshiner_logic import format_moonshine_short
    from src.bounty_logic import format_bounty_short
    from src.naturalist_logic import format_naturalist_short

    owned_rows           = []
    unavailable_sections = []

    for role_definition in ROLE_DEFINITIONS:
        role       = find_guild_role(guild, role_definition)
        owns_role  = has_game_role(member, role_definition["key"], account)

        if owns_role:
            icon = get_role_icon(role_definition, role)
            name = role_definition["name"]
            if role_definition["key"] == DEALER_ROLE_KEY:
                wagon = account["dealer_wagon"]
                row   = f"{icon} {name}: {format_progress_percent(wagon)}"
            elif role_definition["key"] == MOONSHINER_ROLE_KEY:
                from src.moonshiner_logic import get_moonshine_account
                moonshine = get_moonshine_account(account)
                bottles   = moonshine.get("bottles", 0)
                row       = f"{icon} {name}: {format_moonshine_short(account)}, {bottles}/20 бутылок"
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
            f"{'└─' if i == len(owned_rows) - 1 else '├─'} {row}"
            for i, row in enumerate(owned_rows)
        ]
    else:
        owned_sections = ["└─ Нет активной профессии"]

    if not unavailable_sections:
        unavailable_sections.append("• Нет")

    return "\n".join(owned_sections), "\n".join(unavailable_sections)
