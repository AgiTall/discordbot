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
                {"trigger": "", "emoji": ""},
                "invalid",
            ]
        )
        self.assertEqual(
            rules,
            [{
                "channel_id": "",
                "emojis": ["🤠"],
                "message_type": "all",
                "triggers": ["Дикий Запад"],
                "excluded_triggers": [],
            }],
        )

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

    def test_channel_message_type_and_exclusions_are_honored(self):
        rules = [{
            "channelId": "200",
            "emojis": ["🤠", "🔥"],
            "messageType": "reply",
            "triggers": ["дикий запад"],
            "excludedTriggers": ["спойлер"],
        }]
        self.assertEqual(
            matching_reaction_emojis(
                "Дикий Запад!", rules, channel_id=200, message_type="reply"
            ),
            ["🤠", "🔥"],
        )
        self.assertEqual(
            matching_reaction_emojis(
                "Дикий Запад, спойлер", rules, channel_id=200, message_type="reply"
            ),
            [],
        )
        self.assertEqual(
            matching_reaction_emojis(
                "Дикий Запад!", rules, channel_id=201, message_type="reply"
            ),
            [],
        )

    def test_rule_without_triggers_matches_attachment_only_message(self):
        rules = [{
            "channelId": "200",
            "emojis": ["👀"],
            "messageType": "default",
            "triggers": [],
            "excludedTriggers": [],
        }]
        self.assertEqual(
            matching_reaction_emojis(
                "", rules, channel_id=200, message_type="default"
            ),
            ["👀"],
        )


if __name__ == "__main__":
    unittest.main()
