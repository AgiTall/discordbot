
with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "import discord" in line:
        lines.insert(i + 1, "from src.moonshiner_logic import *\n")
        break

with open("bot.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

