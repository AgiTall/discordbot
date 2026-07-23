import json
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from app.routers.gangs import get_my_gang, get_my_profile
from app.routers.settings import _validate_settings_payload
from app.services.auth_service import create_session_from_code
from src.guild_config import get_guild_settings, set_guild_settings


ROOT = Path(__file__).resolve().parents[1]


class SettingsValidationTests(TestCase):
    def setUp(self):
        self.guild = SimpleNamespace(
            id=100,
            channels=[SimpleNamespace(id=200), SimpleNamespace(id=201)],
            roles=[SimpleNamespace(id=100), SimpleNamespace(id=300)],
        )

    def test_accepts_channels_and_role_from_selected_guild(self):
        _validate_settings_payload(
            self.guild,
            {
                "newsChannelId": "200",
                "agitationChannelId": "201",
                "commandChannelIds": "200, 201",
                "welcomeRoleId": "300",
                "xpRateMessages": "2.5",
                "goldRate": "750.50",
                "workSuccessMessage": "{mention}: {scenario}, награда {reward}",
                "roleRequiredMessage": "Нужна профессия {role}",
                "autoReactions": [{
                    "channelId": "200",
                    "emojis": ["🏆", "🎉"],
                    "messageType": "default",
                    "triggers": ["победа"],
                    "excludedTriggers": ["не победа"],
                }],
            },
        )

    def test_rejects_resource_from_another_guild(self):
        with self.assertRaises(Exception) as raised:
            _validate_settings_payload(self.guild, {"logsChannelId": "999"})
        self.assertEqual(raised.exception.status_code, 400)

    def test_rejects_unknown_message_template_variable(self):
        with self.assertRaises(Exception) as raised:
            _validate_settings_payload(
                self.guild,
                {"workSuccessMessage": "Награда: {unknown}"},
            )
        self.assertEqual(raised.exception.status_code, 400)

    def test_dashboard_initializes_auto_reactions_for_legacy_settings(self):
        source = (ROOT / "docs" / "js" / "app.js").read_text(encoding="utf-8")
        setup = source[source.index("function setupDashboardUi"):source.index("function initSidebarMobileToggle")]
        self.assertIn("initAutoReactionEditor(settings?.autoReactions || [])", setup)

        dashboard = (ROOT / "docs" / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn('src="js/app.js?v=', dashboard)

    def test_auto_reaction_picker_has_categories_search_and_custom_input(self):
        source = (ROOT / "docs" / "js" / "app.js").read_text(encoding="utf-8")
        dashboard = (ROOT / "docs" / "dashboard.html").read_text(encoding="utf-8")

        self.assertIn("REACTION_EMOJI_CATEGORIES", source)
        self.assertIn("guildEmojisCache.map", source)
        self.assertNotIn("prompt('Введите Unicode-эмодзи", source)
        self.assertIn('id="autoReactionEmojiCategories"', dashboard)
        self.assertIn('id="autoReactionEmojiSearch"', dashboard)
        self.assertIn('id="autoReactionCustomEmojiInput"', dashboard)


class GuildSettingsRoundTripTests(TestCase):
    class EconomyStore:
        def __init__(self):
            self.data = {}
            self.saved = 0

        def guild_data(self, guild_id):
            return self.data

        def save_all(self):
            self.saved += 1

    class LevelingStore:
        def __init__(self):
            self.settings = {}
            self.rates = {}

        def get_setting(self, guild_id, key, default=None):
            return self.settings.get(key, default)

        def set_setting(self, guild_id, key, value):
            self.settings[key] = value

        def get_xp_rate(self, guild_id, source):
            return self.rates.get(source, 1.0)

        def set_xp_rate(self, guild_id, source, value):
            self.rates[source] = value

        def get_rank_roles(self, guild_id):
            return {}

    def test_advanced_dashboard_settings_reach_bot_store(self):
        economy = self.EconomyStore()
        leveling = self.LevelingStore()

        saved = set_guild_settings(
            economy,
            leveling,
            "100",
            {
                "agitationChannelId": "201",
                "goldRate": "812.25",
                "safeEmoji": "🔐",
                "balanceGangEmoji": "<:gang:123456789>",
                "roleIconMoonshiner": "🥃",
                "workSuccessMessage": "{mention}: {scenario}; {reward}",
                "roleRequiredMessage": "Сначала получите роль {role}",
                "autoReactions": [{
                    "channelId": "201",
                    "emojis": ["🤠", "🔥"],
                    "messageType": "all",
                    "triggers": ["  Дикий   Запад "],
                    "excludedTriggers": ["спойлер"],
                }],
            },
        )

        self.assertEqual(economy.saved, 1)
        self.assertEqual(economy.data["agitation_channel_id"], 201)
        self.assertEqual(economy.data["gold_rate"], 812.25)
        self.assertEqual(economy.data["gold_rate_history"][-1]["rate"], 812.25)
        self.assertEqual(economy.data["balance_ui_gang"], "<:gang:123456789>")
        self.assertEqual(economy.data["role_key_icons"]["moonshiner"], "🥃")
        self.assertEqual(
            economy.data["auto_reactions"],
            [{
                "channel_id": "201",
                "emojis": ["🤠", "🔥"],
                "message_type": "all",
                "triggers": ["Дикий Запад"],
                "excluded_triggers": ["спойлер"],
            }],
        )
        self.assertEqual(saved["roleRequiredMessage"], "Сначала получите роль {role}")
        self.assertEqual(saved["goldRateHistory"][-1]["rate"], 812.25)
        self.assertEqual(saved["autoReactions"], [{
            "channelId": "201",
            "emojis": ["🤠", "🔥"],
            "messageType": "all",
            "triggers": ["Дикий Запад"],
            "excludedTriggers": ["спойлер"],
        }])
        self.assertEqual(get_guild_settings(economy, leveling, "100")["agitationChannelId"], "201")


class DashboardApiTests(IsolatedAsyncioTestCase):
    async def test_oauth_keeps_player_guilds_without_manage_permission(self):
        result = SimpleNamespace(scalar_one_or_none=lambda: None)
        db = SimpleNamespace(
            execute=AsyncMock(return_value=result),
            add=lambda row: setattr(db, "added", row),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        with (
            patch("app.services.auth_service.discord_api.exchange_code", new=AsyncMock(return_value={"access_token": "access"})),
            patch("app.services.auth_service.discord_api.get_user", new=AsyncMock(return_value={"id": "42", "username": "player"})),
            patch(
                "app.services.auth_service.discord_api.get_user_guilds",
                new=AsyncMock(
                    return_value=[
                        {"id": "100", "name": "Managed", "permissions": 0x20},
                        {"id": "200", "name": "Player only", "permissions": 0},
                    ]
                ),
            ),
        ):
            await create_session_from_code("code", db, {"100", "200"})

        guilds = json.loads(db.added.guilds_json)
        self.assertEqual([guild["id"] for guild in guilds], ["100", "200"])
        self.assertTrue(guilds[0]["canManage"])
        self.assertFalse(guilds[1]["canManage"])

    async def test_profile_returns_authenticated_players_gang(self):
        guild = SimpleNamespace(fetch_member=AsyncMock(return_value=object()))
        bot = SimpleNamespace(get_guild=lambda guild_id: guild)
        store = SimpleNamespace(
            guild_data=lambda guild_id: {
                "gangs": {
                    "Armadillo": {
                        "id": 7,
                        "leader": 42,
                        "members": [42, 43],
                        "cash": 1250,
                        "camp_upgrades": {"camp": 1},
                    }
                }
            }
        )
        request = SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(bot=bot, economy_data=store)
            )
        )
        user = SimpleNamespace(discord_id="42")

        response = await get_my_gang("100", request, user)

        self.assertEqual(response["gang"]["name"], "Armadillo")
        self.assertEqual(response["gang"]["member_count"], 2)
        self.assertEqual(response["my_role"], "leader")

    async def test_profile_returns_player_economy(self):
        member = SimpleNamespace(
            display_name="Arthur",
            display_avatar=SimpleNamespace(url="https://example.test/avatar.png"),
        )
        guild = SimpleNamespace(fetch_member=AsyncMock(return_value=member))
        leveling_db = SimpleNamespace(
            get_user=lambda guild_id, user_id: {"xp": 1250, "level": 6},
            get_user_rank_position=lambda guild_id, user_id: 4,
        )
        bot = SimpleNamespace(
            get_guild=lambda guild_id: guild,
            get_cog=lambda name: SimpleNamespace(db=leveling_db),
        )
        store = SimpleNamespace(
            guild_data=lambda guild_id: {
                "cash_emoji": "<:cash:100>",
                "gold_emoji": "<:gold:101>",
                "gold_rate": 600,
                "gold_rate_date": "2026-07-23",
                "gold_rate_history": [
                    {"date": "2026-07-22", "rate": 590},
                    {"date": "2026-07-23", "rate": 600},
                ],
                "users": {
                    "42": {
                        "cash": 150.5,
                        "gold": 2,
                        "safe_cash": 49.5,
                        "safe_gold": 1,
                        "treasure_maps": 3,
                        "owned_roles": ["miner"],
                    }
                }
            }
        )
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(bot=bot, economy_data=store))
        )

        response = await get_my_profile("100", request, SimpleNamespace(discord_id="42"))

        self.assertEqual(response["display_name"], "Arthur")
        self.assertEqual(response["cash"], 150.5)
        self.assertEqual(response["owned_roles"], ["miner"])
        self.assertEqual(response["emojis"]["cash"], "<:cash:100>")
        self.assertEqual(response["emojis"]["gold"], "<:gold:101>")
        self.assertEqual(response["total_cash"], 200)
        self.assertEqual(response["total_gold"], 3)
        self.assertEqual(response["wealth"], 2000)
        self.assertEqual(response["owned_role_details"][0]["name"], "Шахтёр")
        self.assertEqual(response["gold_rate_history"][-1]["rate"], 600)
        self.assertEqual(response["level"], 6)
        self.assertEqual(response["xp"], 1250)
        self.assertEqual(response["rank_position"], 4)

    def test_homepage_promotes_complete_player_profile(self):
        homepage = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        profile = (ROOT / "docs" / "profile.html").read_text(encoding="utf-8")

        self.assertIn('id="heroProfileCta"', homepage)
        self.assertIn("Открыть мой профиль", homepage)
        self.assertIn('id="mySafeCash"', profile)
        self.assertIn('id="myWealth"', profile)
        self.assertIn('id="myRoleList"', profile)
        self.assertIn('id="goldRateChart"', profile)
