import ast
import logging
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load_balance_functions():
    source = Path(__file__).parents[1].joinpath("bot.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        "format_balance_role_sections",
        "format_balance_miner_status",
        "format_balance_gang_section",
        "format_balance_property_section",
        "format_balance_weapon_section",
    }
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    namespace = {"logging": logging}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), "bot.py", "exec"), namespace)
    return namespace


class _EconomyData:
    def __init__(self, guild_data):
        self.guild_data = guild_data

    def get(self, key, default=None):
        return default

    def current(self):
        return self.guild_data


class BalanceProfileTests(unittest.TestCase):
    def setUp(self):
        self.ns = _load_balance_functions()
        self.ns.update(
            {
                "DEALER_ROLE_KEY": "trader",
                "MOONSHINER_ROLE_KEY": "moonshiner",
                "BOUNTY_ROLE_KEY": "bounty_hunter",
                "NATURALIST_ROLE_KEY": "naturalist",
                "DEFAULT_BALANCE_GANG_EMOJI": "🏴‍☠️",
                "ROLE_OWNED_PIN_EMOJI": "<:grenpin:1527602575463944232>",
                "find_guild_role": lambda guild, definition: None,
                "get_role_icon": lambda definition, role: definition.get("emoji", ""),
                "get_lock_emoji": lambda: "🔒",
                "format_progress_percent": lambda value: f"{value:.0f}%",
                "get_role_price": lambda role: 20,
                "format_role_price": lambda value: f"{value:.0f} G",
                "format_integer": lambda value: str(value),
                "format_money_plain": lambda value: f"{value:.2f}",
                "format_gold_plain": lambda value: f"{value:.2f}",
                "get_cash_emoji": lambda: "$",
                "get_gold_emoji": lambda: "G",
                "format_collection_showcase": lambda account: "пока пусто",
                "has_game_role": lambda member, key, account: key in account.get("owned_roles", []),
            }
        )

    def test_all_unowned_professions_remain_visible_as_locked(self):
        self.ns["ROLE_DEFINITIONS"] = [
            {"key": "trader", "name": "Торговец", "emoji": "🛒", "available": True},
            {"key": "moonshiner", "name": "Самогонщик", "emoji": "🥃", "available": True},
            {"key": "miner", "name": "Шахтёр", "emoji": "⛏️", "available": True},
            {"key": "collector", "name": "Коллекционер", "emoji": "🖼️", "available": False},
        ]

        text = self.ns["format_balance_role_sections"](
            SimpleNamespace(), SimpleNamespace(id=42), {"owned_roles": []}
        )

        for name in ("Торговец", "Самогонщик", "Шахтёр", "Коллекционер"):
            self.assertIn(name, text)
        self.assertEqual(text.count("🔒"), 4)
        self.assertIn("не куплено", text)
        self.assertIn("20 G · `/roles`", text)
        self.assertIn("пока недоступно на сервере", text)

    def test_active_weapons_are_visible_with_custom_emojis(self):
        account = {
            "inventory": {"revolver_cattleman": 1, "rifle_boltaction": 1},
            "weapon_loadout": {
                "sidearms": ["revolver_cattleman"],
                "longarms": ["rifle_boltaction"],
            },
            "weapon_condition": {
                "revolver_cattleman": 87.5,
                "rifle_boltaction": 100,
            },
            "ammo": {
                "revolver": {"normal": 44},
                "rifle": {"normal": 34},
            },
            "selected_ammo": {"revolver": "normal", "rifle": "normal"},
        }
        text = self.ns["format_balance_weapon_section"](account)
        self.assertIn("Револьвер Cattleman", text)
        self.assertIn("Болтовая винтовка", text)
        self.assertIn("87.5%", text)
        self.assertIn("<:gun:1527598299501035660>", text)
        self.assertIn("<:bullet_normal:1527591453784670308> **44/200**", text)
        self.assertIn("<:bullet_normal:1527591453784670308> **34/100**", text)

    def test_role_stats_are_on_an_indented_second_line(self):
        self.ns["ROLE_DEFINITIONS"] = [
            {"key": "trader", "name": "Торговец", "emoji": "🛒", "available": True},
        ]
        text = self.ns["format_balance_role_sections"](
            SimpleNamespace(),
            SimpleNamespace(id=42),
            {"owned_roles": ["trader"], "dealer_wagon": 25},
        )
        self.assertIn("└─ <:grenpin:1527602575463944232> 🛒 **Торговец**", text)
        self.assertIn("\n   └─ повозка", text)

    def test_gang_section_is_visible_without_membership(self):
        self.ns["economy_data"] = _EconomyData({"gangs": {}})

        text = self.ns["format_balance_gang_section"](
            SimpleNamespace(id=42), {"gang_name": None}
        )

        self.assertIn("Банда", text)
        self.assertIn("Вы не состоите", text)
        self.assertIn("/gang-create", text)

    def test_gang_section_shows_progress_and_treasury(self):
        self.ns["economy_data"] = _EconomyData(
            {
                "gangs": {
                    "Armadillo": {
                        "id": 7,
                        "leader": 42,
                        "members": [42, 43],
                        "cash": 1250,
                        "gold": 3,
                        "level": 2,
                        "influence": 8,
                        "leader_role_name": "Шериф",
                    }
                }
            }
        )

        text = self.ns["format_balance_gang_section"](
            SimpleNamespace(id=42), {"gang_name": "Armadillo"}
        )

        self.assertIn("Armadillo", text)
        self.assertIn("Шериф", text)
        self.assertIn("Участников: **2**", text)
        self.assertIn("1250.00", text)


if __name__ == "__main__":
    unittest.main()
