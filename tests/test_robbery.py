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
        self.assertIn("await interaction.followup.send", source[lock_at:])


if __name__ == "__main__":
    unittest.main()
