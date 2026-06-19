
with open("cogs/bounty.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("    self.bot = bot"):
        new_lines.append("        self.bot = bot\n")
    elif "set_economy_guild_id(interaction.guild_id)" in line:
        new_lines.append(line.replace("set_economy_guild_id(", "self.bot.set_economy_guild_id("))
    else:
        new_lines.append(line)

with open("cogs/bounty.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

