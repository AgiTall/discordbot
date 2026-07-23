"""Normalization helpers for the daily gold-rate chart."""

from __future__ import annotations

import math
from datetime import date
from typing import Any


MAX_GOLD_RATE_HISTORY_POINTS = 365


def _valid_date(value: Any) -> str | None:
    raw = str(value or "").strip()
    try:
        return date.fromisoformat(raw).isoformat()
    except (TypeError, ValueError):
        return None


def _valid_rate(value: Any) -> float | None:
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(rate) or rate <= 0:
        return None
    return round(rate, 2)


def normalize_gold_rate_history(
    value: Any,
    *,
    fallback_date: Any,
    fallback_rate: Any,
) -> list[dict[str, Any]]:
    """Return sorted, unique and bounded daily rate points."""
    by_date: dict[str, float] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            point_date = _valid_date(item.get("date"))
            point_rate = _valid_rate(item.get("rate"))
            if point_date and point_rate is not None:
                by_date[point_date] = point_rate

    if not by_date:
        point_date = _valid_date(fallback_date)
        point_rate = _valid_rate(fallback_rate)
        if point_date and point_rate is not None:
            by_date[point_date] = point_rate

    return [
        {"date": point_date, "rate": by_date[point_date]}
        for point_date in sorted(by_date)[-MAX_GOLD_RATE_HISTORY_POINTS:]
    ]


def record_gold_rate(
    value: Any,
    *,
    point_date: Any,
    rate: Any,
) -> list[dict[str, Any]]:
    """Add or replace the rate for one calendar day."""
    history = normalize_gold_rate_history(
        value,
        fallback_date=point_date,
        fallback_rate=rate,
    )
    valid_date = _valid_date(point_date)
    valid_rate = _valid_rate(rate)
    if valid_date is None or valid_rate is None:
        return history

    by_date = {item["date"]: item["rate"] for item in history}
    by_date[valid_date] = valid_rate
    return [
        {"date": item_date, "rate": by_date[item_date]}
        for item_date in sorted(by_date)[-MAX_GOLD_RATE_HISTORY_POINTS:]
    ]
