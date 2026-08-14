import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from src.leveling import (
    AntiFarm,
    LevelingCog,
    calculate_total_xp_for_level,
    calculate_xp_for_level,
    draw_progress_bar,
    format_voice_duration,
)


class FakeLevelingDB:
    def __init__(self, *, xp=0, level=1, rate=1.0):
        self.xp = xp
        self.level = level
        self.rate = rate
        self.increment_calls = []
        self.level_updates = []
        self.voice_records = []
        self.top_user_calls = []

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

    def record_voice_session(self, guild_id, user_id, duration_seconds):
        self.voice_records.append((guild_id, user_id, duration_seconds))

    def get_top_users(self, guild_id, limit=10, user_ids=None):
        self.top_user_calls.append((guild_id, limit, user_ids))
        return []


def make_cog(db):
    cog = object.__new__(LevelingCog)
    cog.bot = SimpleNamespace()
    cog.db = db
    cog.anti_farm = AntiFarm()
    cog.active_voice_sessions = {}
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

    def test_voice_duration_is_human_readable(self):
        self.assertEqual(format_voice_duration(0), "0 сек")
        self.assertEqual(format_voice_duration(3665), "1 ч 1 мин")
        self.assertEqual(format_voice_duration(90061), "1 д 1 ч 1 мин")

    def test_finished_voice_session_persists_the_longest_candidate(self):
        db = FakeLevelingDB()
        cog = make_cog(db)
        member = make_member()

        cog._start_voice_session(member, now=100)
        duration = cog._finish_voice_session(member, now=3705)

        self.assertEqual(duration, 3605)
        self.assertEqual(db.voice_records, [("7", "42", 3605)])


class LevelingRewardTests(unittest.IsolatedAsyncioTestCase):
    async def test_leaderboard_filters_to_current_non_bot_members(self):
        db = FakeLevelingDB()
        cog = make_cog(db)
        guild = SimpleNamespace(
            id=7,
            members=[
                SimpleNamespace(id=42, bot=False),
                SimpleNamespace(id=43, bot=False),
                SimpleNamespace(id=99, bot=True),
            ],
        )
        interaction = SimpleNamespace(
            guild=guild,
            response=SimpleNamespace(send_message=AsyncMock()),
        )

        await LevelingCog.leaderboard_cmd.callback(cog, interaction)

        self.assertEqual(db.top_user_calls, [("7", 10, ["42", "43"])])
        interaction.response.send_message.assert_awaited_once_with(
            "Рейтинг пока пуст.",
            ephemeral=True,
        )

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

    async def test_hourly_voice_reward_credits_current_guild_account(self):
        class FakeLock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        guild = SimpleNamespace(id=7, afk_channel=None)
        channel = SimpleNamespace(id=70)
        member = make_member()
        member.guild = guild
        member.voice = SimpleNamespace(channel=channel)
        account = {"cash": 125.0}

        cog = make_cog(FakeLevelingDB())
        cog.bot = SimpleNamespace(
            economy_lock=FakeLock(),
            set_economy_guild_id=Mock(return_value="token"),
            reset_economy_guild_id=Mock(),
            get_account=Mock(return_value=account),
            save_economy=Mock(),
        )

        awarded = await cog._award_voice_cash(
            guild,
            {("7", "42"): (member, 2)},
        )

        self.assertEqual(account["cash"], 225.0)
        self.assertEqual(awarded, {("7", "42"): 2})
        cog.bot.set_economy_guild_id.assert_called_once_with(7)
        cog.bot.save_economy.assert_called_once_with()
        cog.bot.reset_economy_guild_id.assert_called_once_with("token")

    async def test_completed_voice_hour_is_not_paid_twice(self):
        class FakeLock:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        guild = SimpleNamespace(id=7, afk_channel=None, stage_channels=[])
        channel = SimpleNamespace(id=70, members=[])
        guild.voice_channels = [channel]
        member = make_member()
        member.guild = guild
        member.voice = SimpleNamespace(channel=channel)
        channel.members = [member]
        account = {"cash": 0.0}

        cog = make_cog(FakeLevelingDB())
        cog.bot = SimpleNamespace(
            economy_lock=FakeLock(),
            set_economy_guild_id=Mock(return_value="token"),
            reset_economy_guild_id=Mock(),
            get_account=Mock(return_value=account),
            save_economy=Mock(),
        )

        await cog._update_voice_sessions(guild, now=100)
        await cog._update_voice_sessions(guild, now=3700)
        await cog._update_voice_sessions(guild, now=3710)

        self.assertEqual(account["cash"], 50.0)
        self.assertEqual(cog.bot.save_economy.call_count, 1)


if __name__ == "__main__":
    unittest.main()
