
import os

with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def get_block(start_idx):
    indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    for i in range(start_idx + 1, len(lines)):
        if lines[i].strip() == "":
            continue
        curr_indent = len(lines[i]) - len(lines[i].lstrip())
        if curr_indent <= indent:
            return start_idx, i
    return start_idx, len(lines)

blocks_to_remove = []

def find_block_start(pattern):
    for i, line in enumerate(lines):
        if pattern in line:
            return i
    return None

targets = [
    "def moonshine_text_key",
    "class MoonshineOwnerView",
    "class MoonshineMashSelect",
    "class MoonshineMashView",
    "class MoonshineSpecialSelect",
    "class MoonshineSpecialView",
    "class MoonshineUpgradeView",
    "class MoonshineMainView"
]

for t in targets:
    s = find_block_start(t)
    if s is not None:
        s, e = get_block(s)
        blocks_to_remove.append((s, e))

# Command and autocomplete
ac_idx = find_block_start("async def moonshine_ingredient_autocomplete")
cmd_idx = find_block_start("@bot.tree.command(name=\"moonshine\"")

if ac_idx is not None:
    s, e = get_block(ac_idx - 1) # to include decorator
    blocks_to_remove.append((s, e))
    
if cmd_idx is not None:
    # find end of command
    indent = None
    for j in range(cmd_idx, len(lines)):
        if "async def " in lines[j] and indent is None:
            indent = len(lines[j]) - len(lines[j].lstrip())
            continue
        if indent is not None and lines[j].strip():
            curr_indent = len(lines[j]) - len(lines[j].lstrip())
            if curr_indent <= indent and ("def " in lines[j] or "class " in lines[j] or "@" in lines[j][:4]):
                blocks_to_remove.append((cmd_idx, j))
                break

blocks_to_remove = sorted(blocks_to_remove, key=lambda x: x[0])

with open("cogs/moonshiner.py", "w", encoding="utf-8") as out:
    out.write("import discord\n")
    out.write("import time\n")
    out.write("from discord.ext import commands\n")
    out.write("from discord import app_commands\n\n")

    # Constants needed
    out.write("MOONSHINE_IMAGE_FILE = \"assets/images/moonshine.png\"\n")
    out.write("MOONSHINE_IMAGE_ATTACHMENT_NAME = \"moonshine.png\"\n")
    out.write("DEFAULT_MOONSHINE_STAR_EMOJIS = \"⭐\"\n")
    out.write("DEFAULT_MOONSHINE_SPECIAL_EMOJI = \"🌟\"\n")
    out.write("DEFAULT_MOONSHINE_CONDENSER_EMOJI = \"🔥\"\n")
    out.write("DEFAULT_MOONSHINE_DISTILLER_EMOJI = \"⚗️\"\n")
    out.write("DEFAULT_MOONSHINE_BUTTON_EMOJIS = \"🍾\"\n")
    out.write("MOONSHINE_BUY_PRICES = {\"moonshiner_base\": 20.0, \"moonshiner_special\": 40.0, \"moonshiner_condenser\": 25.0, \"moonshiner_distiller\": 35.0}\n")
    out.write("MOONSHINE_RECIPES = {\"Слабая брага\": {\"ingredients\": [\"Кукуруза\", \"Сахар\"], \"quality\": 1, \"base_price\": 10.0, \"time\": 10}, \"Крепкий самогон\": {\"ingredients\": [\"Кукуруза\", \"Сахар\", \"Дрожжи\"], \"quality\": 2, \"base_price\": 25.0, \"time\": 20}, \"Первоклассный напиток\": {\"ingredients\": [\"Ячмень\", \"Рожь\", \"Дрожжи\", \"Чистая вода\"], \"quality\": 3, \"base_price\": 50.0, \"time\": 30}}\n")
    out.write("MOONSHINE_INGREDIENTS = [\"Кукуруза\", \"Сахар\", \"Дрожжи\", \"Ячмень\", \"Рожь\", \"Чистая вода\"]\n\n")

    for s, e in blocks_to_remove[:-2]:
        for line in lines[s:e]:
            # Replace globals
            if "def __init__(self, user_id" in line:
                line = line.replace("def __init__(self, user_id", "def __init__(self, bot, user_id")
            elif "super().__init__(" in line:
                out.write(line)
                out.write("        self.bot = bot\n")
                continue
            line = line.replace("economy_lock", "self.bot.economy_lock")
            line = line.replace("get_account(", "self.bot.get_account(")
            line = line.replace("save_economy(", "self.bot.save_economy(")
            line = line.replace("format_money(", "self.bot.format_money(")
            line = line.replace("MoonshineOwnerView(interaction.user.id)", "MoonshineOwnerView(self.bot, interaction.user.id)")
            line = line.replace("MoonshineOwnerView(self.user_id)", "MoonshineOwnerView(self.bot, self.user_id)")
            out.write(line)
        out.write("\n")

    out.write("class MoonshinerCog(commands.Cog):\n")
    out.write("    def __init__(self, bot):\n")
    out.write("        self.bot = bot\n\n")
    
    # Error handler
    out.write("    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):\n")
    out.write("        import traceback\n")
    out.write("        print(f\"Moonshiner Cog error: {error}\")\n")
    out.write("        traceback.print_exception(type(error), error, error.__traceback__)\n")
    out.write("        if not interaction.response.is_done():\n")
    out.write("            await interaction.response.send_message(f\"Произошла ошибка: {error}\", ephemeral=True)\n\n")

    # The command and autocomplete
    for s, e in blocks_to_remove[-2:]:
        for line in lines[s:e]:
            if "@bot.tree.command" in line:
                line = line.replace("@bot.tree.command", "@app_commands.command")
            if "async def moonshine_command(interaction" in line:
                line = line.replace("interaction", "self, interaction")
            if "async def moonshine_ingredient_autocomplete(interaction" in line:
                line = line.replace("interaction", "self, interaction")
            
            line = line.replace("get_account(", "self.bot.get_account(")
            line = line.replace("MoonshineMainView(interaction.user.id", "MoonshineMainView(self.bot, interaction.user.id")
            
            out.write("    " + line)
            
    out.write("\nasync def setup(bot):\n")
    out.write("    await bot.add_cog(MoonshinerCog(bot))\n")

new_lines = []
for i, line in enumerate(lines):
    in_block = False
    for s, e in blocks_to_remove:
        if s <= i < e:
            in_block = True
            break
    if not in_block:
        new_lines.append(line)

with open("bot.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Extracted Moonshiner.")

