"""Pure builders for the website economy overview."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from src.company_logic import (
    COMPANY_DEFINITIONS,
    WHEELER_RAWSON,
    get_company_state,
    investor_discount_percent,
    next_level_threshold,
    personal_investment,
)


def _money(value) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def build_economy_stats(
    guild_data: dict,
    *,
    viewer_id=None,
    name_resolver: Callable[[str, Mapping], str] | None = None,
    level_resolver: Callable[[str], int] | None = None,
) -> dict:
    """Build leaderboard, gang and company data from the live economy store."""
    users = guild_data.get("users", {})
    if not isinstance(users, dict):
        users = {}
    gangs = guild_data.get("gangs", {})
    if not isinstance(gangs, dict):
        gangs = {}
    gold_rate = _money(guild_data.get("gold_rate", 543.45)) or 543.45

    user_list = []
    total_cash = 0.0
    total_gold = 0.0
    for raw_user_id, raw_account in users.items():
        user_id = str(raw_user_id)
        account = raw_account if isinstance(raw_account, dict) else {}
        cash = _money(account.get("cash"))
        safe_cash = _money(account.get("safe_cash"))
        gold = _money(account.get("gold"))
        safe_gold = _money(account.get("safe_gold"))
        total_user_cash = cash + safe_cash
        total_user_gold = gold + safe_gold
        wealth = total_user_cash + total_user_gold * gold_rate
        total_cash += total_user_cash
        total_gold += total_user_gold

        name = name_resolver(user_id, account) if name_resolver else ""
        if not name:
            name = str(account.get("name") or f"Игрок {user_id[-6:]}")
        try:
            level = max(1, int(level_resolver(user_id))) if level_resolver else 1
        except (TypeError, ValueError):
            level = 1

        user_list.append({
            "id": user_id,
            "name": name,
            "cash": cash,
            "safe_cash": safe_cash,
            "gold": gold,
            "safe_gold": safe_gold,
            "total_cash": total_user_cash,
            "total_gold": total_user_gold,
            "wealth": wealth,
            "level": level,
        })

    user_list.sort(key=lambda entry: (-entry["wealth"], entry["name"].casefold()))
    players_total_cash = total_cash
    players_total_gold = total_gold

    gang_list = []
    for gang_name, raw_gang in gangs.items():
        gang = raw_gang if isinstance(raw_gang, dict) else {}
        cash = _money(gang.get("cash"))
        gold = _money(gang.get("gold"))
        wealth = cash + gold * gold_rate
        total_cash += cash
        total_gold += gold
        gang_list.append({
            "name": str(gang_name),
            "id": gang.get("id", 0),
            "members_count": len(gang.get("members", [])),
            "cash": cash,
            "gold": gold,
            "wealth": wealth,
            "influence": gang.get("influence", 0),
        })
    gang_list.sort(key=lambda entry: entry["wealth"], reverse=True)

    company_id = WHEELER_RAWSON
    company = get_company_state(guild_data, company_id)
    next_threshold = next_level_threshold(company_id, company["level"])
    investor_list = []
    for investor_id, amount in company["investors"].items():
        account = users.get(str(investor_id), {})
        if not isinstance(account, dict):
            account = {}
        name = name_resolver(str(investor_id), account) if name_resolver else ""
        investor_list.append({
            "id": str(investor_id),
            "name": name or str(account.get("name") or f"Игрок {str(investor_id)[-6:]}"),
            "amount": int(amount),
        })
    investor_list.sort(key=lambda entry: (-entry["amount"], entry["name"].casefold()))

    return {
        "leaderboard": user_list[:10],
        "gangs": gang_list,
        "company": {
            "id": company_id,
            "name": COMPANY_DEFINITIONS[company_id]["name"],
            "level": company["level"],
            "max_level": len(COMPANY_DEFINITIONS[company_id]["level_thresholds"]),
            "invested": company["invested"],
            "next_threshold": next_threshold,
            "remaining": max(0, next_threshold - company["invested"]) if next_threshold else 0,
            "investors": investor_list[:10],
            "viewer_invested": personal_investment(company, viewer_id),
            "viewer_discount": investor_discount_percent(company, viewer_id),
        },
        "globals": {
            "total_users": len(users),
            "total_gangs": len(gangs),
            "total_cash": total_cash,
            "total_gold": total_gold,
            "players_total_cash": players_total_cash,
            "players_total_gold": players_total_gold,
            "gold_rate": gold_rate,
        },
    }
