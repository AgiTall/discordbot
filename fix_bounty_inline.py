
import re

with open("cogs/bounty.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("def __init__(self, bot, difficulty_key):        self.bot = bot", "def __init__(self, bot, difficulty_key):\n        self.bot = bot")
text = text.replace("def __init__(self, bot, tactic_key):        self.bot = bot", "def __init__(self, bot, tactic_key):\n        self.bot = bot")

with open("cogs/bounty.py", "w", encoding="utf-8") as f:
    f.write(text)

