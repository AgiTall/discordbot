import random
import unittest
from datetime import datetime, timedelta, timezone

from src.trader_logic import (
    TRADER_HUNTING_WAGON_COST,
    TRADER_PRODUCTION_SECONDS,
    TRADER_ROUTE_GOODS,
    TRADER_ROUTE_XP,
    TRADER_RESUPPLY_XP,
    TRADER_SUPPLY_BATCH,
    TRADER_WAGONS,
    add_trader_materials,
    buy_trader_upgrade,
    can_buy_trader_upgrade,
    complete_trader_delivery,
    complete_trade_route,
    default_trader_data,
    get_trader_account,
    get_trader_capacity,
    get_trade_route_slot,
    resupply_trader,
    trader_needs_supplies,
    update_trader_production,
)
from src.constants import ROLE_DEFINITIONS


class TraderLogicTests(unittest.TestCase):
    def test_reference_wagon_prices_capacities_and_rewards(self):
        self.assertEqual(
            {
                "small": (25, 0.0, (50.0, 62.5), (250, 312)),
                "medium": (50, 500.0, (150.0, 187.5), (1250, 1562)),
                "large": (100, 750.0, (500.0, 625.0), (2000, 2500)),
            },
            {
                key: (wagon["capacity"], wagon["cost"], wagon["cash"], wagon["xp"])
                for key, wagon in TRADER_WAGONS.items()
            },
        )
        self.assertEqual(875.0, TRADER_HUNTING_WAGON_COST)
        trader_role = next(role for role in ROLE_DEFINITIONS if role["key"] == "trader")
        self.assertEqual(15.0, trader_role["price"])

    def test_legacy_percent_is_migrated_to_small_wagon_goods(self):
        account = {"dealer_wagon": 40}
        trader = get_trader_account(account)

        self.assertEqual("small", trader["wagon_size"])
        self.assertEqual(10, trader["goods"])
        self.assertEqual(40.0, account["dealer_wagon"])

    def test_one_good_is_produced_every_two_minutes_and_stops_at_25(self):
        trader = default_trader_data()
        trader["wagon_size"] = "large"
        add_trader_materials(trader, 100)
        started = datetime(2026, 1, 1, tzinfo=timezone.utc)
        trader["production_updated_at"] = started.isoformat()

        produced = update_trader_production(
            trader,
            now=started + timedelta(seconds=TRADER_PRODUCTION_SECONDS * 40),
        )

        self.assertEqual(TRADER_SUPPLY_BATCH, produced)
        self.assertEqual(25, trader["goods"])
        self.assertEqual(0, trader["supplies_remaining"])
        self.assertTrue(trader_needs_supplies(trader))

    def test_supply_mission_restores_batch_and_grants_500_xp(self):
        trader = default_trader_data()
        trader["wagon_size"] = "medium"
        trader["goods"] = 25
        trader["supplies_remaining"] = 0

        supplied, _ = resupply_trader(trader, method="mission")

        self.assertTrue(supplied)
        self.assertEqual(TRADER_SUPPLY_BATCH, trader["supplies_remaining"])
        self.assertEqual(TRADER_RESUPPLY_XP, 500)
        self.assertGreaterEqual(trader["level"], 2)

    def test_large_wagon_requires_medium_first(self):
        trader = default_trader_data()
        self.assertFalse(can_buy_trader_upgrade(trader, "large"))
        self.assertTrue(buy_trader_upgrade(trader, "medium"))
        self.assertEqual(50, get_trader_capacity(trader))
        self.assertTrue(buy_trader_upgrade(trader, "large"))
        self.assertEqual(100, get_trader_capacity(trader))

    def test_full_large_delivery_uses_reference_reward_range(self):
        trader = default_trader_data()
        trader["wagon_size"] = "large"
        trader["goods"] = 100

        cash, xp, _ = complete_trader_delivery(trader, random.Random(7))

        self.assertGreaterEqual(cash, 500.0)
        self.assertLessEqual(cash, 625.0)
        self.assertGreaterEqual(xp, 2000)
        self.assertLessEqual(xp, 2500)
        self.assertEqual(0, trader["goods"])

    def test_trade_route_has_two_daily_slots_and_cannot_be_claimed_twice(self):
        trader = default_trader_data()
        trader["level"] = 4
        trader["wagon_size"] = "large"
        morning = datetime(2026, 1, 1, 7, 0, tzinfo=timezone.utc)

        first = complete_trade_route(trader, now=morning, rng=random.Random(3))
        duplicate = complete_trade_route(trader, now=morning, rng=random.Random(3))
        evening = complete_trade_route(
            trader,
            now=morning + timedelta(hours=14),
            rng=random.Random(4),
        )

        self.assertEqual("2026-01-01T09:22", get_trade_route_slot(now=morning))
        self.assertEqual(TRADER_ROUTE_GOODS, first[0])
        self.assertEqual(TRADER_ROUTE_XP, first[2])
        self.assertIsNone(duplicate)
        self.assertIsNotNone(evening)


if __name__ == "__main__":
    unittest.main()
