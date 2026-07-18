import unittest

from src.economy_stats import build_economy_stats


class EconomyStatsTests(unittest.TestCase):
    def test_leaderboard_uses_wallet_and_safe_balances(self):
        guild_data = {
            "gold_rate": 500,
            "users": {
                "1": {"cash": 100, "safe_cash": 900, "gold": 1, "safe_gold": 1},
                "2": {"cash": 1_500, "gold": 0},
            },
        }

        stats = build_economy_stats(
            guild_data,
            name_resolver=lambda user_id, _: {"1": "Артур", "2": "Джон"}[user_id],
            level_resolver=lambda user_id: {"1": 12, "2": 7}[user_id],
        )

        self.assertEqual([entry["id"] for entry in stats["leaderboard"]], ["1", "2"])
        richest = stats["leaderboard"][0]
        self.assertEqual(richest["wealth"], 2_000)
        self.assertEqual(richest["total_cash"], 1_000)
        self.assertEqual(richest["total_gold"], 2)
        self.assertEqual(richest["level"], 12)
        self.assertEqual(stats["globals"]["players_total_cash"], 2_500)

    def test_company_payload_contains_live_progress_and_investors(self):
        guild_data = {
            "users": {"42": {"name": "Корнуолл"}},
            "companies": {
                "wheeler_rawson": {
                    "invested": 5_000,
                    "level": 1,
                    "investors": {"42": 5_000},
                }
            },
        }

        company = build_economy_stats(guild_data, viewer_id="42")["company"]

        self.assertEqual(company["level"], 3)
        self.assertEqual(company["next_threshold"], 12_000)
        self.assertEqual(company["remaining"], 7_000)
        self.assertEqual(company["viewer_invested"], 5_000)
        self.assertEqual(company["viewer_discount"], 8)
        self.assertEqual(company["investors"][0]["name"], "Корнуолл")

    def test_invalid_legacy_money_does_not_break_stats(self):
        stats = build_economy_stats({"users": {"x": {"cash": "broken", "gold": -5}}})
        self.assertEqual(stats["leaderboard"][0]["wealth"], 0)
        self.assertEqual(stats["globals"]["total_cash"], 0)


if __name__ == "__main__":
    unittest.main()
