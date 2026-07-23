import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from src.gold_rate_history import (
    MAX_GOLD_RATE_HISTORY_POINTS,
    normalize_gold_rate_history,
    record_gold_rate,
)
from src.economy_store import update_gold_rate
from src import state


class GoldRateHistoryTests(unittest.TestCase):
    def test_normalization_sorts_dates_and_keeps_last_rate_for_day(self):
        history = normalize_gold_rate_history(
            [
                {"date": "2026-07-22", "rate": 500},
                {"date": "invalid", "rate": 999},
                {"date": "2026-07-21", "rate": 490.123},
                {"date": "2026-07-22", "rate": 505.5},
                {"date": "2026-07-23", "rate": float("nan")},
            ],
            fallback_date="2026-07-20",
            fallback_rate=480,
        )

        self.assertEqual(
            history,
            [
                {"date": "2026-07-21", "rate": 490.12},
                {"date": "2026-07-22", "rate": 505.5},
            ],
        )

    def test_record_replaces_same_day_and_limits_history(self):
        source = [
            {
                "date": (date(2025, 1, 1) + timedelta(days=offset)).isoformat(),
                "rate": 500 + offset,
            }
            for offset in range(400)
        ]
        result = record_gold_rate(
            source,
            point_date=(date(2025, 1, 1) + timedelta(days=399)).isoformat(),
            rate=777.77,
        )

        self.assertEqual(len(result), MAX_GOLD_RATE_HISTORY_POINTS)
        self.assertEqual(result[-1]["rate"], 777.77)

    def test_legacy_server_gets_current_rate_as_first_point(self):
        self.assertEqual(
            normalize_gold_rate_history(
                None,
                fallback_date="2026-07-23",
                fallback_rate=543.45,
            ),
            [{"date": "2026-07-23", "rate": 543.45}],
        )

    def test_daily_update_records_every_missed_date(self):
        original_economy_data = state.economy_data
        state.economy_data = {
            "gold_rate": 500,
            "gold_rate_date": "2026-07-20",
            "gold_rate_history": [{"date": "2026-07-20", "rate": 500}],
        }
        try:
            with patch(
                "src.economy_store.now_local",
                return_value=datetime(2026, 7, 23, 12, tzinfo=timezone.utc),
            ):
                update_gold_rate()
        finally:
            history = list(state.economy_data["gold_rate_history"])
            state.economy_data = original_economy_data

        self.assertEqual(
            [point["date"] for point in history],
            ["2026-07-20", "2026-07-21", "2026-07-22", "2026-07-23"],
        )


if __name__ == "__main__":
    unittest.main()
