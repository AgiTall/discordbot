
with open("bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "bot.set_economy_guild_id = set_economy_guild_id" in line:
        skip = True
    if skip and "async def setup_hook():" in line:
        skip = False
        new_lines.append(line)
        new_lines.append("    bot.set_economy_guild_id = set_economy_guild_id\n")
        new_lines.append("    bot.validate_bet = validate_bet\n")
        new_lines.append("    bot.economy_lock = economy_lock\n")
        new_lines.append("    bot.get_account = get_account\n")
        new_lines.append("    bot.save_economy = save_economy\n")
        new_lines.append("    bot.format_money = format_money\n")
        new_lines.append("    bot.accrue_deposit_interest = accrue_deposit_interest\n")
        continue
        
    if not skip:
        new_lines.append(line)

with open("bot.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("bot.py fixed")

