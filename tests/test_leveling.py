import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.leveling import (
    AntiFarm,
    LevelingCog,
    calculate_total_xp_for_level,
    calculate_xp_for_level,
    draw_progress_bar,
)


class FakeLevelingDB:
    def __init__(self, *, xp=0, level=1, rate=1.0):
        self.xp = xp
        self.level = level
        self.rate = rate
        self.increment_calls = []
        self.level_updates = []

    def get_xp_rate(self, guild_id, source):
        return self.rate

    def increment_user_xp(self, guild_id, user_id, amount):
        self.increment_calls.append((guild_id, user_id, amount))
        self.xp += amount
        return {"xp": self.xp, "level": self.level}

    def set_user_level_at_least(self, guild_id, user_id, level):
        self.level_updates.append((guild_id, user_id, level))
        self.level = max(self.level, level)

    def get_rank_roles(self, guild_id):
        return {}

    def get_setting(self, guild_id, key, default=None):
        return default


def make_cog(db):
    cog = object.__new__(LevelingCog)
    cog.bot = SimpleNamespace()
    cog.db = db
    cog.anti_farm = AntiFarm()
    return cog


def make_member(*, user_id=42, guild_id=7, bot=False):
    guild = SimpleNamespace(id=guild_id)
    return SimpleNamespace(id=user_id, guild=guild, bot=bot, roles=[])


class LevelingFormulaTests(unittest.TestCase):
    def test_bot_thresholds_match_the_rounded_public_formula(self):
        self.assertEqual(calculate_xp_for_level(1), 0)
        self.assertEqual(calculate_xp_for_level(2), 283)
        self.assertEqual(calculate_xp_for_level(3), 520)
        self.assertEqual(calculate_total_xp_for_level(3), 803)

    def test_progress_bar_is_clamped_to_its_requested_length(self):
        self.assertEqual(draw_progress_bar(200, 100, 4), "🟩" * 4)
        self.assertEqual(draw_progress_bar(-10, 100, 4), "⬜" * 4)

    def test_antifarm_state_is_isolated_by_guild_and_user(self):
        anti_farm = AntiFarm()
        self.assertTrue(anti_farm.check_message((1, 42), "hello"))
        self.assertTrue(anti_farm.check_message((2, 42), "hello"))

    def test_invalid_integer_setting_falls_back_to_default(self):
        db = FakeLevelingDB()
        db.get_setting = lambda guild_id, key, default=None: "broken"
        cog = make_cog(db)

        self.assertEqual(cog.get_base_message_xp("7"), 15)
        self.assertEqual(cog.get_antifarm_cooldown("7"), 60)


class LevelingRewardTests(unittest.IsolatedAsyncioTestCase):
    async def test_profession_event_is_forwarded_to_xp_accounting(self):
        cog = make_cog(FakeLevelingDB())
        cog.add_xp = AsyncMock()
        member = make_member()

        await cog.on_leveling_add_xp(member, 350, "jobs")

        cog.add_xp.assert_awaited_once_with(member, 350, source="jobs")

    async def test_reward_is_incremented_and_level_is_persisted(self):
        db = FakeLevelingDB(xp=280, level=1)
        cog = make_cog(db)
        cog.handle_level_up = AsyncMock()
        member = make_member()

        await cog.add_xp(member, 10, source="jobs")

        self.assertEqual(db.increment_calls, [("7", "42", 10)])
        self.assertEqual(db.level_updates, [("7", "42", 2)])
        cog.handle_level_up.assert_awaited_once_with(member, 2)

    async def test_non_finite_reward_is_ignored(self):
        db = FakeLevelingDB()
        cog = make_cog(db)

        await cog.add_xp(make_member(), float("nan"), source="jobs")

        self.assertEqual(db.increment_calls, [])

    async def test_role_sync_without_notification_returns_a_result_tuple(self):
        cog = make_cog(FakeLevelingDB())
        member = make_member()

        result = await cog.handle_level_up(member, 1, notify=False)

        self.assertEqual(result, (None, None))


if __name__ == "__main__":
    unittest.main()
