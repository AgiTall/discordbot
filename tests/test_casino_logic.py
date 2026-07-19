import unittest

from cogs.casino import should_announce_blackjack_win


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


if __name__ == "__main__":
    unittest.main()
