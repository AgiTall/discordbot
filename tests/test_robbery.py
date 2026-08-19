from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RobberyResponseContractTests(unittest.TestCase):
    def test_command_is_deferred_before_remote_economy_work(self):
        source = (ROOT / "cogs" / "robbery.py").read_text(encoding="utf-8")
        command_start = source.index("async def rob_command")
        defer_at = source.index("await interaction.response.defer", command_start)
        lock_at = source.index("async with economy_lock", command_start)

        self.assertLess(defer_at, lock_at)
        self.assertIn("await interaction.edit_original_response", source[lock_at:])

    def test_result_replaces_deferred_response_and_shows_amount(self):
        source = (ROOT / "cogs" / "robbery.py").read_text(encoding="utf-8")
        command = source[source.index("async def rob_command"):]

        self.assertNotIn("interaction.followup.send", command)
        self.assertNotIn("interaction.delete_original_response", command)
        self.assertIn("format_money_plain(stolen_amount)", command)
        self.assertIn("format_money_plain(fine_amount)", command)

    def test_dealer_commands_acknowledge_before_economy_work(self):
        source = (ROOT / "bot.py").read_text(encoding="utf-8")

        for command_name in ("dealer_command", "dealer_delivery_command"):
            command = source[source.index(f"async def {command_name}"):]
            self.assertLess(
                command.index("await interaction.response.defer"),
                command.index("async with economy_lock"),
            )

        loading_helper = source[
            source.index("async def send_loading_then_edit"):
            source.index("_original_interaction_send_message")
        ]
        self.assertIn("await interaction.edit_original_response", loading_helper)
        self.assertNotIn("await interaction.followup.send", loading_helper)


if __name__ == "__main__":
    unittest.main()
