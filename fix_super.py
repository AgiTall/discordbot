
with open("cogs/moonshiner.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "self.bot = bot" in line and "    self.bot = bot" not in line and "class " not in line:
        pass # remove the incorrectly indented one
    else:
        new_lines.append(line)

# Now we need to insert `self.bot = bot` at the START of `def __init__(self, bot, ...):` for classes that need it.
final_lines = []
for line in new_lines:
    final_lines.append(line)
    if "def __init__(self, bot" in line:
        # get indent
        indent = len(line) - len(line.lstrip())
        final_lines.append(" " * (indent + 4) + "self.bot = bot\n")

with open("cogs/moonshiner.py", "w", encoding="utf-8") as f:
    f.writelines(final_lines)
print("fixed")

