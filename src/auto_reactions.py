"""Normalization and matching helpers for configurable message reactions."""

from __future__ import annotations

import re
from typing import Any, Iterable


MAX_AUTO_REACTION_RULES = 20
MAX_REACTIONS_PER_RULE = 10
MAX_REACTIONS_PER_MESSAGE = 10
MAX_MATCHES_PER_RULE = 50
MAX_TRIGGER_LENGTH = 100
MAX_REACTION_EMOJI_LENGTH = 80
MESSAGE_TYPES = {"all", "default", "reply"}


def _normalize_terms(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for raw in value[:MAX_MATCHES_PER_RULE]:
        term = " ".join(str(raw).split())
        folded = term.casefold()
        if not term or len(term) > MAX_TRIGGER_LENGTH or folded in seen:
            continue
        seen.add(folded)
        terms.append(term)
    return terms


def _normalize_emojis(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    emojis: list[str] = []
    for raw in value[:MAX_REACTIONS_PER_RULE]:
        emoji = str(raw).strip()
        if emoji and len(emoji) <= MAX_REACTION_EMOJI_LENGTH and emoji not in emojis:
            emojis.append(emoji)
    return emojis


def normalize_auto_reactions(value: Any) -> list[dict[str, Any]]:
    """Normalize current rules and transparently migrate legacy trigger/emoji pairs."""
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in value[:MAX_AUTO_REACTION_RULES]:
        if not isinstance(item, dict):
            continue

        # v0.8.1.10 stored one trigger and one emoji per rule.
        triggers = _normalize_terms(item.get("triggers", item.get("trigger", [])))
        excluded = _normalize_terms(
            item.get("excluded_triggers", item.get("excludedTriggers", []))
        )
        emojis = _normalize_emojis(item.get("emojis", item.get("emoji", [])))
        if not emojis:
            continue

        channel_id = str(item.get("channel_id", item.get("channelId", "")) or "").strip()
        if channel_id and not channel_id.isdigit():
            channel_id = ""
        message_type = str(
            item.get("message_type", item.get("messageType", "all")) or "all"
        ).strip().lower()
        if message_type not in MESSAGE_TYPES:
            message_type = "all"

        identity = (
            channel_id,
            message_type,
            tuple(term.casefold() for term in triggers),
            tuple(term.casefold() for term in excluded),
            tuple(emojis),
        )
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(
            {
                "channel_id": channel_id,
                "emojis": emojis,
                "message_type": message_type,
                "triggers": triggers,
                "excluded_triggers": excluded,
            }
        )
    return normalized


def auto_reactions_for_dashboard(value: Any) -> list[dict[str, Any]]:
    """Convert stored snake_case rules to the dashboard's camelCase payload."""
    return [
        {
            "channelId": rule["channel_id"],
            "emojis": list(rule["emojis"]),
            "messageType": rule["message_type"],
            "triggers": list(rule["triggers"]),
            "excludedTriggers": list(rule["excluded_triggers"]),
        }
        for rule in normalize_auto_reactions(value)
    ]


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
    rules: Iterable[dict[str, Any]],
    *,
    channel_id: int | str | None = None,
    message_type: str = "default",
    limit: int = MAX_REACTIONS_PER_MESSAGE,
) -> list[str]:
    """Return distinct emojis for every rule that matches the message context."""
    matched: list[str] = []
    current_channel = str(channel_id or "")
    current_type = str(message_type or "default").lower()

    for rule in normalize_auto_reactions(list(rules)):
        if rule["channel_id"] and rule["channel_id"] != current_channel:
            continue
        if rule["message_type"] != "all" and rule["message_type"] != current_type:
            continue
        if rule["excluded_triggers"] and any(
            message_matches_trigger(content, term) for term in rule["excluded_triggers"]
        ):
            continue
        if rule["triggers"] and not any(
            message_matches_trigger(content, term) for term in rule["triggers"]
        ):
            continue

        for emoji in rule["emojis"]:
            if emoji not in matched:
                matched.append(emoji)
                if len(matched) >= limit:
                    return matched
    return matched
