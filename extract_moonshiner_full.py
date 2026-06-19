
import ast

with open("bot.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

moonshine_nodes = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.ClassDef):
        if "moonshine" in node.name.lower() or "moonshiner" in node.name.lower():
            moonshine_nodes.append(node)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and ("moonshine" in target.id.lower() or "moonshiner" in target.id.lower()):
                moonshine_nodes.append(node)
                break

lines = source.split("\n")

extracted_lines = []
nodes_to_remove = []

for node in moonshine_nodes:
    # Need to include decorators for functions/classes
    start_lineno = node.lineno
    if hasattr(node, "decorator_list") and node.decorator_list:
        start_lineno = node.decorator_list[0].lineno
    end_lineno = node.end_lineno
    
    extracted_lines.extend(lines[start_lineno - 1:end_lineno])
    extracted_lines.append("")
    extracted_lines.append("")
    nodes_to_remove.append((start_lineno - 1, end_lineno))

nodes_to_remove = sorted(nodes_to_remove, key=lambda x: x[0])

# Merge overlapping or contiguous regions if any
merged_remove = []
for s, e in nodes_to_remove:
    if not merged_remove:
        merged_remove.append([s, e])
    else:
        last_s, last_e = merged_remove[-1]
        if s <= last_e:
            merged_remove[-1][1] = max(last_e, e)
        else:
            merged_remove.append([s, e])

new_bot_lines = []
for i, line in enumerate(lines):
    in_remove = False
    for s, e in merged_remove:
        if s <= i < e:
            in_remove = True
            break
    if not in_remove:
        new_bot_lines.append(line)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write("\n".join(new_bot_lines))

# We need to construct cogs/moonshiner.py properly
with open("cogs/moonshiner.py", "w", encoding="utf-8") as f:
    f.write("import discord\n")
    f.write("from discord.ext import commands\n")
    f.write("from discord import app_commands\n")
    f.write("import random\n")
    f.write("import time\n")
    f.write("import math\n\n")
    
    f.write("class MoonshinerCog(commands.Cog):\n")
    f.write("    def __init__(self, bot):\n")
    f.write("        self.bot = bot\n\n")
    f.write("    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):\n")
    f.write("        import traceback\n")
    f.write("        print(f\"Moonshiner Cog error: {error}\")\n")
    f.write("        traceback.print_exception(type(error), error, error.__traceback__)\n")
    f.write("        if not interaction.response.is_done():\n")
    f.write("            await interaction.response.send_message(f\"Произошла ошибка: {error}\", ephemeral=True)\n\n")

    f.write("\n".join(extracted_lines))
    
    f.write("\nasync def setup(bot):\n")
    f.write("    await bot.add_cog(MoonshinerCog(bot))\n")

print("Full extraction completed!")

