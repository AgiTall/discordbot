
with open("cogs/casino.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "async def blackjack_command(self" in line:
        new_lines.append("    @blackjack_command.error\n")
        new_lines.append("    async def blackjack_error(self, interaction, error):\n")
        new_lines.append("        import traceback\n")
        new_lines.append("        print(f\"Blackjack error: {error}\")\n")
        new_lines.append("        traceback.print_exception(type(error), error, error.__traceback__)\n")
        new_lines.append("        if not interaction.response.is_done():\n")
        new_lines.append("            await interaction.response.send_message(f\"Произошла ошибка: {error}\", ephemeral=True)\n\n")
    new_lines.append(line)

with open("cogs/casino.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
print("Added error handler")

