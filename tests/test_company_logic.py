import unittest

from src.company_logic import (
    WHEELER_RAWSON,
    add_investment,
    combined_discount_percent,
    default_company_state,
    get_company_state,
    investor_discount_percent,
    level_for_investment,
    next_level_threshold,
    normalize_company_state,
)


class CompanyLogicTests(unittest.TestCase):
    def test_levels_use_cumulative_thresholds(self):
        self.assertEqual(level_for_investment(WHEELER_RAWSON, 0), 1)
        self.assertEqual(level_for_investment(WHEELER_RAWSON, 1_499), 1)
        self.assertEqual(level_for_investment(WHEELER_RAWSON, 1_500), 2)
        self.assertEqual(level_for_investment(WHEELER_RAWSON, 5_000), 3)
        self.assertEqual(level_for_investment(WHEELER_RAWSON, 12_000), 4)

    def test_one_large_investment_can_unlock_multiple_levels(self):
        state = default_company_state()
        old_level, new_level = add_investment(
            state, WHEELER_RAWSON, user_id=42, amount=5_000
        )
        self.assertEqual((old_level, new_level), (1, 3))
        self.assertEqual(state["invested"], 5_000)
        self.assertEqual(state["investors"]["42"], 5_000)

    def test_personal_discount_tiers_and_global_cap(self):
        state = default_company_state()
        for total, expected in ((99, 0), (100, 2), (500, 4), (1_500, 6), (5_000, 8)):
            state["investors"]["7"] = total
            self.assertEqual(investor_discount_percent(state, 7), expected)
        self.assertEqual(combined_discount_percent(20, 8), 25)

    def test_normalization_repairs_legacy_values(self):
        state = normalize_company_state(
            WHEELER_RAWSON,
            {"level": 99, "invested": "5000", "investors": {42: "500", "bad": "x"}},
        )
        self.assertEqual(state["level"], 3)
        self.assertEqual(state["invested"], 5_000)
        self.assertEqual(state["investors"], {"42": 500})

    def test_guild_state_is_created_lazily(self):
        guild_data = {}
        state = get_company_state(guild_data)
        self.assertEqual(state["level"], 1)
        self.assertIn("companies", guild_data)
        self.assertEqual(next_level_threshold(WHEELER_RAWSON, 1), 1_500)
        self.assertIsNone(next_level_threshold(WHEELER_RAWSON, 4))


if __name__ == "__main__":
    unittest.main()
