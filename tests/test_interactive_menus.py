import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def registered_command_names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            for keyword in decorator.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    names.add(keyword.value.value)
    return names


class InteractiveMenuContracts(unittest.TestCase):
    def test_miner_load_is_not_blocked_by_another_extension(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        self.assertIn('"cogs.miner",', source)
        self.assertIn("for extension in extensions:", source)
        self.assertIn("logging.exception(\"Failed to load extension %s\", extension)", source)

    def test_balance_owns_roles_and_gang_creation(self):
        catalog = (ROOT / "cogs" / "catalog.py").read_text(encoding="utf-8")
        self.assertIn('label="Купить роли"', catalog)
        self.assertIn('label="Создать банду"', catalog)
        self.assertIn('label="Инвестиции"', catalog)
        self.assertIn('bot.tree.remove_command("roles")', catalog)

    def test_casino_is_a_replayable_menu(self):
        casino = (ROOT / "cogs" / "casino.py").read_text(encoding="utf-8")
        names = registered_command_names(ROOT / "cogs" / "casino.py")
        self.assertIn("casino", names)
        self.assertNotIn("blackjack", names)
        self.assertIn('label="Ещё раз с той же ставкой"', casino)
        self.assertIn('label="Новая ставка"', casino)
        self.assertIn("token = bot.set_economy_guild_id(interaction.guild_id)", casino)
        self.assertIn("bot.reset_economy_guild_id(token)", casino)
        self.assertIn("self.bot.set_economy_guild_id(self.guild_id)", casino)

    def test_help_uses_current_casino_and_mine_menus(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        help_source = source[
            source.index("def build_help_pages"):source.index(
                "class HelpCategorySelect"
            )
        ]
        self.assertIn("`/casino` — открыть казино", help_source)
        self.assertIn("`/mine` — открыть шахту (5 попыток в день)", help_source)
        self.assertIn("`/collector`", help_source)
        self.assertIn("`/admin-bank`", help_source)
        for removed_command in (
            "`/dice bet`",
            "`/poker bet`",
            "`/blackjack`",
            "`/mine-status`",
            "`/mine-buy`",
            "`/mine-sell`",
            "`/mine-smelt`",
            "`/mine-forge`",
        ):
            self.assertNotIn(removed_command, help_source)

    def test_investments_is_the_only_company_investment_command(self):
        names = registered_command_names(ROOT / "cogs" / "catalog.py")
        self.assertIn("investments", names)
        self.assertNotIn("companies", names)
        self.assertNotIn("invest", names)

    def test_company_level_up_is_sent_to_the_configured_news_channel(self):
        catalog = (ROOT / "cogs" / "catalog.py").read_text(encoding="utf-8")
        self.assertIn("async def send_company_level_up_announcement", catalog)
        self.assertIn('guild_data.get("news_channel_id")', catalog)
        self.assertIn("await channel.send(embed=embed)", catalog)
        self.assertIn("if new_level > old_level:", catalog)
        self.assertIn("await send_company_level_up_announcement(interaction, level_up)", catalog)

    def test_gold_exchange_is_owned_by_balance_menu(self):
        bot_commands = registered_command_names(ROOT / "bot.py")
        self.assertNotIn("gold-rate", bot_commands)
        self.assertNotIn("buy-gold", bot_commands)
        self.assertNotIn("sell-gold", bot_commands)

        catalog = (ROOT / "cogs" / "catalog.py").read_text(encoding="utf-8")
        self.assertIn("class GoldExchangeView", catalog)
        self.assertIn('label="Обмен золота"', catalog)
        self.assertIn("class InvestmentsView", catalog)

    def test_miner_buttons_use_shared_custom_emoji_constants(self):
        miner = (ROOT / "cogs" / "miner.py").read_text(encoding="utf-8")
        self.assertIn('label="Копать", emoji=EMOJI_MINE_DIG', miner)
        self.assertIn('label="Купить", emoji=EMOJI_MINE_BUY', miner)
        self.assertIn('label="Кузнец", emoji=EMOJI_MINE_SMELT', miner)
        self.assertIn('label="Ювелир", emoji=EMOJI_MINE_FORGE', miner)

    def test_mine_acknowledges_interaction_before_database_work(self):
        miner = (ROOT / "cogs" / "miner.py").read_text(encoding="utf-8")
        command = miner[miner.index("async def mine_cmd"):]
        self.assertLess(
            command.index("await interaction.response.defer"),
            command.index("self.db.get_player"),
        )
        self.assertIn("await interaction.edit_original_response", command)

    def test_mine_database_connection_is_lazy(self):
        source = (ROOT / "src" / "mine_logic.py").read_text(encoding="utf-8")
        start = source.index("def __init__(self, db_url")
        constructor = source[start:source.index("@staticmethod", start)]
        self.assertNotIn("psycopg2.connect", constructor)

    def test_message_handler_applies_configured_auto_reactions(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")
        handler = source[source.index("async def on_message(message):"):]
        self.assertIn("matching_reaction_emojis", handler)
        self.assertIn('economy_data.get("auto_reactions", [])', handler)
        self.assertIn('message.content or ""', handler)
        self.assertIn("await message.add_reaction", handler)

    def test_bounty_leaderboard_lives_inside_bounty_menu(self):
        bounty_path = ROOT / "cogs" / "bounty.py"
        names = registered_command_names(bounty_path)
        source = bounty_path.read_text(encoding="utf-8")
        self.assertIn("bounty", names)
        self.assertNotIn("bounty-leaderboard", names)
        self.assertIn("class BountyLeaderboardButton", source)
        self.assertIn("has_usable_ammo(account, CATALOG_ITEMS)", source)

    def test_weapon_menu_acknowledges_buttons_before_database_work(self):
        catalog = (ROOT / "cogs" / "catalog.py").read_text(encoding="utf-8")
        self.assertIn("async def take_button", catalog)
        self.assertIn("await interaction.response.defer()", catalog)
        self.assertIn("await interaction.edit_original_response", catalog)
        self.assertIn("Weapon menu failed", catalog)


if __name__ == "__main__":
    unittest.main()
