import unittest

from cogs.casino import _normalize_casino_amount, should_announce_blackjack_win


class BlackjackAnnouncementTests(unittest.TestCase):
    def test_regular_win_is_not_announced(self):
        self.assertFalse(should_announce_blackjack_win(bet=1000))

    def test_blackjack_with_meaningful_bet_is_announced(self):
        self.assertTrue(should_announce_blackjack_win(bet=100, is_blackjack=True))

    def test_double_win_with_meaningful_bet_is_announced(self):
        self.assertTrue(should_announce_blackjack_win(bet=100, won_after_double=True))

    def test_small_or_zero_bets_are_not_announced(self):
        self.assertFalse(should_announce_blackjack_win(bet=99, is_blackjack=True))
        self.assertFalse(should_announce_blackjack_win(bet=0, won_after_double=True))


class CasinoBankTests(unittest.TestCase):
    def test_bank_amount_rejects_non_finite_and_negative_values(self):
        for value in (float("nan"), float("inf"), float("-inf"), -1, "bad", None):
            with self.subTest(value=value):
                self.assertEqual(_normalize_casino_amount(value), 0.0)

    def test_bank_amount_is_rounded_for_persistence(self):
        self.assertEqual(_normalize_casino_amount("12.345"), 12.35)


if __name__ == "__main__":
    unittest.main()
