import unittest
from datetime import date
from unittest.mock import patch

from src.mine_logic import (
    DAILY_MINE_LIMIT,
    DEPTH_LAYERS,
    ORE_SELL_PRICE,
    get_item_name,
    get_item_price,
    get_jewelry_name,
    get_jewelry_emoji,
    get_jewelry_sell_price,
    make_jewelry_key,
    parse_jewelry_key,
    reset_daily_if_needed,
    roll_mine,
)


def make_player(*, depth=0):
    return {
        "pickaxe_type": "basic",
        "pickaxe_durability": 60,
        "canary_count": 0,
        "wood_count": 0,
        "current_depth": depth,
        "inventory": {},
    }


class MineDailyLimitTests(unittest.TestCase):
    def test_daily_limit_resets_on_a_new_day(self):
        player = {"daily_mines_left": 0, "last_mine_date": "2000-01-01"}
        reset_daily_if_needed(player)
        self.assertEqual(player["daily_mines_left"], DAILY_MINE_LIMIT)

    def test_daily_limit_is_not_reset_twice_on_the_same_day(self):
        player = {
            "daily_mines_left": 2,
            "last_mine_date": date.today().isoformat(),
        }
        reset_daily_if_needed(player)
        self.assertEqual(player["daily_mines_left"], 2)


class MineJewelryTests(unittest.TestCase):
    def test_jewelry_key_round_trip_and_sale_data(self):
        key = make_jewelry_key("silver", "emerald", "brooch")
        self.assertEqual(parse_jewelry_key(key), ("silver", "emerald", "brooch"))
        self.assertEqual(get_jewelry_name(key), "Серебряная брошь с изумрудом")
        self.assertEqual(get_item_name(key), get_jewelry_name(key))
        self.assertGreater(get_jewelry_sell_price(key), 0)
        self.assertEqual(get_item_price(key), get_jewelry_sell_price(key))
        self.assertEqual(
            get_jewelry_emoji(key),
            "<:provision_jewelry_sphr_bracelet:1527605714611212370>",
        )

    def test_invalid_jewelry_key_is_not_sellable(self):
        key = "jewel_unknown_value"
        self.assertIsNone(parse_jewelry_key(key))
        self.assertEqual(get_jewelry_sell_price(key), 0.0)


class MineRollTests(unittest.TestCase):
    def test_shallow_shift_has_a_mean_raw_value_near_one_hundred(self):
        shallow = DEPTH_LAYERS[0]["ores"]["coal"]
        average_amount = sum(shallow["amount"]) / 2
        expected_shift_value = (
            DAILY_MINE_LIMIT
            * shallow["chance"]
            * average_amount
            * ORE_SELL_PRICE["coal"]
        )
        self.assertGreaterEqual(expected_shift_value, 99)
        self.assertGreaterEqual(shallow["amount"][0] * ORE_SELL_PRICE["coal"], 20)

    @patch("src.mine_logic.roll_gem", return_value=None)
    @patch("src.mine_logic.random.randint", return_value=4)
    @patch("src.mine_logic.random.random", side_effect=[0.99, 0.99, 0.99, 0.0])
    def test_successful_ore_roll_updates_inventory(self, _random, _randint, _gem):
        player = make_player(depth=0)
        result = roll_mine(player, has_oil=True)
        self.assertEqual(result["ore"], "coal")
        self.assertEqual(result["ore_amount"], 4)
        self.assertEqual(player["inventory"]["coal"], 4)

    @patch("src.mine_logic.roll_gem", return_value=None)
    @patch("src.mine_logic.random.randint", return_value=4)
    @patch(
        "src.mine_logic.random.random",
        side_effect=[0.99, 0.99, 0.25, 0.99, 0.0],
    )
    def test_no_oil_penalty_does_not_discard_a_quarter_roll(
        self, _random, _randint, _gem
    ):
        player = make_player(depth=17)
        result = roll_mine(player, has_oil=False)
        self.assertEqual(result["ore"], "coal")
        self.assertEqual(result["ore_amount"], 4)

    @patch("src.mine_logic.roll_gem", return_value=None)
    @patch("src.mine_logic.random.randint", return_value=4)
    @patch(
        "src.mine_logic.random.random",
        side_effect=[0.0, 0.99, 0.99, 0.99, 0.0],
    )
    def test_unprotected_gas_halves_ore_instead_of_discarding_it(
        self, _random, _randint, _gem
    ):
        player = make_player(depth=100)
        result = roll_mine(player, has_oil=True)
        self.assertTrue(result["gas"])
        self.assertFalse(result["gas_blocked"])
        self.assertEqual(result["ore_amount"], 2)
        self.assertEqual(player["inventory"][result["ore"]], 2)


if __name__ == "__main__":
    unittest.main()
