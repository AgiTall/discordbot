from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.services.guild_service import sync_bot_guilds
from app.utils.dependencies import require_guild_access


class GuildAccessTests(IsolatedAsyncioTestCase):
    def _request(self, guild):
        bot = SimpleNamespace(get_guild=lambda guild_id: guild)
        return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(bot=bot)))

    async def test_uses_live_discord_permissions(self):
        member = SimpleNamespace(
            guild_permissions=SimpleNamespace(
                administrator=False,
                manage_guild=True,
            )
        )
        guild = SimpleNamespace(fetch_member=AsyncMock(return_value=member))
        user = SimpleNamespace(discord_id="42", guilds_json="[]")

        allowed = await require_guild_access("123", user, self._request(guild))

        self.assertTrue(allowed)
        guild.fetch_member.assert_awaited_once_with(42)

    async def test_stale_cached_permission_does_not_grant_access(self):
        member = SimpleNamespace(
            guild_permissions=SimpleNamespace(
                administrator=False,
                manage_guild=False,
            )
        )
        guild = SimpleNamespace(fetch_member=AsyncMock(return_value=member))
        user = SimpleNamespace(
            discord_id="42",
            guilds_json='[{"id":"123","canManage":true}]',
        )

        with self.assertRaises(HTTPException) as raised:
            await require_guild_access("123", user, self._request(guild))

        self.assertEqual(raised.exception.status_code, 403)

    async def test_discord_lookup_failure_fails_closed(self):
        guild = SimpleNamespace(fetch_member=AsyncMock(side_effect=RuntimeError("down")))
        user = SimpleNamespace(discord_id="42", guilds_json=None)

        with self.assertRaises(HTTPException) as raised:
            await require_guild_access("123", user, self._request(guild))

        self.assertEqual(raised.exception.status_code, 403)


class GuildSyncTests(IsolatedAsyncioTestCase):
    async def test_new_guild_is_not_granted_lifetime_access(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=[]))

        with patch(
            "app.services.guild_service.get_or_create_guild",
            new=AsyncMock(),
        ) as create:
            created = await sync_bot_guilds(db, [("123", "Test Guild")])

        self.assertEqual(created, 1)
        create.assert_awaited_once_with(
            db,
            "123",
            "Test Guild",
            lifetime_free=False,
        )
