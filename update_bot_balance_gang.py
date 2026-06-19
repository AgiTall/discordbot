import re

with open("bot.py", "r", encoding="utf-8") as f:
    text = f.read()

def replace_func(m):
    return """def build_balance_embed(guild, member, account, rate):
    cash = account["cash"]
    gold = account["gold"]
    treasure_maps = account["treasure_maps"]
    role_sections, unavailable_role_sections = format_balance_role_sections(
        guild, member, account
    )

    gang_name = account.get("gang_name")
    gang_str = ""
    if gang_name:
        guild_data = economy_data.current()
        gang = guild_data.get("gangs", {}).get(gang_name, {})
        gang_id = gang.get("id", "N/A")
        is_leader = gang.get("leader") == member.id
        role_name = gang.get("leader_role_name", "Лидер") if is_leader else gang.get("member_role_name", "Участник")
        gang_str = f"🏴‍☠️ Фракция: **{gang_name}** [#{gang_id}] ({role_name})\\n\\n"

    description = (
        "💰 Финансы\\n"
        f"├─ {get_cash_emoji()} Деньги: {format_money_plain(cash)}\\n"
        f"├─ 🧰 Сейф (Деньги): {format_money_plain(account.get('safe_cash', 0.0))}\\n"
        f"├─ 🧰 Сейф (Золото): {format_number(account.get('safe_gold', 0.0))} золота\\n"
        f"├─ {get_gold_emoji()} Золото: {format_gold_plain(gold)}\\n"
        f"└─ {get_map_emoji()} Карты: {format_treasure_maps_plain(treasure_maps)}\\n\\n"
        f"{gang_str}"
        "🎭 Роли\\n"
        f"{role_sections}\\n"
        "\\n"
        "🏦 Экономика\\n"
        f"├─ Курс: 1 {get_gold_emoji()} = {format_exchange_rate(rate)}\\n\\n"
        "🔒 Недоступные роли\\n"
        f"{unavailable_role_sections}\\n"
    )"""

text = re.sub(r"def build_balance_embed.*?f\"\{unavailable_role_sections\}\\n\"\n    \)", replace_func, text, flags=re.DOTALL)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Done")
