import unittest
from datetime import datetime, timedelta, timezone

import src.moonshiner_logic as moonshine


class MoonshinerStateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
        moonshine.now_local = lambda: self.now
        moonshine.parse_local_datetime = self._parse_datetime

    def _parse_datetime(self, value):
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def test_normalization_repairs_legacy_batch_fields(self):
        data = moonshine.normalize_moonshine_data(
            {
                "ingredients": {" яблоко ": "2"},
                "batch": {
                    "type": "unknown",
                    "name": None,
                    "stars": "9",
                    "duration_seconds": "1800",
                    "payout": "82.5",
                    "cost": "50",
                    "started_at": None,
                    "ready_at": "broken",
                },
            }
        )

        self.assertEqual(data["ingredients"]["Яблоко"], 2)
        self.assertEqual(data["batch"]["type"], "mash")
        self.assertEqual(data["batch"]["stars"], 3)
        self.assertEqual(data["batch"]["name"], "Самогон")
        self.assertIsInstance(datetime.fromisoformat(data["batch"]["ready_at"]), datetime)

    def test_irrecoverable_batch_is_reset_without_losing_inventory(self):
        data = moonshine.normalize_moonshine_data(
            {
                "ingredients": {"Мята": 3},
                "batch": {"duration_seconds": "not-a-number"},
            }
        )

        self.assertIsNone(data["batch"])
        self.assertEqual(data["ingredients"], {"Мята": 3})

    def test_bottle_progress_uses_live_batch_time(self):
        data = moonshine.default_moonshine_data()
        data["batch"] = {
            "ready_at": (self.now + timedelta(seconds=50)).isoformat(),
            "duration_seconds": 100,
        }

        self.assertEqual(moonshine.get_moonshine_bottles(data), 10)
        formatted = moonshine.format_moonshine_bottles(data)
        self.assertIn("50.0%", formatted)
        self.assertIn("10/20", formatted)

    def test_special_recipe_consumes_exact_ingredients(self):
        recipe = moonshine.get_moonshine_special_recipe("wild_cider")
        data = moonshine.default_moonshine_data()
        data["ingredients"] = {
            "Яблоко": 2,
            "Женьшень": 1,
            "Смородина": 1,
        }

        self.assertTrue(moonshine.has_moonshine_ingredients(data, recipe))
        moonshine.consume_moonshine_ingredients(data, recipe)
        self.assertEqual(data["ingredients"], {"Яблоко": 1})


if __name__ == "__main__":
    unittest.main()
