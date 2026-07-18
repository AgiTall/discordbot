import unittest

from src.bounty_logic import (
    BOUNTY_MAX_LEVEL,
    DEFAULT_BOUNTY_BUTTON_EMOJIS,
    normalize_bounty_data,
)


class BountyLogicTests(unittest.TestCase):
    def test_invalid_progress_is_normalized(self):
        bounty = normalize_bounty_data(
            {"level": 999, "xp": "bad", "captures": -4, "escaped": "3"}
        )
        self.assertEqual(bounty["level"], BOUNTY_MAX_LEVEL)
        self.assertEqual(bounty["xp"], 0)
        self.assertEqual(bounty["captures"], 0)
        self.assertEqual(bounty["escaped"], 3)

    def test_all_bounty_menu_icons_are_custom(self):
        self.assertEqual(
            set(DEFAULT_BOUNTY_BUTTON_EMOJIS),
            {"easy", "medium", "hard", "ambush", "chase", "negotiate", "leaderboard"},
        )
        for emoji in DEFAULT_BOUNTY_BUTTON_EMOJIS.values():
            self.assertTrue(emoji.startswith("<:"), emoji)


if __name__ == "__main__":
    unittest.main()
