
import re
with open("bot.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("f\"├─ 🧰 Сейф (Деньги): {format_money_plain(account.get('safe_cash', 0.0))}\\n\\\"", "f\"├─ 🧰 Сейф (Деньги): {format_money_plain(account.get('safe_cash', 0.0))}\\n\"")
text = text.replace("0.0))} золота\\n\\\"", "0.0))} золота\\n\"")

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Fixed")

