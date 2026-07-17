import ast
import unittest
from pathlib import Path
from types import SimpleNamespace


def _load_formatter():
    source = Path(__file__).parents[1].joinpath("bot.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    definition = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "format_emoji_export"
    )
    namespace = {}
    exec(compile(ast.Module(body=[definition], type_ignores=[]), "bot.py", "exec"), namespace)
    return namespace["format_emoji_export"]


class EmojiExportTests(unittest.TestCase):
    def test_exports_static_and_animated_markup(self):
        formatter = _load_formatter()
        text = formatter(
            [
                SimpleNamespace(name="shovel", id=1518547808012079114, animated=False),
                SimpleNamespace(name="dance", id=42, animated=True),
            ],
            [SimpleNamespace(name="collector", id=99, animated=False)],
        )
        self.assertIn("shovel\t1518547808012079114\t<:shovel:1518547808012079114>", text)
        self.assertIn("dance\t42\t<a:dance:42>", text)
        self.assertIn("ЭМОДЗИ ПРИЛОЖЕНИЯ (1)", text)


if __name__ == "__main__":
    unittest.main()
