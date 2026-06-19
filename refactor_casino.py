
import os

with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

def get_block(start_idx):
    indent = None
    for i in range(start_idx, len(lines)):
        if ("def " in lines[i] or "class " in lines[i]) and indent is None:
            indent = len(lines[i]) - len(lines[i].lstrip())
            continue
        
        if indent is not None and lines[i].strip():
            curr_indent = len(lines[i]) - len(lines[i].lstrip())
            if curr_indent <= indent:
                return start_idx, i
    return start_idx, len(lines)

def find_block(pattern):
    for i, line in enumerate(lines):
        if pattern in line:
            return get_block(i)
    return None, None

build_deck_s, build_deck_e = find_block("def build_card_deck()")
card_val_s, card_val_e = find_block("def blackjack_card_value")
hand_val_s, hand_val_e = find_block("def blackjack_hand_value")
view_s, view_e = find_block("class BlackjackView")
cmd_s, cmd_e = find_block("@bot.tree.command(name=\"blackjack\"")

blocks_to_remove = [
    (build_deck_s, build_deck_e),
    (card_val_s, card_val_e),
    (hand_val_s, hand_val_e),
    (view_s, view_e),
    (cmd_s, cmd_e)
]

os.makedirs("cogs", exist_ok=True)
with open("cogs/casino.py", "w", encoding="utf-8") as out:
    out.write("import discord\n")
    out.write("import random\n")
    out.write("import asyncio\n")
    out.write("from discord.ext import commands\n")
    out.write("from discord import app_commands\n\n")
    
    for s, e in blocks_to_remove[:3]:
        out.write("".join(lines[s:e]))
        out.write("\n")
        
    view_lines = lines[view_s:view_e]
    for line in view_lines:
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
        out.write(line)
    out.write("\n")
        
    out.write("class CasinoCog(commands.Cog):\n")
    out.write("    def __init__(self, bot):\n")
    out.write("        self.bot = bot\n\n")
    
    cmd_lines = lines[cmd_s:cmd_e]
    for line in cmd_lines:
        if "@bot.tree.command" in line:
            line = line.replace("@bot.tree.command", "@app_commands.command")
        if "async def blackjack_command(interaction" in line:
            line = line.replace("interaction", "self, interaction")
            
        line = line.replace("validate_bet(", "self.bot.validate_bet(")
        line = line.replace("economy_lock", "self.bot.economy_lock")
        line = line.replace("get_account(", "self.bot.get_account(")
        line = line.replace("accrue_deposit_interest(", "self.bot.accrue_deposit_interest(")
        line = line.replace("save_economy(", "self.bot.save_economy(")
        line = line.replace("format_money(", "self.bot.format_money(")
        line = line.replace("BlackjackView(interaction", "BlackjackView(self.bot, interaction")
        
        out.write("    " + line)
        
    out.write("\nasync def setup(bot):\n")
    out.write("    await bot.add_cog(CasinoCog(bot))\n")

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
print("Extracted successfully.")

