
with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "await bot.load_extension(\"cogs.casino\")" in line:
        new_lines.append("        await bot.load_extension(\"cogs.moonshiner\")\n")

with open("bot.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Added cogs.moonshiner")

