
import ast
import re

with open("bot.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

logic_nodes = []
cmd_nodes = []

for node in tree.body:
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.ClassDef):
        name = node.name.lower()
        if "bounty" in name:
            if name.endswith("_command") or isinstance(node, ast.ClassDef) and "view" in name or isinstance(node, ast.ClassDef) and "button" in name:
                cmd_nodes.append(node)
            else:
                logic_nodes.append(node)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and "bounty" in target.id.lower():
                logic_nodes.append(node)
                break

lines = source.split("\n")

def get_node_lines(node):
    start = node.lineno
    if hasattr(node, "decorator_list") and node.decorator_list:
        start = node.decorator_list[0].lineno
    return start - 1, node.end_lineno

logic_remove = []
logic_lines = []
for node in logic_nodes:
    s, e = get_node_lines(node)
    logic_remove.append((s, e))
    logic_lines.extend(lines[s:e])
    logic_lines.append("")
    logic_lines.append("")

cmd_remove = []
cmd_lines = []
for node in cmd_nodes:
    s, e = get_node_lines(node)
    cmd_remove.append((s, e))
    chunk = lines[s:e]
    # Patch command dependencies
    new_chunk = []
    for line in chunk:
        if "def __init__(self, user_id" in line:
            line = line.replace("def __init__(self, user_id", "def __init__(self, bot, user_id")
        elif "def __init__(self, difficulty_key):" in line:
            line = line.replace("def __init__(self, difficulty_key):", "def __init__(self, bot, difficulty_key):")
            line = line + "        self.bot = bot\n"
        elif "def __init__(self, tactic_key):" in line:
            line = line.replace("def __init__(self, tactic_key):", "def __init__(self, bot, tactic_key):")
            line = line + "        self.bot = bot\n"
        elif "def __init__(self, user_id, difficulty_key, target_name):" in line:
            line = line.replace("def __init__(self, user_id", "def __init__(self, bot, user_id")
        
        # Patch init calls
        line = line.replace("BountyMainView(interaction.user.id)", "BountyMainView(self.bot, interaction.user.id)")
        line = line.replace("BountyOwnerView(user_id)", "BountyOwnerView(self.bot, user_id)")
        line = line.replace("super().__init__(user_id)", "super().__init__(bot, user_id)")
        line = line.replace("BountyDifficultyButton(difficulty_key)", "BountyDifficultyButton(self.bot, difficulty_key)")
        line = line.replace("BountyTacticButton(tactic_key)", "BountyTacticButton(self.bot, tactic_key)")
        line = line.replace("BountyTacticView(interaction.user.id", "BountyTacticView(self.bot, interaction.user.id")
        line = line.replace("BountyTacticView(user_id", "BountyTacticView(self.bot, user_id")

        # Patch globals
        line = line.replace("economy_lock", "self.bot.economy_lock")
        line = line.replace("get_account(", "self.bot.get_account(")
        line = line.replace("save_economy(", "self.bot.save_economy(")
        line = line.replace("format_money(", "self.bot.format_money(")
        line = line.replace("add_xp(", "self.bot.add_xp(")
        
        # Commands to Cog
        if "@bot.tree.command" in line:
            line = line.replace("@bot.tree.command", "@app_commands.command")
        if "async def bounty_command(interaction" in line:
            line = line.replace("interaction", "self, interaction")
        if "async def bounty_leaderboard_command(interaction" in line:
            line = line.replace("interaction", "self, interaction")

        new_chunk.append(line)
    
    # Custom fix for super().__init__ in OwnerView
    fixed_chunk = []
    for line in new_chunk:
        fixed_chunk.append(line)
        if "def __init__(self, bot, user_id, timeout=600):" in line:
            fixed_chunk.append(line.replace("def __init__(self, bot, user_id, timeout=600):", "self.bot = bot"))
            
    cmd_lines.extend(fixed_chunk)
    cmd_lines.append("")
    cmd_lines.append("")

all_remove = sorted(logic_remove + cmd_remove, key=lambda x: x[0])
merged_remove = []
for s, e in all_remove:
    if not merged_remove:
        merged_remove.append([s, e])
    else:
        last_s, last_e = merged_remove[-1]
        if s <= last_e + 1:
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
        
# Add logic import to bot.py
for i, line in enumerate(new_bot_lines):
    if "import discord" in line:
        new_bot_lines.insert(i + 1, "from src.bounty_logic import *\n")
        break

with open("bot.py", "w", encoding="utf-8") as f:
    f.write("\n".join(new_bot_lines))

with open("src/bounty_logic.py", "w", encoding="utf-8") as f:
    f.write("import time\nimport math\nimport random\nimport json\nimport discord\nfrom discord import app_commands\n\n")
    f.write("\n".join(logic_lines))

with open("cogs/bounty.py", "w", encoding="utf-8") as f:
    f.write("import discord\nfrom discord.ext import commands\nfrom discord import app_commands\nimport random\nfrom src.bounty_logic import *\n\n")
    f.write("\n".join(cmd_lines))
    f.write("\nclass BountyCog(commands.Cog):\n")
    f.write("    def __init__(self, bot):\n")
    f.write("        self.bot = bot\n\n")
    f.write("    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):\n")
    f.write("        import traceback\n")
    f.write("        print(f\"Bounty Cog error: {error}\")\n")
    f.write("        traceback.print_exception(type(error), error, error.__traceback__)\n")
    f.write("        if not interaction.response.is_done():\n")
    f.write("            await interaction.response.send_message(f\"Произошла ошибка: {error}\", ephemeral=True)\n\n")
    f.write("\nasync def setup(bot):\n")
    f.write("    await bot.add_cog(BountyCog(bot))\n")

print("Extracted Bounty Hunter")

