
import re

with open("bot.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add gang info to profile command
old_profile = """        embed.add_field(
            name="📅 Регистрация",
            value=f"<t:{int(member.created_at.timestamp())}:D>",
            inline=True,
        )"""
new_profile = """        gang_name = account.get("gang_name")
        gang_text = f"🏴‍☠️ {gang_name}" if gang_name else "Одиночка"
        embed.add_field(
            name="📅 Регистрация",
            value=f"<t:{int(member.created_at.timestamp())}:D>",
            inline=True,
        )
        embed.add_field(
            name="🏴‍☠️ Фракция",
            value=gang_text,
            inline=True,
        )"""
text = text.replace(old_profile, new_profile)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Done")

