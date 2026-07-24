import asyncio
import unittest

from cogs.holdem import HoldemCog
from src.poker_cosmetics import (
    COSMETIC_AVATAR_INSET,
    COSMETIC_AVATAR_SIZE,
    COSMETIC_CANVAS_SIZE,
    POKER_COSMETICS,
    cosmetic_asset_filename,
    normalize_poker_cosmetics,
)


class PokerCosmeticStateTests(unittest.TestCase):
    def test_asset_contract_centers_the_avatar(self):
        self.assertEqual(128, COSMETIC_CANVAS_SIZE)
        self.assertEqual(88, COSMETIC_AVATAR_SIZE)
        self.assertEqual(20, COSMETIC_AVATAR_INSET)

    def test_invalid_legacy_state_is_safely_normalized(self):
        account = {
            "poker_cosmetics": {
                "owned": ["legend", "missing", "legend"],
                "equipped": "missing",
            }
        }
        state = normalize_poker_cosmetics(account)
        self.assertEqual(["none"], state["owned"])
        self.assertEqual("none", state["equipped"])

    def test_every_catalog_item_has_two_variant_asset_names(self):
        for key in POKER_COSMETICS:
            self.assertEqual(
                f"{key}_normal.png",
                cosmetic_asset_filename(key, active=False),
            )
            self.assertEqual(
                f"{key}_active.png",
                cosmetic_asset_filename(key, active=True),
            )


class FakeEconomyBot:
    def __init__(self):
        self.accounts = {1: {"cash": 500.0}}
        self.guild_data = {
            "users": self.accounts,
            "poker_cosmetic_catalog": {
                "brass": {
                    "name": "Латунная рамка",
                    "description": "Тестовая рамка.",
                    "price": 150,
                    "normal_png": "",
                    "active_png": "",
                }
            },
        }
        self.economy_lock = asyncio.Lock()
        self.saved = 0

    def set_economy_guild_id(self, guild_id):
        return guild_id

    def reset_economy_guild_id(self, token):
        pass

    def get_account(self, user_id):
        return self.accounts[user_id]

    def get_economy_guild_data(self, guild_id):
        return self.guild_data

    def save_economy(self):
        self.saved += 1


class PokerCosmeticPurchaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_purchase_and_equip_use_the_regular_cash_balance(self):
        bot = FakeEconomyBot()
        cog = HoldemCog(bot)
        notice = await cog.purchase_cosmetic(10, 1, "brass")
        self.assertIn("Куплено", notice)
        self.assertEqual(350.0, bot.accounts[1]["cash"])

        notice = await cog.equip_cosmetic(10, 1, "brass")
        self.assertIn("Надето", notice)
        state = bot.accounts[1]["poker_cosmetics"]
        self.assertEqual("brass", state["equipped"])
        self.assertIn("brass", state["owned"])


if __name__ == "__main__":
    unittest.main()
