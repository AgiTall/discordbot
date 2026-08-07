import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from cogs.temp_voice import TemporaryVoiceCog, normalize_temp_voice_records, sanitize_voice_channel_name


class TemporaryVoiceHelpersTests(unittest.TestCase):
    def test_channel_name_is_compact_and_limited(self):
        self.assertEqual(sanitize_voice_channel_name("  Поход\n  за наградой  "), "Поход за наградой")
        self.assertEqual(len(sanitize_voice_channel_name("я" * 150)), 100)

    def test_empty_channel_name_uses_fallback(self):
        self.assertEqual(sanitize_voice_channel_name("\n\t"), "Быстрый канал")

    def test_persisted_records_are_normalized(self):
        self.assertEqual(
            normalize_temp_voice_records(
                {
                    "100": {"owner_id": "200", "message_id": "300"},
                    "101": "201",
                    "broken": {"owner_id": "202"},
                    "102": {"owner_id": "invalid"},
                }
            ),
            {
                "100": {"owner_id": 200, "message_id": 300},
                "101": {"owner_id": 201, "message_id": None},
            },
        )


class TemporaryVoiceLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def make_cog(self):
        data = {"temp_voice_channels": {}}
        bot = SimpleNamespace(
            get_economy_guild_data=lambda guild_id: data,
            save_economy=Mock(),
        )
        return TemporaryVoiceCog(bot), data

    async def test_creator_join_creates_moves_and_persists_owner(self):
        cog, data = self.make_cog()
        cog.refresh_control_message = AsyncMock()
        owner_overwrite = discord.PermissionOverwrite()
        created = SimpleNamespace(
            id=500,
            guild=None,
            overwrites_for=lambda member: owner_overwrite,
            set_permissions=AsyncMock(),
            delete=AsyncMock(),
        )
        guild = SimpleNamespace(
            id=10,
            get_channel=lambda channel_id: None,
            create_voice_channel=AsyncMock(return_value=created),
        )
        created.guild = guild
        member = SimpleNamespace(
            id=20,
            guild=guild,
            display_name="Ковбой",
            move_to=AsyncMock(),
            send=AsyncMock(),
            __str__=lambda self: "Ковбой",
        )
        creator = SimpleNamespace(
            category=None,
            position=4,
            bitrate=64000,
            rtc_region=None,
            video_quality_mode=discord.VideoQualityMode.auto,
            overwrites={},
        )

        await cog.create_or_reuse_channel(member, creator)

        guild.create_voice_channel.assert_awaited_once()
        member.move_to.assert_awaited_once_with(created, reason="Temporary voice: move owner")
        self.assertEqual(
            data["temp_voice_channels"]["500"],
            {"owner_id": 20, "message_id": None},
        )
        self.assertTrue(owner_overwrite.view_channel)
        self.assertTrue(owner_overwrite.connect)
        cog.refresh_control_message.assert_awaited_once_with(created)

    async def test_empty_temporary_channel_is_deleted(self):
        cog, data = self.make_cog()
        data["temp_voice_channels"] = {
            "500": {"owner_id": 20, "message_id": None}
        }
        channel = SimpleNamespace(
            id=500,
            guild=SimpleNamespace(id=10),
            members=[],
            delete=AsyncMock(),
        )

        await cog.clean_or_transfer(channel)

        channel.delete.assert_awaited_once()
        self.assertEqual(data["temp_voice_channels"], {})


if __name__ == "__main__":
    unittest.main()
