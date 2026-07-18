import unittest

from src.admin_logic import (
    change_quantity,
    reset_account_cooldowns,
    reset_mechanic,
    set_profession_progress,
)


class AdminQuantityTests(unittest.TestCase):
    def test_quantity_actions_are_non_negative_and_honor_caps(self):
        values = {"item": 4}

        self.assertEqual(change_quantity(values, "item", "add", 3), (4, 7))
        self.assertEqual(change_quantity(values, "item", "remove", 20), (7, 0))
        self.assertEqual(
            change_quantity(values, "item", "set", 9, cap=5),
            (0, 5),
        )

    def test_quantity_rejects_invalid_admin_input(self):
        with self.assertRaises(ValueError):
            change_quantity({}, "item", "multiply", 2)
        with self.assertRaises(ValueError):
            change_quantity({}, "item", "add", -1)


class AdminProgressTests(unittest.TestCase):
    def test_profession_progress_is_clamped_to_game_limits(self):
        account = {}

        bounty = set_profession_progress(account, "bounty", 999, 450)
        naturalist = set_profession_progress(account, "naturalist", 0, 120)
        collector = set_profession_progress(account, "collector", 8, 75)

        self.assertEqual((bounty["level"], bounty["xp"]), (20, 450))
        self.assertEqual((naturalist["level"], naturalist["xp"]), (1, 120))
        self.assertEqual((collector["level"], collector["xp"]), (8, 75))

    def test_negative_xp_is_rejected(self):
        with self.assertRaises(ValueError):
            set_profession_progress({}, "collector", 2, -1)


class AdminResetTests(unittest.TestCase):
    def test_all_cooldowns_are_reset_without_touching_balances(self):
        account = {
            "cash": 500,
            "gold": 7,
            "last_work_at": "2026-01-01T00:00:00+00:00",
            "last_dealer_at": "2026-01-01T00:00:00+00:00",
            "bounty": {"last_bounty_at": "2026-01-01T00:00:00+00:00"},
            "naturalist": {
                "last_sample_at": "2026-01-01T00:00:00+00:00",
                "legendary_cooldown_until": "2026-01-02T00:00:00+00:00",
            },
            "cooldowns": {
                "last_player_rob_at": "2026-01-01T00:00:00+00:00",
                "safe_withdraw_at": "2026-01-01T00:00:00+00:00",
            },
        }

        labels = reset_account_cooldowns(account, "all")

        self.assertEqual(account["cash"], 500)
        self.assertEqual(account["gold"], 7)
        self.assertIsNone(account["last_work_at"])
        self.assertIsNone(account["last_dealer_at"])
        self.assertIsNone(account["bounty"]["last_bounty_at"])
        self.assertIsNone(account["naturalist"]["last_sample_at"])
        self.assertIsNone(account["naturalist"]["legendary_cooldown_until"])
        self.assertIsNone(account["cooldowns"]["last_player_rob_at"])
        self.assertIsNone(account["cooldowns"]["safe_withdraw_at"])
        self.assertEqual(len(labels), 7)

    def test_profession_reset_preserves_currency_roles_and_gang(self):
        account = {
            "cash": 100,
            "gold": 2,
            "owned_roles": ["bounty_hunter"],
            "gang_name": "Test",
            "bounty": {"level": 15, "xp": 999, "captures": 80},
            "dealer_wagon": 90,
        }

        reset_mechanic(account, "all_professions")

        self.assertEqual(account["cash"], 100)
        self.assertEqual(account["gold"], 2)
        self.assertEqual(account["owned_roles"], ["bounty_hunter"])
        self.assertEqual(account["gang_name"], "Test")
        self.assertEqual(account["bounty"]["level"], 1)
        self.assertEqual(account["dealer_wagon"], 0)


if __name__ == "__main__":
    unittest.main()
