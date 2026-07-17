import unittest

from src.card_emojis import format_card_emoji


class CardEmojiTests(unittest.TestCase):
    def test_king_of_hearts_uses_uploaded_emoji(self):
        self.assertEqual(
            "<:hearts_k:1527573248663879831>",
            format_card_emoji(("K", "♥")),
        )


if __name__ == "__main__":
    unittest.main()
