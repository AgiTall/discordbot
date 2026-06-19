import re

with open("bot.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Remove DEPOSIT_DAILY_RATE
text = re.sub(r"DEPOSIT_DAILY_RATE\s*=\s*0\.03\n?", "", text)

# 2. In get_account, add migration
text = re.sub(r"(def get_account\(user_id\):.*?)(    return account)", r'\1    if "deposit" in account and account["deposit"] > 0:\n        account["cash"] += account["deposit"]\n        account["deposit"] = 0.0\n\2', text, flags=re.DOTALL)

# 3. Remove accrue_deposit_interest definition
text = re.sub(r"def accrue_deposit_interest\(account\):.*?return new_deposit - deposit\n", "", text, flags=re.DOTALL)

# 4. Remove accrue_deposit_interest calls
text = re.sub(r"\s*interest\s*=\s*accrue_deposit_interest\(account\)\n", "\n", text)
text = re.sub(r"\s*accrue_deposit_interest\(account\)\n", "\n", text)
text = re.sub(r"\s*bot\.accrue_deposit_interest\s*=\s*accrue_deposit_interest\n", "\n", text)

# 5. Remove /deposit and /withdraw and /set-deposit commands
text = re.sub(r"@bot\.tree\.command\(name=\"deposit\",.*?async def deposit_command\(.*?await send_embed_response\(message, color=discord\.Color\.blue\(\)\)\n", "", text, flags=re.DOTALL)
text = re.sub(r"@bot\.tree\.command\(name=\"withdraw\",.*?async def withdraw_deposit_command\(.*?await send_embed_response\(message, color=discord\.Color\.green\(\)\)\n", "", text, flags=re.DOTALL)
text = re.sub(r"@bot\.tree\.command\(name=\"set-deposit\",.*?async def set_deposit_command\(.*?await interaction\.response\.send_message\(message, ephemeral=True\)\n", "", text, flags=re.DOTALL)

# 6. Remove help menu references to deposit
text = re.sub(r"\s*\"`/deposit amount` — положить деньги на вклад\.\\n\".*?\"`/withdraw amount` — снять деньги со вклада\.\\n\"", "", text, flags=re.DOTALL)
text = re.sub(r"\s*f\"Вклад растёт на \*\*\{format_number\(DEPOSIT_DAILY_RATE \* 100\)\}% в день\*\*\.\\n\"", "", text)
text = re.sub(r"\s*\"`/set-deposit member amount` — установить вклад\.\"\n", "\n", text)
text = re.sub(r"\s*\"deposit\",\n", "\n", text)
text = re.sub(r"\s*\"withdraw\",\n", "\n", text)
text = re.sub(r"\s*\"set-deposit\",\n", "\n", text)

# 7. Update profile / balance view
text = re.sub(r"\s*deposit\s*=\s*account\[\"deposit\"\]\n", "\n", text)
text = re.sub(r"\s*f\"├─ \{get_investment_emoji\(\)\} Вклад: \{format_money_plain\(deposit\)\}\\n\"", "", text)
text = re.sub(r"        f\"Вклад: \*\*\{format_money\(account\['deposit'\]\)\}\*\*\\n\"", "", text)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Done")
