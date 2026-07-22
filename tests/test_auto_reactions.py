import unittest

from src.auto_reactions import (
    matching_reaction_emojis,
    message_matches_trigger,
    normalize_auto_reactions,
)


class AutoReactionTests(unittest.TestCase):
    def test_matches_whole_words_and_phrases_without_case(self):
        self.assertTrue(message_matches_trigger("Это ПОБЕДА!", "победа"))
        self.assertTrue(message_matches_trigger("Дикий   Запад зовёт", "дикий запад"))
        self.assertFalse(message_matches_trigger("победитель найден", "победа"))

    def test_normalization_drops_invalid_and_duplicate_rules(self):
        rules = normalize_auto_reactions(
            [
                {"trigger": "  Дикий   Запад ", "emoji": " 🤠 "},
                {"trigger": "дикий запад", "emoji": "🤠"},
                {"trigger": "", "emoji": "👍"},
                "invalid",
            ]
        )
        self.assertEqual(rules, [{"trigger": "Дикий Запад", "emoji": "🤠"}])

    def test_matching_emojis_are_distinct_and_limited(self):
        rules = [
            {"trigger": "ура", "emoji": "🎉"},
            {"trigger": "победа", "emoji": "🎉"},
            {"trigger": "победа", "emoji": "🏆"},
        ]
        self.assertEqual(
            matching_reaction_emojis("Ура, победа!", rules),
            ["🎉", "🏆"],
        )


if __name__ == "__main__":
    unittest.main()
