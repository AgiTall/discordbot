
with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "from src.bounty_logic import *\n" == line:
        continue
    new_lines.append(line)

new_lines.insert(0, "from src.bounty_logic import *\n")

with open("bot.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

