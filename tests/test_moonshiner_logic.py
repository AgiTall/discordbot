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

    def test_store_purchase_goes_to_moonshine_ingredient_storage(self):
        account = {"moonshine": moonshine.default_moonshine_data()}
        stored = moonshine.add_moonshine_ingredient(account, "Яблоко", 1)
        self.assertEqual(stored, 1)
        self.assertEqual(account["moonshine"]["ingredients"]["Яблоко"], 1)

        stored = moonshine.add_moonshine_ingredient(account, " яблоко ", 2)
        self.assertEqual(stored, 3)

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

    def test_reference_recipe_payouts_are_preserved(self):
        expected = {
            "berry_mint": 206.25,
            "wild_cider": 206.25,
            "berry_apple": 226.87,
            "evergreen": 226.87,
            "tropical_punch": 226.87,
            "berry_cobbler": 226.87,
            "mahogany_sunrise": 247.50,
            "wild_creek": 247.50,
            "spiced_island": 247.50,
            "poison_poppy": 247.50,
        }

        self.assertEqual(
            {
                recipe["key"]: recipe["payout"]
                for recipe in moonshine.MOONSHINE_SPECIAL_RECIPES
            },
            expected,
        )

    def test_legacy_mahonia_inventory_migrates_to_magnolia(self):
        data = moonshine.normalize_moonshine_data(
            {"ingredients": {"Магония": 2, "Магнолия": 1}}
        )

        self.assertEqual(data["ingredients"], {"Магнолия": 3})
        recipe = moonshine.get_moonshine_special_recipe("mahogany_sunrise")
        self.assertIn("Магнолия", recipe["ingredients"])
        self.assertEqual(recipe["name"], "Рассвет среди магнолий")

    def test_level_15_skill_uses_reference_brewing_times(self):
        expected_minutes = {"weak": 24, "medium": 36, "strong": 48}
        for recipe in moonshine.MOONSHINE_MASH_RECIPES:
            with self.subTest(recipe=recipe["key"]):
                self.assertEqual(
                    moonshine.get_moonshine_duration_seconds(recipe, skill=True),
                    expected_minutes[recipe["strength_key"]] * 60,
                )


if __name__ == "__main__":
    unittest.main()
