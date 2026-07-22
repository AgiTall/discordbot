"""Normalization and matching helpers for configurable message reactions."""

from __future__ import annotations

import re
from typing import Any, Iterable


MAX_AUTO_REACTION_RULES = 20
MAX_REACTIONS_PER_MESSAGE = 5
MAX_TRIGGER_LENGTH = 100
MAX_REACTION_EMOJI_LENGTH = 80


def normalize_auto_reactions(value: Any) -> list[dict[str, str]]:
    """Return a bounded, copy-safe list of valid trigger/emoji rules."""
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in value[:MAX_AUTO_REACTION_RULES]:
        if not isinstance(item, dict):
            continue
        trigger = " ".join(str(item.get("trigger", "")).split())
        emoji = str(item.get("emoji", "")).strip()
        if not trigger or not emoji:
            continue
        if len(trigger) > MAX_TRIGGER_LENGTH or len(emoji) > MAX_REACTION_EMOJI_LENGTH:
            continue
        identity = (trigger.casefold(), emoji)
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append({"trigger": trigger, "emoji": emoji})
    return normalized


def message_matches_trigger(content: str, trigger: str) -> bool:
    """Match a whole word or phrase, case-insensitively and with flexible spaces."""
    normalized_trigger = " ".join(str(trigger or "").split())
    if not content or not normalized_trigger:
        return False

    parts = normalized_trigger.casefold().split(" ")
    expression = r"\s+".join(re.escape(part) for part in parts)
    if normalized_trigger[0].isalnum() or normalized_trigger[0] == "_":
        expression = rf"(?<!\w){expression}"
    if normalized_trigger[-1].isalnum() or normalized_trigger[-1] == "_":
        expression = rf"{expression}(?!\w)"
    return re.search(expression, content.casefold()) is not None


def matching_reaction_emojis(
    content: str,
    rules: Iterable[dict[str, str]],
    *,
    limit: int = MAX_REACTIONS_PER_MESSAGE,
) -> list[str]:
    """Return distinct configured emojis matching a message, in rule order."""
    matched: list[str] = []
    for rule in normalize_auto_reactions(list(rules)):
        emoji = rule["emoji"]
        if emoji not in matched and message_matches_trigger(content, rule["trigger"]):
            matched.append(emoji)
            if len(matched) >= limit:
                break
    return matched
