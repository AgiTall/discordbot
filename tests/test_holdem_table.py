import asyncio
import unittest
from unittest.mock import patch

from cogs.holdem import (
    DEFAULT_BUY_IN,
    DiscordPokerTable,
    PokerMenuView,
    blind_structure,
)


class FakeAvatar:
    async def read(self):
        return b"not-an-image"


class FakeMember:
    def __init__(self, user_id, name):
        self.id = user_id
        self.display_name = name
        self.display_avatar = FakeAvatar()


class FakeBot:
    def __init__(self):
        self.accounts = {
            1: {"cash": 2000.0},
            2: {"cash": 2000.0},
        }
        self.economy_lock = asyncio.Lock()
        self.save_count = 0

    def set_economy_guild_id(self, guild_id):
        return guild_id

    def reset_economy_guild_id(self, token):
        pass

    def get_account(self, user_id):
        return self.accounts[user_id]

    def save_economy(self):
        self.save_count += 1


class FakeCog:
    def __init__(self):
        self.bot = FakeBot()
        self.tables = {}


class PokerTableEconomyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cog = FakeCog()
        self.table = DiscordPokerTable(
            self.cog,
            guild_id=10,
            channel_id=20,
            host_id=1,
        )
        self.cog.tables[self.table.key] = self.table

    async def test_join_escrows_buy_in_and_leave_returns_stack(self):
        joined = await self.table.seat_member(FakeMember(1, "One"))
        self.assertTrue(joined.ok)
        self.assertEqual(2000 - DEFAULT_BUY_IN, self.cog.bot.accounts[1]["cash"])
        self.assertEqual(DEFAULT_BUY_IN, self.table.player_by_id(1).stack)

        left = await self.table.leave(1)
        self.assertTrue(left.ok)
        self.assertEqual(2000, self.cog.bot.accounts[1]["cash"])
        self.assertIsNone(self.table.player_by_id(1))

    async def test_cannot_leave_during_a_hand(self):
        await self.table.seat_member(FakeMember(1, "One"))
        await self.table.seat_member(FakeMember(2, "Two"))
        started = self.table.start_hand(1)
        self.assertTrue(started.ok)

        left = await self.table.leave(1)
        self.assertFalse(left.ok)
        self.assertEqual(1000, self.cog.bot.accounts[1]["cash"])

    async def test_host_can_start_consecutive_numbered_hands(self):
        await self.table.seat_member(FakeMember(1, "One"))
        await self.table.seat_member(FakeMember(2, "Two"))
        self.assertTrue(self.table.start_hand(1).ok)
        self.assertEqual(1, self.table.game.hand_number)

        # End quickly by folding the heads-up dealer, then start again.
        current_id = self.table.game.current_player.user_id
        self.table.perform_action(current_id, "fold")
        self.assertTrue(self.table.start_hand(1).ok)
        self.assertEqual(2, self.table.game.hand_number)

    async def test_close_refunds_every_seated_player(self):
        await self.table.seat_member(FakeMember(1, "One"))
        await self.table.seat_member(FakeMember(2, "Two"))
        notice = await self.table.close(1)
        self.assertTrue(notice.ok)
        self.assertEqual(2000, self.cog.bot.accounts[1]["cash"])
        self.assertEqual(2000, self.cog.bot.accounts[2]["cash"])
        self.assertNotIn(self.table.key, self.cog.tables)

    async def test_buy_in_is_five_times_the_configured_max_bet(self):
        table = DiscordPokerTable(
            self.cog,
            guild_id=10,
            channel_id=21,
            host_id=1,
            max_bet=5,
        )
        self.cog.tables[table.key] = table
        joined = await table.seat_member(FakeMember(1, "One"))
        self.assertTrue(joined.ok)
        self.assertEqual(25, table.buy_in)
        self.assertEqual(25, table.player_by_id(1).stack)
        self.assertEqual(1975, self.cog.bot.accounts[1]["cash"])
        await table.close(1)

    async def test_busted_player_can_pay_the_full_buy_in_again(self):
        table = DiscordPokerTable(
            self.cog,
            guild_id=10,
            channel_id=21,
            host_id=1,
            max_bet=5,
        )
        self.cog.tables[table.key] = table
        await table.seat_member(FakeMember(1, "One"))
        table.player_by_id(1).stack = 0
        notice = await table.rebuy(1)
        self.assertTrue(notice.ok)
        self.assertEqual(25, table.player_by_id(1).stack)
        self.assertEqual(1950, self.cog.bot.accounts[1]["cash"])
        await table.close(1)

    async def test_unjoined_table_expires_and_refunds_host(self):
        await self.table.seat_member(FakeMember(1, "One"))
        with patch("cogs.holdem.TABLE_JOIN_TIMEOUT_SECONDS", 0):
            self.table.schedule_join_timeout()
            await asyncio.sleep(0.02)
        self.assertTrue(self.table.closed)
        self.assertNotIn(self.table.key, self.cog.tables)
        self.assertEqual(2000, self.cog.bot.accounts[1]["cash"])

    async def test_first_hand_auto_starts_after_waiting_period(self):
        await self.table.seat_member(FakeMember(1, "One"))
        with patch("cogs.holdem.TABLE_AUTO_START_SECONDS", 0):
            await self.table.seat_member(FakeMember(2, "Two"))
            await asyncio.sleep(0.02)
        self.assertTrue(self.table.hand_active)
        self.assertEqual(1, self.table.hand_number)

    async def test_dealer_rotation_survives_a_player_leaving(self):
        self.cog.bot.accounts[3] = {"cash": 2000.0}
        await self.table.seat_member(FakeMember(1, "One"))
        await self.table.seat_member(FakeMember(2, "Two"))
        await self.table.seat_member(FakeMember(3, "Three"))
        self.assertTrue(self.table.start_hand(1).ok)
        self.assertEqual(0, self.table.dealer_seat)

        # Finish, remove seat 1, then the button must move from seat 0 to seat 2.
        self.table.perform_action(self.table.game.current_player.user_id, "fold")
        self.table.perform_action(self.table.game.current_player.user_id, "fold")
        self.assertTrue((await self.table.leave(2)).ok)
        self.assertTrue(self.table.start_hand(1).ok)
        self.assertEqual(2, self.table.dealer_seat)


class PokerLobbyContractTests(unittest.TestCase):
    def test_poker_menu_has_exactly_create_and_join_buttons(self):
        cog = FakeCog()
        view = PokerMenuView(cog, user_id=1)
        self.assertEqual(
            ["Создать стол", "Присоединиться к существующему"],
            [item.label for item in view.children],
        )

    def test_blinds_scale_with_maximum_bet(self):
        self.assertEqual((1, 1), blind_structure(5))
        self.assertEqual((10, 20), blind_structure(200))


if __name__ == "__main__":
    unittest.main()
