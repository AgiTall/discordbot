import re

with open("bot.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix build_balance_embed definition
old_def = "def build_balance_embed(guild, member, account, rate, interest=0.0):"
new_def = "def build_balance_embed(guild, member, account, rate):"
text = text.replace(old_def, new_def)

# Update build_balance_embed content to show safe if present
old_bank = """        "🏦 Банк\\n"
        f"├─ Доход: +{format_money_plain(interest)}\\n"
        f"└─ Курс: 1 {get_gold_emoji()} = {format_exchange_rate(rate)}\\n\\n"
        "🔒 Недоступные роли\\n"
        f"{unavailable_role_sections}"""
new_bank = """        "🏦 Экономика\\n"
        f"├─ Курс: 1 {get_gold_emoji()} = {format_exchange_rate(rate)}\\n\\n"
        "🔒 Недоступные роли\\n"
        f"{unavailable_role_sections}"""

# Sometimes the string formatting can be tricky, let's use regex
text = re.sub(
    r"\"🏦 Банк\\n\".*?f\"\{unavailable_role_sections\}\"",
    new_bank,
    text,
    flags=re.DOTALL
)

# Add Safe to finances
text = re.sub(
    r"(├─ \{get_cash_emoji\(\)\} Деньги: \{format_money_plain\(cash\)\}\\n\")",
    r"\1\n          f\"├─ 🧰 Сейф (Деньги): {format_money_plain(account.get('safe_cash', 0.0))}\\n\"\n          f\"├─ 🧰 Сейф (Золото): {format_number(account.get('safe_gold', 0.0))} золота\\n\"",
    text
)

# Fix balance_command calls
text = text.replace(
    "embed = build_balance_embed(interaction.guild, interaction.user, account, rate, interest)",
    "embed = build_balance_embed(interaction.guild, interaction.user, account, rate)"
)

# Also fix the call in profile_command which passes interest
text = text.replace(
    "embed = build_balance_embed(interaction.guild, member, account, rate, interest)",
    "embed = build_balance_embed(interaction.guild, member, account, rate)"
)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Done")
