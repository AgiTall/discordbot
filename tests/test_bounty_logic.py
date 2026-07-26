import random
import unittest

from src.bounty_logic import (
    BOUNTY_BASE_MAX_LEVEL,
    BOUNTY_MAX_LEVEL,
    BOUNTY_TARGETS,
    BOUNTY_WAGON_PRICE,
    DEFAULT_BOUNTY_BUTTON_EMOJIS,
    LEGENDARY_BOUNTIES,
    PRESTIGIOUS_LICENSE_PRICE,
    bounty_level_cap,
    normalize_bounty_data,
    roll_bounty_contract,
    simple_bounty_target_key,
)


class BountyLogicTests(unittest.TestCase):
    def test_invalid_progress_is_normalized(self):
        bounty = normalize_bounty_data(
            {"level": 999, "xp": "bad", "captures": -4, "escaped": "3"}
        )
        self.assertEqual(bounty["level"], BOUNTY_BASE_MAX_LEVEL)
        self.assertEqual(bounty["xp"], 0)
        self.assertEqual(bounty["captures"], 0)
        self.assertEqual(bounty["escaped"], 3)

    def test_all_bounty_menu_icons_are_custom(self):
        self.assertEqual(
            set(DEFAULT_BOUNTY_BUTTON_EMOJIS),
            {*BOUNTY_TARGETS, "leaderboard"},
        )
        for emoji in DEFAULT_BOUNTY_BUTTON_EMOJIS.values():
            self.assertTrue(emoji.startswith("<:"), emoji)

    def test_prestigious_license_unlocks_level_thirty(self):
        ordinary = normalize_bounty_data({"level": 30})
        prestigious = normalize_bounty_data(
            {"level": 30, "prestigious_license": True}
        )
        self.assertEqual(BOUNTY_BASE_MAX_LEVEL, bounty_level_cap(ordinary))
        self.assertEqual(BOUNTY_MAX_LEVEL, bounty_level_cap(prestigious))
        self.assertEqual(20, ordinary["level"])
        self.assertEqual(30, prestigious["level"])

    def test_reference_contract_rewards(self):
        expected = {
            "cheap": ((1, 2), 30.0, 50.0, 0.08, 450),
            "medium": ((1, 4), 37.50, 75.0, 0.08, 700),
            "expensive": ((1, 6), 45.0, 90.0, 0.08, 900),
            "legendary": ((1, 6), 100.0, 225.0, 0.24, 1000),
        }
        self.assertEqual(
            expected,
            {
                key: (
                    value["target_count"],
                    value["reward_min"],
                    value["reward_max"],
                    value["gold"],
                    value["xp"],
                )
                for key, value in BOUNTY_TARGETS.items()
            },
        )

    def test_all_reference_legendary_bounties_are_available(self):
        self.assertEqual(13, len(LEGENDARY_BOUNTIES))
        for seed in range(20):
            contract = roll_bounty_contract("legendary", random.Random(seed))
            self.assertGreaterEqual(contract["reward"], contract["reward_min"])
            self.assertLessEqual(contract["reward"], contract["reward_max"])
            self.assertGreaterEqual(contract["count"], 1)
            self.assertLessEqual(contract["count"], 6)

    def test_reference_equipment_prices(self):
        self.assertEqual(15.0, PRESTIGIOUS_LICENSE_PRICE)
        self.assertEqual(875.0, BOUNTY_WAGON_PRICE)

    def test_simple_menu_has_no_profession_level_gate(self):
        self.assertEqual("expensive", simple_bounty_target_key({"level": 1}))
        self.assertEqual("expensive", simple_bounty_target_key({"level": 10}))
        self.assertEqual(
            "legendary",
            simple_bounty_target_key(
                {"level": 1, "prestigious_license": True}
            ),
        )


if __name__ == "__main__":
    unittest.main()
