import random
import unittest
from pathlib import Path

from emoji_config import (
    CASINO_BIG_BLIND_EMOJI,
    CASINO_DEALER_EMOJI,
    CASINO_SMALL_BLIND_EMOJI,
)
from src.holdem import (
    FINISHED,
    FLOP,
    PREFLOP,
    HoldemError,
    HoldemGame,
    HoldemPlayer,
    best_hand,
    build_deck,
    evaluate_five,
)


def player(user_id, stack=1000, seat=None):
    return HoldemPlayer(user_id, f"P{user_id}", stack, user_id - 1 if seat is None else seat)


class HandEvaluationTests(unittest.TestCase):
    def test_wheel_straight_is_five_high(self):
        score = evaluate_five([
            ("A", "♠"), ("2", "♥"), ("3", "♦"), ("4", "♣"), ("5", "♠"),
        ])
        self.assertEqual((4, (5,)), score)

    def test_best_of_seven_prefers_full_house(self):
        score, name, cards = best_hand([
            ("A", "♠"), ("A", "♥"), ("A", "♦"),
            ("K", "♣"), ("K", "♠"), ("2", "♥"), ("3", "♥"),
        ])
        self.assertEqual(6, score[0])
        self.assertEqual("Фулл-хаус", name)
        self.assertEqual(5, len(cards))


class BettingTests(unittest.TestCase):
    def make_game(self, count=3, stack=1000):
        game = HoldemGame(
            [player(index + 1, stack=stack) for index in range(count)],
            small_blind=10,
            big_blind=20,
            rng=random.Random(1),
        )
        game.start_hand()
        return game

    def test_blinds_and_first_player_for_three_handed_game(self):
        game = self.make_game()
        self.assertEqual(PREFLOP, game.stage)
        self.assertEqual(0, game.dealer_index)
        self.assertEqual(1, game.small_blind_index)
        self.assertEqual(2, game.big_blind_index)
        self.assertEqual(0, game.current_index)
        self.assertEqual(30, game.pot)

    def test_heads_up_dealer_posts_small_blind_and_acts_first(self):
        game = self.make_game(count=2)
        self.assertEqual(game.dealer_index, game.small_blind_index)
        self.assertEqual(game.dealer_index, game.current_index)

    def test_call_call_check_advances_to_flop(self):
        game = self.make_game()
        game.act(1, "call")
        game.act(2, "call")
        game.act(3, "check")
        self.assertEqual(FLOP, game.stage)
        self.assertEqual(3, len(game.board))
        self.assertEqual(60, game.pot)

    def test_full_raise_reopens_action(self):
        game = self.make_game()
        game.act(1, "raise", 60)
        game.act(2, "call")
        game.act(3, "call")
        self.assertEqual(FLOP, game.stage)
        self.assertEqual(180, game.pot)

    def test_too_small_raise_is_rejected_unless_all_in(self):
        game = self.make_game()
        with self.assertRaises(HoldemError):
            game.act(1, "raise", 30)
        self.assertEqual(0, game.current_index)

    def test_configured_bet_cap_is_enforced(self):
        game = HoldemGame(
            [player(1, stack=25), player(2, stack=25)],
            small_blind=1,
            big_blind=1,
            max_bet=5,
            rng=random.Random(4),
        )
        game.start_hand()
        with self.assertRaises(HoldemError):
            game.act(game.current_player.user_id, "raise", 6)
        game.act(game.current_player.user_id, "raise", 5)
        self.assertEqual(5, game.current_bet)
        self.assertNotIn("raise", game.legal_actions(game.current_player.user_id))

    def test_everyone_folding_awards_the_whole_pot(self):
        game = self.make_game()
        game.act(1, "fold")
        game.act(2, "fold")
        self.assertEqual(FINISHED, game.stage)
        self.assertEqual(1010, game.players[2].stack)
        self.assertEqual((3,), game.pot_awards[0][1])


class SidePotTests(unittest.TestCase):
    def test_side_pots_are_awarded_to_eligible_players(self):
        game = HoldemGame(
            [player(1, 50), player(2, 100), player(3, 100)],
            small_blind=10,
            big_blind=20,
            rng=random.Random(2),
        )
        game.start_hand()

        # Force a deterministic showdown state. P1 wins the 150 main pot,
        # P2 wins the 100 side pot against P3.
        game.board = [
            ("A", "♠"), ("K", "♦"), ("7", "♣"), ("4", "♥"), ("2", "♠"),
        ]
        game.players[0].hole = [("A", "♥"), ("A", "♦")]
        game.players[1].hole = [("K", "♥"), ("K", "♣")]
        game.players[2].hole = [("Q", "♥"), ("J", "♣")]
        for p, contribution in zip(game.players, (50, 100, 100)):
            p.total_bet = contribution
            p.stack = 0
            p.all_in = True

        game._showdown()

        self.assertEqual(FINISHED, game.stage)
        self.assertEqual(150, game.players[0].stack)
        self.assertEqual(100, game.players[1].stack)
        self.assertEqual(0, game.players[2].stack)
        self.assertEqual([(150, (1,)), (100, (2,))], game.pot_awards)

    def test_all_in_players_trigger_automatic_runout(self):
        game = HoldemGame(
            [player(1, 20), player(2, 20)],
            small_blind=10,
            big_blind=20,
            rng=random.Random(3),
        )
        game.start_hand()
        game.act(1, "all_in")
        self.assertEqual(FINISHED, game.stage)
        self.assertEqual(5, len(game.board))


class DeckTests(unittest.TestCase):
    def test_standard_deck_contains_52_unique_cards(self):
        deck = build_deck()
        self.assertEqual(52, len(deck))
        self.assertEqual(52, len(set(deck)))


class PokerVisualAssetTests(unittest.TestCase):
    def test_blind_and_dealer_assets_are_available(self):
        root = Path(__file__).resolve().parents[1]
        casino_icons = root / "ref" / "icons" / "Casino"
        for filename in (
            "bigblind_icon.png",
            "dealer_icon.png",
            "smallblind_icon.png",
        ):
            self.assertTrue((casino_icons / filename).is_file())

    def test_discord_role_emojis_match_uploaded_assets(self):
        self.assertEqual(
            "<:bigblind_icon:1530254229229273208>",
            CASINO_BIG_BLIND_EMOJI,
        )
        self.assertEqual(
            "<:dealer_icon:1530254231083155517>",
            CASINO_DEALER_EMOJI,
        )
        self.assertEqual(
            "<:smallblind_icon:1530254232526131280>",
            CASINO_SMALL_BLIND_EMOJI,
        )

    def test_renderer_uses_the_same_rdr_fonts_as_the_site(self):
        root = Path(__file__).resolve().parents[1]
        fonts = root / "docs" / "fonts"
        for filename in ("RDRLino.ttf", "RDRGothica.ttf", "DroidSerifPro.ttf"):
            self.assertTrue((fonts / filename).is_file())
        self.assertTrue((root / "assets" / "images" / "poker_divider.png").is_file())


if __name__ == "__main__":
    unittest.main()
