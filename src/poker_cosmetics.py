"""Catalog and persistent account state for poker avatar decorations."""

from __future__ import annotations

from dataclasses import dataclass


COSMETIC_CANVAS_SIZE = 128
COSMETIC_AVATAR_SIZE = 88
COSMETIC_AVATAR_INSET = (COSMETIC_CANVAS_SIZE - COSMETIC_AVATAR_SIZE) // 2
POKER_COSMETICS_ACCOUNT_KEY = "poker_cosmetics"


@dataclass(frozen=True)
class PokerCosmetic:
    key: str
    name: str
    description: str
    price: float
    emoji: str


POKER_COSMETICS = {
    "none": PokerCosmetic(
        "none",
        "Без украшения",
        "Обычная круглая аватарка.",
        0,
        "⭕",
    ),
}


def cosmetic_asset_filename(key: str, *, active: bool) -> str:
    variant = "active" if active else "normal"
    return f"{key}_{variant}.png"


def normalize_poker_cosmetics(
    account: dict,
    valid_keys: set[str] | None = None,
) -> dict:
    valid_keys = set(valid_keys or POKER_COSMETICS)
    valid_keys.add("none")
    raw = account.get(POKER_COSMETICS_ACCOUNT_KEY)
    state = raw if isinstance(raw, dict) else {}
    owned_raw = state.get("owned", [])
    owned = (
        [str(key) for key in owned_raw if str(key) in valid_keys]
        if isinstance(owned_raw, list)
        else []
    )
    owned = list(dict.fromkeys(["none", *owned]))
    equipped = str(state.get("equipped", "none"))
    if equipped not in owned or equipped not in valid_keys:
        equipped = "none"
    normalized = {"owned": owned, "equipped": equipped}
    account[POKER_COSMETICS_ACCOUNT_KEY] = normalized
    return normalized
