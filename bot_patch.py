
import os

with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "bot = commands.Bot(command_prefix=\"!\", intents=intents)" in line:
        insert_idx = i + 1
        lines.insert(insert_idx, "bot.set_economy_guild_id = set_economy_guild_id\n")
        lines.insert(insert_idx + 1, "bot.validate_bet = validate_bet\n")
        lines.insert(insert_idx + 2, "bot.economy_lock = economy_lock\n")
        lines.insert(insert_idx + 3, "bot.get_account = get_account\n")
        lines.insert(insert_idx + 4, "bot.save_economy = save_economy\n")
        lines.insert(insert_idx + 5, "bot.format_money = format_money\n")
        lines.insert(insert_idx + 6, "bot.accrue_deposit_interest = accrue_deposit_interest\n")
        break

for i, line in enumerate(lines):
    if "await bot.add_cog(leveling.LevelingCog(bot))" in line:
        insert_idx = i + 1
        lines.insert(insert_idx, "        await bot.load_extension(\"cogs.casino\")\n")
        break

with open("bot.py", "w", encoding="utf-8") as f:
    f.writelines(lines)
print("bot.py patched.")

