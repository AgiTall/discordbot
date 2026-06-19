
import re

# 1. Fix cogs/naturalist.py indentation
with open("cogs/naturalist.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix inline replacements
text = re.sub(r"def __init__\(([^)]+)\):        self\.bot = bot", r"def __init__(\1):\n        self.bot = bot", text)

# Fix standalone replacements
lines = text.split("\n")
new_lines = []
for line in lines:
    if line.startswith("    self.bot = bot"):
        new_lines.append("        self.bot = bot")
    elif "set_economy_guild_id(interaction.guild_id)" in line:
        new_lines.append(line.replace("set_economy_guild_id(", "self.bot.set_economy_guild_id("))
    else:
        new_lines.append(line)

with open("cogs/naturalist.py", "w", encoding="utf-8") as f:
    f.write("\n".join(new_lines))

# 2. Fix bot.py imports
with open("bot.py", "r", encoding="utf-8") as f:
    bot_lines = f.readlines()

new_bot_lines = []
for line in bot_lines:
    if "from src.naturalist_logic import *\n" == line:
        continue
    new_bot_lines.append(line)

new_bot_lines.insert(0, "from src.naturalist_logic import *\n")

# 3. Patch setup hook
final_bot_lines = []
for line in new_bot_lines:
    final_bot_lines.append(line)
    if "await bot.load_extension(\"cogs.bounty\")" in line:
        final_bot_lines.append("        await bot.load_extension(\"cogs.naturalist\")\n")

with open("bot.py", "w", encoding="utf-8") as f:
    f.writelines(final_bot_lines)

print("Fixed Naturalist issues.")

